"""API HTTP do Projeto 1, implementando o contrato compartilhado.

    uvicorn serve:app --reload --port 8080
    python serve.py                          # equivalente, sem reload

Terceiro entrypoint, ao lado de ingest.py e ask.py. É deliberadamente magro: a
camada HTTP inteira vive em `rag/api/` (ADR-009), e a lógica de RAG nas facades
(ADR-007). Este arquivo só publica o app e sabe subir um servidor.

Contrato: ../docs/contracts/rag-api.yaml
"""

import sys

from rag.api.app import create_app

app = create_app()

PORTA = 8080


def main() -> int:
    import uvicorn

    # 127.0.0.1, não 0.0.0.0: a API não tem autenticação nem limite de taxa,
    # e só deve ser alcançável da própria máquina.
    uvicorn.run(app, host="127.0.0.1", port=PORTA)
    return 0


if __name__ == "__main__":
    sys.exit(main())
