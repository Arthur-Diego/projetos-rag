"""Tradução de exceção de domínio para status HTTP.

Equivalente ao `@ControllerAdvice` do Spring: **um lugar só** decide o status de
cada falha. Sem isso, cada rota repetiria try/except e os status divergiriam
entre elas com o tempo.

As camadas de `rag/` não sabem o que é HTTP; é aqui que a ponte acontece.
"""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from ..exceptions import (
    EmptyIndexException,
    InvalidConfigurationException,
    RagException,
    ServiceUnavailableException,
)
from ..presenter.json_presenter import JsonPresenter

# Ordem irrelevante: são classes irmãs, sem sobreposição.
STATUS_POR_EXCECAO: list[tuple[type[RagException], int, str]] = [
    (ServiceUnavailableException, 503, "SERVICE_UNAVAILABLE"),
    (EmptyIndexException, 409, "EMPTY_INDEX"),
    (InvalidConfigurationException, 422, "INVALID_CONFIGURATION"),
]

PADRAO = (500, "INTERNAL")


def registrar(app: FastAPI) -> None:
    presenter = JsonPresenter()

    @app.exception_handler(RagException)
    async def _tratar(_: Request, exc: RagException) -> JSONResponse:
        status, code = next(
            ((s, c) for tipo, s, c in STATUS_POR_EXCECAO if isinstance(exc, tipo)),
            PADRAO,
        )
        return JSONResponse(
            status_code=status,
            content=presenter.problem(type(exc).__name__, str(exc), code),
        )
