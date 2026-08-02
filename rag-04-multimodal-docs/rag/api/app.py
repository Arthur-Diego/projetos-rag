"""Fábrica do app HTTP.

Um único lugar monta o app: middleware, tratadores de erro e rotas. Rota nova =
arquivo em `routes/` + uma linha na tupla lá embaixo.

Publica as quatro rotas do contrato compartilhado: `/ask`, `/ingest`, `/health` e
`/capabilities`. `serve.py` importa daqui e não de outro lugar.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import error_handlers
from .routes import ask, ingest, meta

#: Versão do contrato compartilhado que este backend serve. A evolução aditiva
#: 1.2.0 -> 1.3.0 (`kind`, `content_html`, `elements`) foi entregue pela task_02,
#: no yaml compartilhado; este valor é o que o backend PROMETE cumprir.
CONTRACT_VERSION = "1.3.0"

# O frontend genérico roda em outra porta (Vite usa 5173), e o navegador exige
# CORS. Restrito a localhost: isto é ferramenta de estudo local, não serviço
# exposto — o HLD amarra o servidor em 127.0.0.1 pelo mesmo motivo.
ORIGENS_LOCAIS = r"http://(localhost|127\.0\.0\.1):\d+"


def create_app() -> FastAPI:
    """Monta o app: middleware, error handlers e rotas.

    Fábrica, e não módulo com `app = FastAPI()` no topo, porque os testes
    precisam de uma instância nova por caso e o uvicorn aceita `--factory`.
    """
    app = FastAPI(
        title="rag-04-multimodal-docs",
        version=CONTRACT_VERSION,
        summary="Pipeline RAG multimodal: tabelas e imagens de PDFs complexos.",
        description=(
            "Implementa ../docs/contracts/rag-api.yaml 1.3.0. A ingestão deste "
            "projeto RECONCILIA em vez de recriar: reprocessa o que mudou e "
            "preserva o que não mudou (nota aditiva do /ingest na 1.3.0)."
        ),
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=ORIGENS_LOCAIS,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )

    error_handlers.register(app)

    for module in (meta, ask, ingest):
        app.include_router(module.router)

    return app
