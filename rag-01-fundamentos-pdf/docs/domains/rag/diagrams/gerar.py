#!/usr/bin/env python3
"""Gera README.md embutindo os diagramas Mermaid.

Existe por um motivo prático: a extensão bierner.markdown-mermaid do VS Code só
renderiza blocos ```mermaid dentro de arquivos .md. Um .mmd solto não
pré-visualiza com Ctrl+Shift+V.

Os .mmd continuam sendo a fonte de verdade (é neles que o mermaid-cli e a
extensão Mermaid Chart operam). O README embute cópias, e este script mantém as
duas em sincronia.

    python docs/domains/rag/diagrams/gerar.py
"""

import re
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
MODELO = AQUI / "_relatorio.md"
SAIDA = AQUI / "README.md"
MERMAID = AQUI / "mermaid"

MARCADOR = re.compile(r"^<!-- INCLUI: (.+?\.mmd) -->$", re.MULTILINE)


def expandir(_modelo: str) -> str:
    faltando = []

    def troca(m: re.Match) -> str:
        arquivo = MERMAID / m.group(1)
        if not arquivo.is_file():
            faltando.append(m.group(1))
            return m.group(0)
        return "```mermaid\n" + arquivo.read_text(encoding="utf-8").strip() + "\n```"

    resultado = MARCADOR.sub(troca, _modelo)
    if faltando:
        print(f"erro: não encontrei {', '.join(faltando)}", file=sys.stderr)
        raise SystemExit(1)
    return resultado


def main() -> int:
    if not MODELO.is_file():
        print(f"erro: modelo ausente: {MODELO}", file=sys.stderr)
        return 1

    SAIDA.write_text(expandir(MODELO.read_text(encoding="utf-8")), encoding="utf-8")

    embutidos = len(MARCADOR.findall(MODELO.read_text(encoding="utf-8")))
    print(f"{SAIDA.name} gerado com {embutidos} diagrama(s) embutido(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
