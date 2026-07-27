"""Consulta de turno único ao corpus indexado.

    python ask.py "sua pergunta"
    python ask.py "sua pergunta" --k 8

**Turno único, sem histórico, e sem REPL (ADR-006).** O `ask.py` do Projeto 1
tem um laço interativo; este não tem, de propósito. Quem conversa é o
`chat.py`.

Manter um comando que TERMINA não é conservadorismo, é requisito:

- o critério 4 do PRD é uma matriz (turnos 1/2/3 × dentro/fora do corpus × com
  e sem reescrita), e scriptá-la contra um comando que termina é uma linha de
  shell por caso;
- o critério 5 compara custo com e sem histórico, e comparar exige que o caso
  sem histórico exista como caminho de primeira classe.

stdout recebe APENAS a resposta. Reescrita, distâncias, latências e citações
vão para stderr, de modo que `python ask.py "..." > saida.txt` grave só a
resposta.
"""

import argparse
import sys

from composition import build_query_facade
from rag import config
from rag.config import DEFAULT_K
from rag.exceptions import RagException
from rag.presenter.console_reporter import ConsoleReporter
from rag.service.health_checker import HealthChecker


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Pergunta ao corpus indexado, em turno único e sem histórico."
    )
    parser.add_argument("pergunta", help="a pergunta, entre aspas")
    parser.add_argument(
        "--k", type=int, default=DEFAULT_K,
        help=f"quantos trechos recuperar (default: {DEFAULT_K})",
    )
    return parser.parse_args()


def main() -> int:
    reporter = ConsoleReporter()
    try:
        args = parse_args()
        properties = config.load()
        HealthChecker(properties).check()

        facade = build_query_facade(properties, k=args.k)
        total = facade.open_index(properties.collection)
        reporter.index_opened(
            properties.collection, total, facade.k, facade.history_window
        )

        # Sem conversa: a facade recebe o default vazio, e a decisão de
        # reescrita sai como `primeiro_turno`, sem gastar chamada de LLM.
        reporter.answer(facade.ask(args.pergunta))
    except RagException as e:
        reporter.failure(str(e))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
