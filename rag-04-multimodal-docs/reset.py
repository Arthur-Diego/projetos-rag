"""Zera os DOIS armazéns numa operação, preservando o cache de partição.

    .venv/bin/python reset.py
    .venv/bin/python reset.py --sim

**Por que isto é um script CLI e não uma rota** (seção 1 do FDD): o `POST
/ingest` deste projeto reconcilia em vez de recriar (ADR-003), então a operação
destrutiva precisou sair de perto dele. Um botão "reingerir" que apagasse tudo
repagaria minutos de `hi_res` e uma chamada por tabela e por imagem.

O que ele NÃO apaga: `data/partition/` (ADR-005) e `pdfs/`. Zerar os armazéns
não pode custar o estágio local caro de novo.

Idempotente: rodar duas vezes seguidas conclui sem erro (EC-1 da US-013).
"""

import argparse
import sys

from composition import build_chroma_client, build_reset_facade
from rag import config
from rag.exceptions import RagException
from rag.presenter.console_reporter import ConsoleReporter


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Zera a coleção do Chroma e data/docstore/ numa operação. "
            "Preserva data/partition/."
        )
    )
    parser.add_argument(
        "--sim",
        action="store_true",
        help="não pergunta nada; use em script.",
    )
    return parser.parse_args()


def confirmed(reporter: ConsoleReporter) -> bool:
    """Pede confirmação interativa antes de destruir.

    A confirmação vive no ENTRYPOINT e não na facade, pela mesma regra que
    mantém `sys.exit()` fora das camadas: só quem sabe que existe um terminal
    pode perguntar a alguém. Sem terminal (`--sim`, ou entrada redirecionada),
    não há pergunta a fazer.

    Reingerir custa minutos de partição e uma chamada paga por tabela e por
    imagem. Um reset acidental não é um inconveniente, é uma conta.
    """
    reporter.diagnostic(
        "isto apaga a coleção do Chroma e todos os originais do docstore.\n"
        "o cache de partição em data/partition/ é preservado."
    )
    answer = input("confirma? [s/N] ").strip().lower()
    return answer in {"s", "sim"}


def main() -> int:
    """Devolve código de saída; quem encerra o processo é o bloco `__main__`."""
    reporter = ConsoleReporter()

    try:
        args = parse_args()
        if not args.sim and not confirmed(reporter):
            reporter.diagnostic("cancelado; nada foi apagado.")
            return 1

        properties = config.load()
        facade = build_reset_facade(
            properties, build_chroma_client(properties), reporter
        )
        reporter.reset(facade.reset())
    except RagException as e:
        reporter.failure(str(e))
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
