"""Indexação do corpus.

    python ingest.py                          # usa os defaults
    python ingest.py --chunk-size 400         # experimento de chunking

Faz duas coisas e só duas: adapta a linha de comando (controller) e monta as
dependências concretas (composition root). O caso de uso vive na
IngestionFacade, que não sabe que existe um terminal.

Lê `pdfs/*.pdf`, NÃO recursivo. `pdfs/fora-do-corpus/` fica de fora de
propósito: é o corpus de controle do teste negativo de grounding.
"""

import argparse
import sys

from composition import build_ingestion_facade
from rag import config
from rag.config import DEFAULT_CHUNK_OVERLAP, DEFAULT_CHUNK_SIZE
from rag.exceptions import RagException
from rag.presenter.console_reporter import ConsoleReporter
from rag.service.health_checker import HealthChecker


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Indexa os PDFs de pdfs/.")
    parser.add_argument(
        "--chunk-size", type=int, default=DEFAULT_CHUNK_SIZE,
        help=f"caracteres por pedaço (default: {DEFAULT_CHUNK_SIZE})",
    )
    parser.add_argument(
        "--chunk-overlap", type=int, default=DEFAULT_CHUNK_OVERLAP,
        help=f"caracteres repetidos entre pedaços (default: {DEFAULT_CHUNK_OVERLAP})",
    )
    return parser.parse_args()


def main() -> int:
    reporter = ConsoleReporter()
    try:
        args = parse_args()
        properties = config.load()
        HealthChecker(properties).check()

        facade = build_ingestion_facade(
            properties, args.chunk_size, args.chunk_overlap
        )

        # A listagem vem ANTES do trabalho: é onde um PDF do corpus de controle
        # indexado por engano aparece, em vez de ser descoberto quando o teste
        # negativo parar de falhar.
        reporter.files(facade.files())
        reporter.ingestion(facade.ingest())
    except RagException as e:
        reporter.failure(str(e))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
