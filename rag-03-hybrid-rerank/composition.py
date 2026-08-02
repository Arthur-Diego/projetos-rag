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

from elasticsearch import Elasticsearch

from rag.config import (
    DEFAULT_CANDIDATES,
    DEFAULT_CHUNK_OVERLAP,
    DEFAULT_CHUNK_SIZE,
    DEFAULT_CONDITIONAL_REWRITE,
    DEFAULT_HISTORY_WINDOW,
    DEFAULT_HYBRID,
    DEFAULT_K,
    DEFAULT_RERANK,
    DEFAULT_RRF_K,
    RagProperties,
)
from rag.facade.ingestion_facade import IngestionFacade
from rag.facade.query_facade import QueryFacade
from rag.repository.document_reader import PdfDocumentReader
from rag.repository.keyword_repository import ElasticKeywordRepository
from rag.repository.vector_repository import ElasticVectorRepository, VectorRepository
from rag.service.chunking_service import RecursiveChunkingService
from rag.service.citation_resolver import CitationResolver
from rag.service.generation_service import OpenAiGenerationService, create_embeddings
from rag.service.prompt_builder import PromptBuilder
from rag.service.query_rewrite_service import QueryRewriteService
from rag.service.retrieval.dense_search_service import DenseSearchService
from rag.service.retrieval.fusion_service import FusionService
from rag.service.retrieval.keyword_search_service import KeywordSearchService
from rag.service.retrieval.rerank_service import CrossEncoderRerankService
from rag.service.retrieval.retrieval_service import RetrievalService


def build_client(properties: RagProperties) -> Elasticsearch:
    """Um cliente, compartilhado pelos DOIS repositórios.

    Eles falam com o mesmo container, sobre o mesmo índice e o mesmo documento
    (ADR-001). Dois clientes seriam dois pools de conexão para nada.
    """
    return Elasticsearch(
        properties.elastic_url, request_timeout=properties.request_timeout_s
    )


def build_repository(
    properties: RagProperties, client: Elasticsearch
) -> VectorRepository:
    """O caminho denso, e o dono do índice e do mapping.

    Trocar de armazém mexe aqui e em `rag.api.dependencies.provide_repository`.
    São dois lugares, e é o preço registrado de ter dois modelos de injeção.

    A demonstração de trocar o armazém em uma linha, que era critério de aceite
    do Projeto 2, saiu de escopo aqui (ADR-004 da feature): existe um motor único
    atendendo dois caminhos, e substituí-lo por um que só faz busca densa mataria
    a metade léxica do funil. O que continua cobrado é a contenção: nenhum
    vocabulário do Elasticsearch acima da camada de repositório.
    """
    return ElasticVectorRepository(
        client=client,
        index=properties.collection,
        embeddings=create_embeddings(
            properties.embedding_model, properties.max_retries, properties.request_timeout_s
        ),
    )


def build_query_facade(
    properties: RagProperties,
    k: int = DEFAULT_K,
    history_window: int = DEFAULT_HISTORY_WINDOW,
    conditional_rewrite: bool = DEFAULT_CONDITIONAL_REWRITE,
    candidates: int = DEFAULT_CANDIDATES,
    rrf_k: int = DEFAULT_RRF_K,
    hybrid: bool = DEFAULT_HYBRID,
    rerank: bool = DEFAULT_RERANK,
) -> QueryFacade:
    generation = OpenAiGenerationService(
        properties.chat_model,
        properties.temperature,
        properties.max_retries,
        properties.request_timeout_s,
    )
    client = build_client(properties)
    return QueryFacade(
        # O MESMO serviço de geração serve os dois estágios. É a origem do custo
        # dobrado por turno, e vê-lo escrito duas vezes aqui é mais honesto do
        # que escondê-lo atrás de duas instâncias.
        rewrite=QueryRewriteService(generation, conditional=conditional_rewrite),
        retrieval=RetrievalService(
            DenseSearchService(build_repository(properties, client)),
            keywords=KeywordSearchService(
                ElasticKeywordRepository(client=client, index=properties.collection)
            ),
            fusion=FusionService(),
            reranker=CrossEncoderRerankService(properties.reranker_model),
            k=k,
            candidates=candidates,
            rrf_k=rrf_k,
            hybrid=hybrid,
            rerank=rerank,
        ),
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
        repository=build_repository(properties, build_client(properties)),
        dimensions=properties.embedding_dimensions,
    )
