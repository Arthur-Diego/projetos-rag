"""Composition root das CLIs.

Em Python não há container de injeção de dependência, então alguém precisa
escrever as implementações concretas com a mão. Nas CLIs esse alguém é o
entrypoint; este módulo existe porque `ingest.py` e `ask.py` montam partes do
mesmo grafo, e duplicá-lo garantiria que as duas versões divergissem.

**Isto NÃO é uma camada** (precedente do ADR-006 do rag-03). São funções no
nível dos entrypoints, importadas por eles, e nada em `rag/` as conhece.

A camada HTTP não usa este módulo: ela monta pelo container do FastAPI, em
`rag/api/dependencies.py`. Dois modelos de injeção convivem, e a regra é a da
seção 2.5 da guideline: container para o estável, construção explícita para o
que vem do corpo da requisição.

**É aqui que se trocam os dois armazéns** (ADR-001) e o descritor de imagens
(ADR-006): `LocalFileStore` por object storage, ou a visão da OpenAI por um
modelo local, é uma linha em cada fábrica abaixo.
"""

import chromadb
from chromadb.api import ClientAPI
from langchain_classic.storage import LocalFileStore

from rag.config import DEFAULT_K, RagProperties
from rag.facade.ingestion_facade import IngestionFacade
from rag.facade.query_facade import QueryFacade
from rag.facade.reset_facade import ResetFacade
from rag.presenter.console_reporter import ConsoleReporter
from rag.repository.corpus_reader import PdfCorpusReader
from rag.repository.docstore_repository import (
    DocstoreRepository,
    FileDocstoreRepository,
)
from rag.repository.pdf_partitioner import (
    FilePartitionCache,
    UnstructuredPartitioner,
)
from rag.repository.vector_repository import ChromaVectorRepository, VectorRepository
from rag.service.enrichment_service import EnrichmentService
from rag.service.generation_service import OpenAiGenerationService
from rag.service.image_description_service import OpenAiImageDescriptionService
from rag.service.indexing_service import IndexingService
from rag.service.openai_models import create_chat_model, create_embeddings
from rag.service.partition_service import PartitionService
from rag.service.prompt_builder import PromptBuilder
from rag.service.retrieval.retrieval_service import RetrievalService
from rag.service.routing_service import ElementRoutingService
from rag.service.table_summary_service import TableSummaryService


def build_chroma_client(properties: RagProperties) -> ClientAPI:
    """Cliente HTTP do Chroma, com escopo de PROCESSO.

    Criado uma vez na composição e nunca por requisição — lição registrada do
    rag-03. O container é o da porta 8002 (`docker compose up -d chroma`); a
    conexão é verificada na construção, então um Chroma fora do ar falha aqui e
    não no meio da ingestão.
    """
    return chromadb.HttpClient(host=properties.chroma_host, port=properties.chroma_port)


def build_docstore(properties: RagProperties) -> LocalFileStore:
    """Docstore dos originais: a FONTE DE VERDADE dos conteúdos (ADR-001).

    `LocalFileStore` atrás da interface `BaseStore` (`mget`/`mset`). Trocar por
    object storage em produção é substituir esta linha, e mais nada: nenhuma
    camada acima conhece o tipo concreto.

    O diretório é criado aqui porque um docstore que não existe em disco é o
    modo de falha mais bobo possível numa ingestão que custa minutos.
    """
    properties.docstore_dir.mkdir(parents=True, exist_ok=True)
    return LocalFileStore(properties.docstore_dir)


def build_docstore_repository(properties: RagProperties) -> DocstoreRepository:
    """O armazém dos originais, já atrás da interface do projeto."""
    return FileDocstoreRepository(build_docstore(properties))


def build_vector_repository(
    properties: RagProperties, client: ClientAPI
) -> VectorRepository:
    """O armazém das representações.

    O cliente chega pronto, e não é construído aqui, porque ele tem escopo de
    PROCESSO: a task_04 vai montar também a consulta, e dois clientes contra o
    mesmo container seriam dois pools de conexão para nada.
    """
    return ChromaVectorRepository(
        client=client,
        collection=properties.collection,
        embeddings=create_embeddings(properties),
    )


def build_ingestion_facade(
    properties: RagProperties,
    client: ClientAPI,
    reporter: ConsoleReporter,
) -> IngestionFacade:
    """Monta o grafo inteiro da ingestão, com todas as escolhas à vista.

    **É aqui que se trocam as peças que os ADRs protegem**, uma linha cada:
    `LocalFileStore` por object storage (ADR-001), o descritor da OpenAI por um
    modelo local (ADR-006), a estratégia de partição (ADR-005). Nenhuma camada
    acima conhece o tipo concreto de nenhuma delas.

    O `reporter` entra como `IngestionLog` — a porta de diagnóstico por estágio.
    A facade não sabe que do outro lado há um terminal.
    """
    # Uma instância de cada armazém, compartilhada entre a facade (que consulta
    # a idempotência) e o IndexingService (que grava). Duas instâncias falariam
    # com o mesmo container abrindo dois pools de conexão para nada.
    docstore = build_docstore_repository(properties)
    vectors = build_vector_repository(properties, client)

    return IngestionFacade(
        reader=PdfCorpusReader(properties.pdf_dir),
        partition=PartitionService(
            partitioner=UnstructuredPartitioner(
                properties.partition_strategy, properties.figures_dir
            ),
            cache=FilePartitionCache(
                properties.partition_cache_dir, properties.partition_strategy
            ),
            log=reporter,
        ),
        routing=ElementRoutingService(properties.figures_dir, log=reporter),
        docstore=docstore,
        vectors=vectors,
        enrichment=EnrichmentService(
            summaries=TableSummaryService(
                create_chat_model(properties, properties.chat_model)
            ),
            descriptions=OpenAiImageDescriptionService(
                create_chat_model(properties, properties.vision_model)
            ),
            log=reporter,
        ),
        indexing=IndexingService(docstore, vectors, log=reporter),
        log=reporter,
    )


def build_query_facade(
    properties: RagProperties,
    client: ClientAPI,
    reporter: ConsoleReporter,
    k: int = DEFAULT_K,
) -> QueryFacade:
    """Monta o grafo da consulta: buscar representações, devolver originais.

    Mesmo molde da ingestão, e os mesmos pontos de troca. `k` chega por
    parâmetro porque é escolha de quem pergunta, não configuração do processo —
    a validação da faixa acontece na construção do `RetrievalService`, então um
    `--k` fora de 1 a 20 falha aqui, antes de qualquer chamada paga.
    """
    return QueryFacade(
        retrieval=RetrievalService(
            vectors=build_vector_repository(properties, client),
            docstore=build_docstore_repository(properties),
            k=k,
            log=reporter,
        ),
        prompts=PromptBuilder(log=reporter),
        generation=OpenAiGenerationService(
            create_chat_model(properties, properties.chat_model)
        ),
        log=reporter,
    )


def build_reset_facade(
    properties: RagProperties,
    client: ClientAPI,
    reporter: ConsoleReporter,
) -> ResetFacade:
    """Monta o grafo do reset: os dois armazéns, e nada mais.

    Nenhum modelo pago entra aqui, e é proposital: zerar armazém não deve
    depender de haver chave da OpenAI configurada nem custar uma chamada.
    """
    return ResetFacade(
        docstore=build_docstore_repository(properties),
        vectors=build_vector_repository(properties, client),
        log=reporter,
    )
