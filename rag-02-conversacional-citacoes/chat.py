"""Conversa multi-turno com o corpus indexado.

    python chat.py
    python chat.py --k 8 --janela 2 --reescrita-condicional

O entrypoint que o Projeto 2 acrescenta (ADR-006). É um REPL, e **é ele quem
guarda a transcrição** (ADR-002): a conversa vive no cliente, e aqui o cliente
é este processo. Nada em `rag/` guarda conversa.

A cada turno imprime, em stderr, a decisão de reescrita e a query efetivamente
buscada. É o critério 2 do PRD: ver a pergunta ambígua virar uma pergunta
autossuficiente é metade do que este projeto ensina.

Comandos do laço:
    \\limpar   esquece a conversa e recomeça do turno 1
    \\q        sai (também Ctrl+D)
"""

import argparse
import sys

from composition import build_query_facade
from rag import config
from rag.config import DEFAULT_HISTORY_WINDOW, DEFAULT_K
from rag.domain.models import Conversation, Turn
from rag.exceptions import RagException
from rag.facade.query_facade import QueryFacade
from rag.presenter.console_reporter import ConsoleReporter
from rag.service.health_checker import HealthChecker

EXIT_COMMANDS = {"\\q", "sair", "quit", "exit"}
CLEAR_COMMANDS = {"\\limpar", "\\clear", "\\reset"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Conversa com o corpus indexado, com reescrita e citação."
    )
    parser.add_argument(
        "--k", type=int, default=DEFAULT_K,
        help=f"quantos trechos recuperar (default: {DEFAULT_K})",
    )
    parser.add_argument(
        "--janela", type=int, default=DEFAULT_HISTORY_WINDOW,
        help=(
            f"quantos turnos anteriores considerar (default: {DEFAULT_HISTORY_WINDOW}). "
            "0 desliga o histórico e faz cada turno agir como o ask.py"
        ),
    )
    parser.add_argument(
        "--reescrita-condicional", action="store_true",
        help=(
            "pula a reescrita quando a pergunta já parece autossuficiente. "
            "economiza uma chamada de LLM por turno, ao risco de não reescrever "
            "algo que precisava (critério 5 do PRD)"
        ),
    )
    return parser.parse_args()


def repl(facade: QueryFacade, reporter: ConsoleReporter) -> None:
    """Laço interativo. É o dono da transcrição.

    A `Conversation` é reatribuída a cada turno, nunca mutada: ela é objeto de
    valor (ADR-003), e manter isso visível aqui é o que impede a tentação de
    guardá-la no servidor mais adiante.
    """
    reporter.diagnostic(
        "conversa iniciada. para sair: \\q ou Ctrl+D. para esquecer o histórico: \\limpar"
    )
    conversation = Conversation()

    while True:
        try:
            reporter.diagnostic("")
            sys.stderr.write(f"[turno {len(conversation.turns) + 1}] > ")
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
        if entry.lower() in CLEAR_COMMANDS:
            conversation = Conversation()
            reporter.diagnostic("histórico esquecido. o próximo turno é o primeiro.")
            continue

        answer = facade.ask(entry, conversation)
        reporter.answer(answer)

        # Só o cliente acrescenta o turno. O servidor recebeu a conversa, usou
        # e esqueceu (ADR-002). Guardamos a resposta COM os [n]: o estágio de
        # reescrita lê a conversa, e os rótulos ajudam a resolver referências
        # do tipo "o artigo que você citou".
        conversation = Conversation(
            conversation.turns + (Turn(question=entry, answer=answer.text),)
        )


def main() -> int:
    reporter = ConsoleReporter()
    try:
        args = parse_args()
        properties = config.load()
        HealthChecker(properties).check()

        facade = build_query_facade(
            properties,
            k=args.k,
            history_window=args.janela,
            conditional_rewrite=args.reescrita_condicional,
        )
        total = facade.open_index(properties.collection)
        reporter.index_opened(
            properties.collection, total, facade.k, facade.history_window
        )
        if args.reescrita_condicional:
            reporter.diagnostic(
                "reescrita condicional LIGADA: turnos com pergunta autossuficiente "
                "não gastam chamada de reescrita"
            )

        repl(facade, reporter)
    except RagException as e:
        reporter.failure(str(e))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
