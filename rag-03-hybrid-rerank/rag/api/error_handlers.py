"""Tradução de exceção de domínio em status HTTP.

Um lugar só, e é o que impede cada rota de inventar o seu próprio código. A
lista abaixo é a matriz de erros da seção 6 do FDD, executável.

Toda resposta de erro sai no formato `Problem` do contrato compartilhado, com
`detail` dizendo o que fazer. Traceback nunca chega ao cliente.
"""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from ..exceptions import (
    EmptyCorpusException,
    EmptyIndexException,
    InvalidConfigurationException,
    InvalidIndexMappingException,
    InvalidParameterException,
    NoExtractableTextException,
    RagException,
    ServiceUnavailableException,
)
from ..presenter.json_presenter import JsonPresenter

# exceção -> (status, título, código do contrato)
_MAPPING: list[tuple[type[RagException], int, str, str]] = [
    (EmptyIndexException, 409, "Índice vazio", "EMPTY_INDEX"),
    # 409 junto de EMPTY_INDEX porque as duas dizem a mesma coisa ao usuário: o
    # índice precisa ser reconstruído. O CÓDIGO é que as distingue, e precisa
    # distinguir, porque as receitas são diferentes: uma manda indexar, a outra
    # manda apagar o volume e indexar.
    #
    # Precisa vir ANTES do tratador genérico. Esta lista para no primeiro
    # isinstance que casar, e uma exceção sem linha própria cai em 500 por
    # omissão, o que aqui seria pior que o normal: 500 diz "defeito do
    # servidor", quando o problema é um índice mal construído que o usuário
    # resolve em dois comandos.
    (
        InvalidIndexMappingException,
        409,
        "Índice mal mapeado",
        "INVALID_INDEX_MAPPING",
    ),
    (EmptyCorpusException, 422, "Corpus vazio", "EMPTY_CORPUS"),
    (NoExtractableTextException, 422, "Sem texto extraível", "NO_EXTRACTABLE_TEXT"),
    (InvalidParameterException, 422, "Parâmetro inválido", "INVALID_PARAMETER"),
    (ServiceUnavailableException, 503, "Serviço indisponível", "SERVICE_UNAVAILABLE"),
    # Por último: é a mais genérica das configuráveis, e a ordem importa porque
    # a busca para na primeira que casar.
    (InvalidConfigurationException, 500, "Configuração inválida", "INVALID_CONFIGURATION"),
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
        # RagException nova que ninguém mapeou. 500 é honesto: o defeito é a
        # ausência da linha na tabela acima, não o pedido do cliente.
        return JSONResponse(
            status_code=500,
            content=presenter.problem("Erro interno", str(exc), "UNMAPPED"),
        )

    app.add_exception_handler(RagException, handle)
