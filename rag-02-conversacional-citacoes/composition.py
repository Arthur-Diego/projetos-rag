"""Composition root das CLIs.

Em Python não há container de injeção de dependência, então alguém precisa
escrever as implementações concretas com a mão. Nas CLIs esse alguém é o
entrypoint; este módulo existe porque `ask.py` e `chat.py` montam exatamente o
mesmo grafo, e duplicá-lo garantiria que as duas versões divergissem.

**Isto NÃO é uma camada** (ADR-006). São funções no nível dos entrypoints,
importadas por eles, e nada em `rag/` as conhece. Uma camada aqui reintroduziria
a indireção que o ADR-007 do Projeto 1 alertou.

A camada HTTP não usa este módulo: ela monta pelo container do FastAPI, em
`rag/api/dependencies.py`. Dois modelos de injeção convivem, e a regra é a da
seção 2.5 da guideline: container para o estável, construção explícita para o
que vem do corpo da requisição.

**É AQUI que se troca o armazém vetorial** (critério de aceite 7 do PRD): uma
linha em `build_repository`, e mais nada no projeto muda.
"""

from rag.config import (
    DEFAULT_CHUNK_OVERLAP,
    DEFAULT_CHUNK_SIZE,
    DEFAULT_CONDITIONAL_REWRITE,
    DEFAULT_HISTORY_WINDOW,
    DEFAULT_K,
    RagProperties,
)
from rag.facade.ingestion_facade import IngestionFacade
from rag.facade.query_facade import QueryFacade
from rag.repository.document_reader import PdfDocumentReader
from rag.repository.vector_repository import QdrantVectorRepository, VectorRepository
from rag.service.chunking_service import RecursiveChunkingService
from rag.service.citation_resolver import CitationResolver
from rag.service.generation_service import OpenAiGenerationService, create_embeddings
from rag.service.prompt_builder import PromptBuilder
from rag.service.query_rewrite_service import QueryRewriteService
from rag.service.retrieval_service import RetrievalService


def build_repository(properties: RagProperties) -> VectorRepository:
    """A única linha que muda para trocar de armazém vetorial.

    Para o exercício 3 do guia e o critério 7 do PRD, troque
    `QdrantVectorRepository` por `ChromaVectorRepository` (mesmo Protocol, mesmo
    construtor menos a porta) e rode de novo. Se precisar mudar mais que isto, a
    fronteira vazou, e o FDD manda registrar o que vazou antes de consertar.
    """
    return QdrantVectorRepository(
        host=properties.qdrant_host,
        port=properties.qdrant_port,
        collection=properties.collection,
        embeddings=create_embeddings(
            properties.embedding_model, properties.max_retries, properties.request_timeout_s
        ),
        timeout_s=properties.request_timeout_s,
    )


def build_query_facade(
    properties: RagProperties,
    k: int = DEFAULT_K,
    history_window: int = DEFAULT_HISTORY_WINDOW,
    conditional_rewrite: bool = DEFAULT_CONDITIONAL_REWRITE,
) -> QueryFacade:
    generation = OpenAiGenerationService(
        properties.chat_model,
        properties.temperature,
        properties.max_retries,
        properties.request_timeout_s,
    )
    return QueryFacade(
        # O MESMO serviço de geração serve os dois estágios. É a origem do custo
        # dobrado por turno, e vê-lo escrito duas vezes aqui é mais honesto do
        # que escondê-lo atrás de duas instâncias.
        rewrite=QueryRewriteService(generation, conditional=conditional_rewrite),
        retrieval=RetrievalService(build_repository(properties), k=k),
        prompts=PromptBuilder(),
        generation=generation,
        citations=CitationResolver(),
        history_window=history_window,
    )


def build_ingestion_facade(
    properties: RagProperties,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> IngestionFacade:
    return IngestionFacade(
        reader=PdfDocumentReader(properties.pdf_dir),
        chunking=RecursiveChunkingService(chunk_size, chunk_overlap),
        repository=build_repository(properties),
        dimensions=properties.embedding_dimensions,
    )
