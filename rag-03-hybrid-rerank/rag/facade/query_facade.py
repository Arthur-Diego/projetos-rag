"""Caso de uso de consulta.

Esta camada **não conhece o ConsoleReporter, nem argparse, nem sys.stderr, nem
requisição HTTP**. Ela recebe uma pergunta e uma conversa e devolve um `Answer`.
É essa ausência que a torna chamável pelas quatro superfícies sem alteração.

**A conversa entra por parâmetro e não fica** (ADR-002). Não há dicionário de
sessão, cache nem `conversation_id`: o cliente é dono da transcrição. É o que
mantém esta facade sendo função dos seus argumentos, e é o que torna a matriz de
recusa do critério 4 trivial de testar, porque não há estado a preparar nem a
limpar entre casos.
"""

import time

from ..config import DEFAULT_HISTORY_WINDOW, MAX_HISTORY_WINDOW
from ..domain.models import (
    REASONS_WITHOUT_CALL,
    Answer,
    Citation,
    Conversation,
    RetrievalResult,
    RewriteDecision,
    SearchHit,
)
from ..exceptions import InvalidParameterException
from ..service.citation_resolver import CitationResolver
from ..service.generation_service import GenerationService
from ..service.prompt_builder import ESCAPE_PHRASE, PromptBuilder
from ..service.query_rewrite_service import QueryRewriteService
from ..service.retrieval_service import RetrievalService


class QueryFacade:
    """Orquestra reescrever -> recuperar -> numerar -> gerar -> resolver citação."""

    def __init__(
        self,
        rewrite: QueryRewriteService,
        retrieval: RetrievalService,
        prompts: PromptBuilder,
        generation: GenerationService,
        citations: CitationResolver,
        history_window: int = DEFAULT_HISTORY_WINDOW,
    ) -> None:
        if history_window < 0:
            raise InvalidParameterException(
                f"history_window não pode ser negativo (recebido: {history_window})."
            )
        if history_window > MAX_HISTORY_WINDOW:
            # O teto é o mesmo declarado em /capabilities. Declarar um limite e
            # não impô-lo transforma o descritor em sugestão, e o contrato diz
            # que ele descreve o backend, não uma intenção.
            raise InvalidParameterException(
                f"history_window deve ser <= {MAX_HISTORY_WINDOW} "
                f"(recebido: {history_window})."
            )
        self._rewrite = rewrite
        self._retrieval = retrieval
        self._prompts = prompts
        self._generation = generation
        self._citations = citations
        self.history_window = history_window

    @property
    def k(self) -> int:
        return self._retrieval.k

    def open_index(self, collection: str) -> int:
        """Confirma que há o que consultar e devolve quantos chunks existem.

        Raises:
            EmptyIndexException: se a coleção não existe ou está vazia.
        """
        return self._retrieval.require_index(collection)

    def ask(
        self,
        question: str,
        conversation: Conversation = Conversation(),
    ) -> Answer:
        """Responde a pergunta a partir do corpus, ciente da conversa.

        `conversation` tem default vazio de propósito: é o que permite ao
        `ask.py` de turno único chamar sem histórico, sem um caminho paralelo
        (ADR-006).
        """
        # A janela é aplicada AQUI, no servidor, e não no cliente (ADR-002).
        # É o que mantém o experimento do critério 6 do PRD controlável de um
        # lugar só, sem precisar tocar em dois clientes para variar o valor.
        windowed = conversation.last(self.history_window)

        t0 = time.perf_counter()
        decision = self._rewrite.decide(question, windowed)
        t1 = time.perf_counter()

        # Invariante 3 do FDD: rewrite_s vale 0.0 EXATAMENTE quando não houve
        # chamada. Zerar explicitamente, em vez de deixar o cronômetro devolver
        # 0.000004, é o que torna a invariante literalmente verdadeira e
        # verificável por igualdade em teste.
        rewrite_s = 0.0 if decision.reason in REASONS_WITHOUT_CALL else t1 - t0

        # ADR-007: a facade NÃO cronometra mais o interior deste estágio.
        #
        # Ela continua medindo `search_s`, que é o TOTAL da recuperação e mantém
        # exatamente o significado que sempre teve. O que ela não faz é fingir
        # saber quanto custou cada etapa lá dentro: com quatro delas, medir de
        # fora só produz um agregado, e o agregado não responde onde o tempo foi.
        #
        # A decomposição vem pelo RETORNO, medida por quem sabe o que aconteceu.
        # O canal lateral (o serviço guardar os tempos num atributo) foi recusado
        # no ADR-007: introduziria estado mutável, e duas requisições concorrentes
        # leriam o tempo uma da outra.
        #
        # A facade continua sem saber que a recuperação virou funil. Ela não
        # conhece caminho denso, BM25, fusão nem reordenação: recebe hits e
        # tempos, e repassa. É essa ignorância que faz a mudança caber aqui sem
        # a orquestração dela mudar.
        retrieval = self._retrieval.retrieve(decision.used)
        hits = retrieval.hits
        t2 = time.perf_counter()

        if not hits:
            # Índice não vazio mas busca sem retorno: caso raro, tratado como
            # ausência de contexto em vez de erro.
            return self._refusal(
                decision, rewrite_s, search_s=t2 - t1, retrieval=retrieval
            )

        # A decisão inteira, não `question`: o estágio de resposta precisa da
        # pergunta RESOLVIDA, senão o pronome que a reescrita acabou de resolver
        # volta a ser ambíguo e o modelo recusa apesar do contexto certo.
        # Defeito encontrado na validação; ver PromptBuilder.format_question.
        text = self._generation.generate(
            self._prompts.build(decision, hits, windowed)
        )
        t3 = time.perf_counter()

        refused = text.strip() == ESCAPE_PHRASE

        # Invariante 1 do FDD: recusa não cita. Curto-circuitar antes de parsear
        # não é otimização; é o que impede um [n] alucinado dentro de uma frase
        # de escape de virar procedência de uma resposta que não existe.
        citations: list[Citation] = []
        unresolved: list[int] = []
        if not refused:
            citations, unresolved = self._citations.resolve(text, hits)

        return Answer(
            text=text,
            hits=hits,
            citations=citations,
            unresolved_labels=unresolved,
            refused=refused,
            rewrite=decision,
            rewrite_s=rewrite_s,
            search_s=t2 - t1,
            generation_s=t3 - t2,
            dense_s=retrieval.dense_s,
            keyword_s=retrieval.keyword_s,
            fusion_s=retrieval.fusion_s,
            rerank_s=retrieval.rerank_s,
        )

    @staticmethod
    def _refusal(
        decision: RewriteDecision,
        rewrite_s: float,
        search_s: float,
        retrieval: RetrievalResult,
    ) -> Answer:
        """Recusa sem gastar geração, quando não há nem o que enviar ao modelo.

        Os tempos dos estágios que RODARAM continuam sendo reportados. Uma
        recusa por ausência de candidatos ainda custou uma busca densa, e
        possivelmente uma léxica e uma fusão; esconder esse custo faria a soma
        dos tempos não fechar justamente no caso que mais interessa diagnosticar.
        """
        empty: list[SearchHit] = []
        return Answer(
            text=ESCAPE_PHRASE,
            hits=empty,
            citations=[],
            unresolved_labels=[],
            refused=True,
            rewrite=decision,
            rewrite_s=rewrite_s,
            search_s=search_s,
            generation_s=0.0,
            dense_s=retrieval.dense_s,
            keyword_s=retrieval.keyword_s,
            fusion_s=retrieval.fusion_s,
            rerank_s=retrieval.rerank_s,
        )
