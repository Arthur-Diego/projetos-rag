"""Consulta ao corpus multimodal: busca densa -> originais -> geração.

    .venv/bin/python ask.py "Qual foi a receita no 3T24?"
    .venv/bin/python ask.py "Qual foi a receita no 3T24?" --k 8

Faz duas coisas, e só duas (regra 2.6 da guideline): adapta o mundo externo
(argumentos e configuração) e monta o grafo pelo `composition.py`, delegando à
facade. Nenhuma lógica de RAG aqui.

**Pergunta única, sem REPL e sem histórico** (adr-002 da sessão). Um comando que
TERMINA é requisito, não conservadorismo: validar a pergunta-critério e o
controle negativo do BCB vira uma linha de shell por caso.

stdout recebe APENAS a resposta. Fontes, tipos, tamanho do contexto e tempos vão
para stderr, de modo que `ask.py "..." > resposta.txt` grave só a resposta e
`2> consulta.log` guarde a evidência de que a tabela em HTML chegou ao prompt.
"""

import argparse
import sys

from composition import build_chroma_client, build_query_facade
from rag import config
from rag.config import DEFAULT_K
from rag.exceptions import RagException
from rag.presenter.console_reporter import ConsoleReporter


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Pergunta ao corpus multimodal indexado, em turno único."
    )
    parser.add_argument("pergunta", help="a pergunta, entre aspas")
    parser.add_argument(
        "--k",
        type=int,
        default=DEFAULT_K,
        help=(
            f"quantos trechos recuperar, de 1 a 20 (padrão: {DEFAULT_K}). "
            "Uma tabela entra no prompt em HTML íntegro: valor alto custa caro."
        ),
    )
    return parser.parse_args()


def main() -> int:
    """Devolve código de saída; quem encerra o processo é o bloco `__main__`.

    Só `RagException` é tratada: é a hierarquia dos erros PREVISTOS, e cada uma
    já carrega a receita na mensagem. Qualquer outra sobe com o traceback
    inteiro, porque aí o defeito é deste código.
    """
    reporter = ConsoleReporter()

    try:
        args = parse_args()
        properties = config.load()

        facade = build_query_facade(
            properties, build_chroma_client(properties), reporter, k=args.k
        )
        # Índice vazio para aqui, antes da embedagem da pergunta.
        total = facade.open_index(properties.collection)
        reporter.index_opened(properties.collection, total, facade.k)

        reporter.answer(facade.ask(args.pergunta))
    except RagException as e:
        reporter.failure(str(e))
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
