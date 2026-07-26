"""Fábrica da aplicação HTTP.

Um único lugar monta o app: middleware, tratadores de erro e rotas. É o
equivalente da classe anotada com `@SpringBootApplication` mais a configuração
de CORS.

Fábrica em vez de instância global de propósito: um teste pode criar um app
isolado, e amanhã dá para criar variantes (com e sem CORS, por exemplo) sem
mexer aqui.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import error_handlers
from .descriptor import PROJECT
from .routes import ask, ingest, meta

# O frontend roda em outra porta (Vite usa 5173), e o navegador exige CORS.
# Restrito a localhost: isto é ferramenta de estudo local, não serviço exposto.
ORIGENS_LOCAIS = r"http://(localhost|127\.0\.0\.1):\d+"


def create_app() -> FastAPI:
    app = FastAPI(
        title=f"Contrato RAG — {PROJECT}",
        version="1.0.0",
        description=(
            "Implementa docs/contracts/rag-api.yaml. "
            "A lógica vive nas facades; esta camada é só superfície."
        ),
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=ORIGENS_LOCAIS,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )

    error_handlers.registrar(app)

    for modulo in (meta, ask, ingest):
        app.include_router(modulo.router)

    return app
