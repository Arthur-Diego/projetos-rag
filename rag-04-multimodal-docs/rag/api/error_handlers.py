"""Tradução de exceção de domínio em status HTTP.

Um lugar só, e é o que impede cada rota de inventar o seu próprio código. A
lista abaixo é a matriz de erros da seção 6 do FDD, executável.

Toda resposta de erro sai no formato `Problem` do contrato compartilhado, com
`detail` dizendo o que fazer. Traceback nunca chega ao cliente.

`EmptyIndexException` (409) só ocorre no `/ask`: é lá que índice vazio impede o
trabalho. A ingestão não depende dele.
"""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from ..exceptions import (
    EmptyCorpusException,
    EmptyIndexException,
    InvalidConfigurationException,
    InvalidParameterException,
    PartitionFailedException,
    RagException,
    ServiceUnavailableException,
)
from ..presenter.json_presenter import JsonPresenter

# exceção -> (status, título, código do contrato). A busca para na PRIMEIRA que
# casar por `isinstance`, então a ordem vai da mais específica para a mais geral.
_MAPPING: list[tuple[type[RagException], int, str, str]] = [
    (EmptyIndexException, 409, "Índice vazio", "EMPTY_INDEX"),
    (EmptyCorpusException, 422, "Corpus vazio", "EMPTY_CORPUS"),
    (InvalidParameterException, 422, "Parâmetro inválido", "INVALID_PARAMETER"),
    # 422 e não 500: o corpus não produziu o que precisava produzir, e a receita
    # (instalar poppler/tesseract, ou cair para strategy=fast) está na mensagem.
    # 500 diria "defeito do servidor" para algo que o operador resolve em um
    # comando.
    (PartitionFailedException, 422, "Partição falhou", "PARTITION_FAILED"),
    (ServiceUnavailableException, 503, "Serviço indisponível", "SERVICE_UNAVAILABLE"),
    # Por último: é a mais genérica das configuráveis.
    (
        InvalidConfigurationException,
        500,
        "Configuração inválida",
        "INVALID_CONFIGURATION",
    ),
]


def register(app: FastAPI) -> None:
    presenter = JsonPresenter()

    async def handle(_: Request, exc: Exception) -> JSONResponse:
        for kind, status, title, code in _MAPPING:
            if isinstance(exc, kind):
                return JSONResponse(
                    status_code=status,
                    content=presenter.problem(title, str(exc), code),
                )
        # `RagException` nova que ninguém mapeou. 500 é honesto: o defeito é a
        # ausência da linha na tabela acima, não o pedido do cliente.
        return JSONResponse(
            status_code=500,
            content=presenter.problem("Erro interno", str(exc), "UNMAPPED"),
        )

    app.add_exception_handler(RagException, handle)
