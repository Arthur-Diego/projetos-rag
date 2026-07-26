"""Pipeline de RAG do Projeto 1, em camadas explícitas (ADR-005, ADR-006).

    rag/
    ├── exceptions.py            hierarquia de exceções do domínio
    ├── config.py                RagProperties (parâmetros externos)
    ├── domain/
    │   └── models.py            SearchHit (objeto de valor)
    ├── repository/              fala com fontes externas
    │   ├── document_reader.py   DocumentReader + PdfDocumentReader
    │   └── vector_repository.py VectorRepository + ChromaVectorRepository
    ├── service/                 regra e orquestração de uma responsabilidade
    │   ├── health_checker.py    HealthChecker
    │   ├── chunking_service.py  ChunkingService + RecursiveChunkingService
    │   ├── retrieval_service.py RetrievalService
    │   ├── prompt_builder.py    PromptBuilder
    │   └── generation_service.py GenerationService + OpenAiGenerationService
    └── presenter/
        └── console_reporter.py  ConsoleReporter

Convenção: **código em inglês, mensagens ao usuário e documentação em
português.** Os sufixos de camada (Repository, Service, Presenter) tornam a
direção das chamadas legível pelo nome: entrypoint -> service -> repository.

Nenhuma camada daqui chama sys.exit() nem escreve em stdout por conta própria.
Encerrar o processo é decisão dos entrypoints (ingest.py e ask.py), que são os
composition roots: montam as dependências concretas e traduzem exceção em
código de saída.
"""

from .exceptions import (
    EmptyCorpusException,
    EmptyIndexException,
    InvalidConfigurationException,
    NoExtractableTextException,
    RagException,
    ServiceUnavailableException,
)

__all__ = [
    "RagException",
    "InvalidConfigurationException",
    "ServiceUnavailableException",
    "EmptyCorpusException",
    "NoExtractableTextException",
    "EmptyIndexException",
]
