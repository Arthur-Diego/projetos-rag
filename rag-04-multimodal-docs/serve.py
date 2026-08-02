"""Entrypoint HTTP. Magro por desenho: só publica o app.

    .venv/bin/uvicorn serve:app --host 127.0.0.1 --port 8080

Amarrado em `127.0.0.1` (HLD, seção Segurança): não há autenticação, e nada
deste projeto deve escutar fora da máquina.

Publica as quatro rotas do contrato 1.3.0: `POST /ask`, `POST /ingest`,
`GET /health` e `GET /capabilities`. Quem as monta é `rag/api/app.py`.
"""

from rag.api.app import create_app

app = create_app()
