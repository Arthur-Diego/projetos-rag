#!/usr/bin/env python3
"""Inspeção pós-partição: o que o `hi_res` detectou como tabela.

**É a mitigação do risco 1 do FDD, e roda ANTES de qualquer gasto.** O modo de
falha que este script existe para tornar visível: o `hi_res` conclui sem erro,
não detecta tabela nenhuma (ou detecta e não estrutura), a ingestão resume os
textos, tudo funciona — e a conclusão do projeto vira "multi-vector não ajudou"
quando a verdade é que nunca houve tabela no índice.

**Não faz uma única chamada de API.** Lê o cache de partição de `data/partition/`
(ADR-005) ou particiona localmente, e imprime. Custa CPU, nunca dinheiro.

O julgamento é humano (AC-2 da US-005): o script põe na tela o que a máquina
achou, e quem decide se está bom o bastante é quem tem o PDF aberto ao lado.

Uso, da raiz do projeto:

    .venv/bin/python docs/operations/inspeciona-tabelas.py
    .venv/bin/python docs/operations/inspeciona-tabelas.py --preview 400

Não é um módulo de `rag/`: é ferramenta de operação, mora em `docs/operations/`
com o resto do runbook e importa o pacote como um cliente qualquer.
"""

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from unstructured.documents.elements import Table  # noqa: E402

from rag import config  # noqa: E402
from rag.exceptions import RagException  # noqa: E402
from rag.repository.corpus_reader import PdfCorpusReader  # noqa: E402
from rag.repository.pdf_partitioner import (  # noqa: E402
    FilePartitionCache,
    UnstructuredPartitioner,
)
from rag.service.partition_service import PartitionService  # noqa: E402
from rag.service.routing_service import page_of  # noqa: E402

#: Uma tabela cujo HTML não tem `<td>` nenhum foi DETECTADA mas não
#: ESTRUTURADA: o modelo de layout marcou a região, o Table Transformer não
#: reconstruiu as células. Aparece na listagem marcada como suspeita, nunca
#: escondida (EC-2 da US-005) — é meio caminho do risco 1, e some se a listagem
#: só contar linhas.
CELL_PATTERN = re.compile(r"<t[dh][\s>]", re.IGNORECASE)


class StderrLog:
    """Diagnóstico da partição no stderr, para não sujar a listagem no stdout."""

    def stage(self, message: str) -> None:
        print(message, file=sys.stderr)


def preview_of(html: str, limit: int) -> str:
    """O HTML em uma linha, colapsando espaços, truncado para caber na tela."""
    flat = " ".join(html.split())
    return flat if len(flat) <= limit else f"{flat[:limit]}…"


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Lista as tabelas detectadas pela partição, com página e preview. "
            "Sem nenhuma chamada de API."
        )
    )
    parser.add_argument(
        "--preview",
        type=int,
        default=300,
        help="quantos caracteres de HTML mostrar por tabela (default: 300)",
    )
    args = parser.parse_args()

    try:
        properties = config.load()
    except RagException as e:
        print(f"erro: {e}", file=sys.stderr)
        return 1

    if properties.partition_strategy == "fast":
        print(
            "ATENÇÃO: PARTITION_STRATEGY=fast. Esta estratégia NÃO detecta "
            "tabela nenhuma — uma listagem vazia aqui não diz nada sobre o "
            "corpus.",
            file=sys.stderr,
        )

    partition = PartitionService(
        partitioner=UnstructuredPartitioner(
            properties.partition_strategy, properties.figures_dir
        ),
        cache=FilePartitionCache(
            properties.partition_cache_dir, properties.partition_strategy
        ),
        log=StderrLog(),
    )

    try:
        paths = PdfCorpusReader(properties.pdf_dir).require_files()
    except RagException as e:
        print(f"erro: {e}", file=sys.stderr)
        return 1

    total = 0
    suspeitas = 0
    for path in paths:
        try:
            # Sem cache, isto PARTICIONA: minutos de CPU, zero de API. É o
            # caminho da EC-1 da US-005, e o log de estágio já avisa qual dos
            # dois está acontecendo.
            elements = partition.partition(path)
        except RagException as e:
            print(f"erro: {e}", file=sys.stderr)
            return 1

        # Mesmo critério do roteamento (`isinstance`, não o nome da categoria):
        # inspecionar por um critério diferente do que a ingestão usa faria a
        # listagem prometer tabelas que o índice não recebe.
        tables = [element for element in elements if isinstance(element, Table)]
        print(f"\n=== {path.name}: {len(tables)} tabela(s) detectada(s) ===")

        for position, table in enumerate(tables, start=1):
            html = getattr(table.metadata, "text_as_html", None) or ""
            marca = ""
            if not html.strip():
                marca = "  [SUSPEITA: sem HTML — detectada, não estruturada]"
                suspeitas += 1
            elif not CELL_PATTERN.search(html):
                marca = "  [SUSPEITA: HTML sem células]"
                suspeitas += 1
            print(f"\n{position}. página {page_of(table)}{marca}")
            print(f"   {preview_of(html or table.text, args.preview)}")
        total += len(tables)

    print(f"\ntotal: {total} tabela(s), {suspeitas} suspeita(s)")
    if total == 0:
        print(
            "\nNENHUMA TABELA DETECTADA. É o risco 1 do FDD. Antes de gastar "
            "API, confira:\n"
            "  - PARTITION_STRATEGY=hi_res no .env (fast não detecta tabela)\n"
            "  - pdftoppm -v && tesseract --list-langs | grep por\n"
            "  - o PDF realmente tem tabela na região que você espera",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
