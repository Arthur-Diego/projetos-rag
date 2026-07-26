"""Indexação dos PDFs do corpus na coleção do Chroma.

    python ingest.py
    python ingest.py --chunk-size 200 --chunk-overlap 20

Faz duas coisas e só duas: adapta a linha de comando (controller) e monta as
dependências concretas (composition root). O caso de uso vive na
IngestionFacade, que não sabe que existe um terminal (ADR-007).
"""

import argparse
import sys

from rag import config
from rag.exceptions import RagException
from rag.facade.ingestion_facade import IngestionFacade
from rag.presenter.console_reporter import ConsoleReporter
from rag.repository.document_reader import PdfDocumentReader
from rag.repository.vector_repository import ChromaVectorRepository
from rag.service.chunking_service import RecursiveChunkingService
from rag.service.generation_service import create_embeddings
from rag.service.health_checker import HealthChecker


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Indexa os PDFs de pdfs/ no Chroma.")
    parser.add_argument("--chunk-size", type=int, default=1000,
                        help="caracteres por chunk (default: 1000)")
    parser.add_argument("--chunk-overlap", type=int, default=150,
                        help="caracteres repetidos entre chunks vizinhos (default: 150)")
    return parser.parse_args()


def build_facade(args: argparse.Namespace, properties: config.RagProperties) -> IngestionFacade:
    """Composition root: escolhe as implementações concretas e as injeta."""
    return IngestionFacade(
        reader=PdfDocumentReader(properties.pdf_dir),
        # Valida overlap < size na construção, antes de ler qualquer PDF.
        chunking=RecursiveChunkingService(args.chunk_size, args.chunk_overlap),
        repository=ChromaVectorRepository(
            host=properties.chroma_host,
            port=properties.chroma_port,
            collection=properties.collection,
            embeddings=create_embeddings(
                properties.embedding_model, properties.max_retries
            ),
        ),
        chunk_size=args.chunk_size,
        chunk_overlap=args.chunk_overlap,
    )


def main() -> int:
    reporter = ConsoleReporter()
    try:
        args = parse_args()
        properties = config.load()
        HealthChecker(properties).check()
        reporter.service_ok(properties.chroma_url)

        facade = build_facade(args, properties)
        for path in facade.files():
            reporter.reading(path)

        reporter.ingestion(facade.ingest(), properties.collection)
    except RagException as e:
        # Único ponto que decide encerrar o processo: as camadas levantam,
        # o entrypoint traduz para código de saída.
        reporter.failure(str(e))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
