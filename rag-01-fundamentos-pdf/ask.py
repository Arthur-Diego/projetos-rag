"""Consulta ao corpus indexado.

    python ask.py                  # REPL, reaproveita cliente e coleção
    python ask.py "sua pergunta"   # resposta única
    python ask.py --k 8            # quantos chunks recuperar

Faz duas coisas e só duas: adapta a linha de comando (controller) e monta as
dependências concretas (composition root). O caso de uso vive na QueryFacade,
que não sabe que existe um terminal (ADR-007).

stdout recebe APENAS a resposta do modelo. Chunks, distâncias e latências vão
para stderr, de modo que `python ask.py "..." > saida.txt` grave só a resposta.
"""

import argparse
import sys

from rag import config
from rag.exceptions import InvalidConfigurationException, RagException
from rag.facade.query_facade import QueryFacade
from rag.presenter.console_reporter import ConsoleReporter
from rag.repository.vector_repository import ChromaVectorRepository
from rag.service.generation_service import OpenAiGenerationService, create_embeddings
from rag.service.health_checker import HealthChecker
from rag.service.prompt_builder import PromptBuilder
from rag.service.retrieval_service import RetrievalService

EXIT_COMMANDS = {"\\q", "sair", "quit", "exit"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Pergunta ao corpus indexado.")
    parser.add_argument("pergunta", nargs="?", help="sem ela, entra em modo REPL")
    parser.add_argument("--k", type=int, default=4,
                        help="quantos chunks recuperar (default: 4)")
    return parser.parse_args()


def build_facade(args: argparse.Namespace, properties: config.RagProperties) -> QueryFacade:
    """Composition root: escolhe as implementações concretas e as injeta."""
    repository = ChromaVectorRepository(
        host=properties.chroma_host,
        port=properties.chroma_port,
        collection=properties.collection,
        embeddings=create_embeddings(properties.embedding_model, properties.max_retries),
    )
    return QueryFacade(
        retrieval=RetrievalService(repository, k=args.k),
        prompts=PromptBuilder(),
        generation=OpenAiGenerationService(
            properties.chat_model, properties.temperature, properties.max_retries
        ),
    )


def repl(facade: QueryFacade, reporter: ConsoleReporter) -> None:
    """Laço interativo. Reaproveita cliente e coleção já abertos."""
    reporter.diagnostic("modo REPL. para sair: \\q, sair, ou Ctrl+D")
    while True:
        try:
            reporter.diagnostic("")
            sys.stderr.write("> ")
            sys.stderr.flush()
            entry = input().strip()
        except (EOFError, KeyboardInterrupt):
            # Encerrar é uso normal, não falha: código 0 e sem traceback.
            reporter.diagnostic("")
            return

        if not entry:
            continue
        if entry.lower() in EXIT_COMMANDS:
            return

        reporter.answer(facade.ask(entry))


def main() -> int:
    reporter = ConsoleReporter()
    try:
        args = parse_args()
        if args.k < 1:
            raise InvalidConfigurationException(f"--k deve ser >= 1 (recebido: {args.k}).")

        properties = config.load()
        HealthChecker(properties).check()

        facade = build_facade(args, properties)
        total = facade.open_index(properties.collection)
        reporter.index_opened(properties.collection, total, facade.k)

        if args.pergunta:
            reporter.answer(facade.ask(args.pergunta))
        else:
            repl(facade, reporter)
    except RagException as e:
        reporter.failure(str(e))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
