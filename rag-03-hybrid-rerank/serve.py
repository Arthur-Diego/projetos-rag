"""API HTTP do Projeto 2, implementando o contrato compartilhado 1.1.0.

    uvicorn serve:app --reload --port 8080
    python serve.py                          # equivalente, sem reload

Quarto entrypoint, ao lado de ingest.py, ask.py e chat.py. Deliberadamente
magro: a camada HTTP inteira vive em `rag/api/` e a lógica de RAG nas facades.
Este arquivo só publica o app e sabe subir um servidor.

**Este servidor não guarda conversa** (ADR-002). A transcrição chega em
`options.history` a cada `/ask` e vai embora com a resposta. Não há dicionário
de sessão para limpar, nada vaza entre requisições, e nada morre no restart
porque nada vivia aqui.

Contrato: ../docs/contracts/rag-api.yaml
"""

import sys

from rag.api.app import create_app

app = create_app()

PORTA = 8080


def main() -> int:
    import uvicorn

    # 127.0.0.1, não 0.0.0.0: a API não tem autenticação nem limite de taxa, e
    # só deve ser alcançável da própria máquina. Expor em 0.0.0.0 invalidaria a
    # premissa de usuário único que sustenta o ADR-002.
    uvicorn.run(app, host="127.0.0.1", port=PORTA)
    return 0


if __name__ == "__main__":
    sys.exit(main())
