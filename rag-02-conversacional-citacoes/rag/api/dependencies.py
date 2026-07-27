"""Provedores de dependência da camada HTTP.

Dois modelos de injeção convivem neste projeto, e a regra entre eles é a da
seção 2.5 da guideline de arquitetura: **container para o que é estável,
construção explícita para o que depende da requisição.**

As CLIs montam tudo à mão em `composition.py`. Aqui o container do FastAPI
resolve o que é estável, e a cadeia `Properties -> HealthyProperties ->
Repository` dá um ganho que a montagem manual não tem: se `HealthyProperties`
já rodou o verificador, toda rota que a declarar herda a verificação, e uma
rota nova não pode esquecer de checar.

O que **não** vem por `Depends`: `k`, `history_window`, `conditional_rewrite`,
`chunk_size`. Chegam em `options`, então as facades que os usam são montadas na
própria rota.
"""

from typing import Annotated

from fastapi import Depends

from .. import config
from ..config import RagProperties
from ..domain.models import Conversation, Turn
from ..exceptions import InvalidParameterException
from ..presenter.json_presenter import JsonPresenter
from ..repository.vector_repository import QdrantVectorRepository, VectorRepository
from ..service.citation_resolver import CitationResolver
from ..service.generation_service import (
    GenerationService,
    OpenAiGenerationService,
    create_embeddings,
)
from ..service.health_checker import HealthChecker
from ..service.prompt_builder import PromptBuilder


def provide_properties() -> RagProperties:
    """Recarrega a cada requisição: o .env pode mudar sem reiniciar o servidor."""
    return config.load()


Properties = Annotated[RagProperties, Depends(provide_properties)]


def provide_healthy_properties(properties: Properties) -> RagProperties:
    """Propriedades, com o Qdrant já verificado."""
    HealthChecker(properties).check()
    return properties


HealthyProperties = Annotated[RagProperties, Depends(provide_healthy_properties)]


def provide_repository(properties: HealthyProperties) -> VectorRepository:
    """Trocar de armazém vetorial mexe aqui e em `composition.build_repository`.

    Dois lugares, não um, e é o preço registrado de ter dois modelos de
    injeção. O critério de aceite 7 do PRD conta ambos como "uma linha cada".
    """
    return QdrantVectorRepository(
        host=properties.qdrant_host,
        port=properties.qdrant_port,
        collection=properties.collection,
        embeddings=create_embeddings(
            properties.embedding_model,
            properties.max_retries,
            properties.request_timeout_s,
        ),
        timeout_s=properties.request_timeout_s,
    )


Repository = Annotated[VectorRepository, Depends(provide_repository)]


def provide_checked_repository(
    properties: HealthyProperties, repository: Repository
) -> VectorRepository:
    """Repositório com a dimensão da coleção já conferida contra o modelo.

    Separado de `provide_repository` porque a conferência precisa do
    repositório pronto. Rotas que tocam o índice declaram esta; a ingestão
    declara a anterior, já que ela recria a coleção e a dimensão antiga não
    importa.
    """
    HealthChecker(properties).check_dimensions(repository)
    return repository


CheckedRepository = Annotated[VectorRepository, Depends(provide_checked_repository)]


def provide_generation(properties: HealthyProperties) -> GenerationService:
    return OpenAiGenerationService(
        properties.chat_model,
        properties.temperature,
        properties.max_retries,
        properties.request_timeout_s,
    )


Generation = Annotated[GenerationService, Depends(provide_generation)]

Prompts = Annotated[PromptBuilder, Depends(PromptBuilder)]
Citations = Annotated[CitationResolver, Depends(CitationResolver)]
Presenter = Annotated[JsonPresenter, Depends(JsonPresenter)]


def read_int(options: dict, key: str, default: int) -> int:
    """Lê um inteiro de `options`, caindo no default em silêncio.

    Chave desconhecida ou valor ilegível cai no default. É exigência do
    contrato: um frontend mais novo que o backend não pode quebrá-lo.

    Note a assimetria deliberada com `read_history`: valor MAL FORMADO de `k`
    é ignorado, valor mal formado de histórico é erro. A diferença é a
    consequência. Um `k` errado degrada a busca de um jeito que aparece; um
    histórico truncado em silêncio produz reescrita errada sem sintoma.
    """
    try:
        return int(options.get(key, default))
    except (TypeError, ValueError):
        return default


def read_bool(options: dict, key: str, default: bool) -> bool:
    value = options.get(key, default)
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "sim", "yes"}
    return default


def read_history(options: dict) -> Conversation:
    """Constrói a conversa a partir de `options.history`.

    **Turno malformado é 422, nunca descarte silencioso.** Um histórico
    parcialmente perdido produz uma reescrita que resolve o pronome contra a
    referência errada: a pergunta reescrita sai bem formada, sobre o assunto
    errado, e nada denuncia. Falhar alto aqui é mais barato que diagnosticar
    isso depois.

    Ausência de `history` é o caso normal do primeiro turno, e não é erro.
    """
    raw = options.get("history")
    if raw is None:
        return Conversation()

    if not isinstance(raw, list):
        raise InvalidParameterException(
            "options.history deve ser uma lista de turnos "
            "{question, answer}, do mais antigo para o mais recente."
        )

    turns: list[Turn] = []
    for position, item in enumerate(raw, 1):
        if not isinstance(item, dict):
            raise InvalidParameterException(
                f"turno {position} de options.history não é um objeto."
            )
        question = item.get("question")
        answer = item.get("answer")
        if not isinstance(question, str) or not isinstance(answer, str):
            raise InvalidParameterException(
                f"turno {position} de options.history precisa de 'question' e "
                "'answer', ambos texto."
            )
        turns.append(Turn(question=question, answer=answer))

    return Conversation(tuple(turns))
