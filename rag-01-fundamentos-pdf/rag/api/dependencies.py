"""Provedores de dependência da camada HTTP.

Aqui mora a tensão registrada no ADR-009: `Depends` do FastAPI **é um container
de injeção de dependência**, e usá-lo distribui a montagem do grafo de objetos
por anotações, em vez de concentrá-la num composition root explícito como fazem
`ingest.py` e `ask.py` (ADR-007).

A escolha foi deliberada: é a forma idiomática do FastAPI e é o mesmo modelo dos
Projetos 8 a 10, em Spring. O preço é que a montagem deixa de estar toda num
arquivo só.

O que **não** vem por `Depends`: qualquer coisa que dependa do corpo da
requisição. `k` e `chunk_size` chegam em `options`, então as facades que os
usam são montadas na própria rota, explicitamente.
"""

from typing import Annotated

from fastapi import Depends

from .. import config
from ..config import RagProperties
from ..presenter.json_presenter import JsonPresenter
from ..repository.vector_repository import ChromaVectorRepository, VectorRepository
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
    """Propriedades, com o Chroma já verificado.

    Toda rota que toca o índice depende desta, e não da anterior: assim a
    verificação de pré-condição não fica esquecida em nenhuma rota nova.
    """
    HealthChecker(properties).check()
    return properties


HealthyProperties = Annotated[RagProperties, Depends(provide_healthy_properties)]


def provide_repository(properties: HealthyProperties) -> VectorRepository:
    return ChromaVectorRepository(
        host=properties.chroma_host,
        port=properties.chroma_port,
        collection=properties.collection,
        embeddings=create_embeddings(properties.embedding_model, properties.max_retries),
    )


Repository = Annotated[VectorRepository, Depends(provide_repository)]


def provide_generation(properties: HealthyProperties) -> GenerationService:
    return OpenAiGenerationService(
        properties.chat_model, properties.temperature, properties.max_retries
    )


Generation = Annotated[GenerationService, Depends(provide_generation)]

Prompts = Annotated[PromptBuilder, Depends(PromptBuilder)]
Presenter = Annotated[JsonPresenter, Depends(JsonPresenter)]


def read_int(options: dict, key: str, default: int) -> int:
    """Lê um parâmetro de `options`, ignorando o que não souber interpretar.

    Chave desconhecida ou valor inválido cai no default, em silêncio. É exigência
    do contrato: um frontend mais novo que o backend não pode quebrá-lo.
    """
    try:
        return int(options.get(key, default))
    except (TypeError, ValueError):
        return default
