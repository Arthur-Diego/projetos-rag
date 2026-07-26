"""Caso de uso de consulta.

Esta camada **não conhece o ConsoleReporter, nem argparse, nem sys.stderr**.
Ela recebe uma pergunta e devolve um Answer. É essa ausência que a torna
chamável por uma CLI hoje e por uma API HTTP ou um servidor MCP depois, sem
alteração.

Se um dia aparecer um `print` aqui dentro, a extração terá sido em vão.
"""

import time

from ..domain.models import Answer
from ..service.generation_service import GenerationService
from ..service.prompt_builder import ESCAPE_PHRASE, PromptBuilder
from ..service.retrieval_service import RetrievalService


class QueryFacade:
    """Orquestra retrieve -> augment -> generate."""

    def __init__(
        self,
        retrieval: RetrievalService,
        prompts: PromptBuilder,
        generation: GenerationService,
    ) -> None:
        self._retrieval = retrieval
        self._prompts = prompts
        self._generation = generation

    @property
    def k(self) -> int:
        return self._retrieval.k

    def open_index(self, collection: str) -> int:
        """Confirma que há o que consultar e devolve quantos chunks existem.

        Raises:
            EmptyIndexException: se a coleção não existe ou está vazia.
        """
        return self._retrieval.require_index(collection)

    def ask(self, question: str) -> Answer:
        """Responde a pergunta a partir do corpus indexado.

        A busca sempre devolve k chunks, mesmo quando todos são ruins: não há
        limiar, por decisão registrada no HLD. Quem pode recusar é o prompt, e
        só depois da geração.
        """
        t0 = time.perf_counter()
        hits = self._retrieval.retrieve(question)
        t1 = time.perf_counter()

        if not hits:
            # Índice não vazio mas busca sem retorno: caso raro, tratado como
            # ausência de contexto em vez de erro.
            return Answer(text=ESCAPE_PHRASE, hits=[], search_s=t1 - t0, generation_s=0.0)

        text = self._generation.generate(self._prompts.build(question, hits))
        t2 = time.perf_counter()

        return Answer(text=text, hits=hits, search_s=t1 - t0, generation_s=t2 - t1)
