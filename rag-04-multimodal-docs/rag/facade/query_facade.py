"""Caso de uso da consulta.

Esta camada **não conhece o ConsoleReporter, nem argparse, nem requisição
HTTP**: recebe uma pergunta e devolve um `Answer`. É essa ausência que a torna
chamável pelo `ask.py` e pelo `POST /ask` sem uma linha de diferença.

**Pergunta única, sem histórico** (adr-002 da sessão): não há `conversation`,
nem reescrita, nem `conversation_id`. O objeto de estudo do rag-04 é a ingestão
multimodal e o multi-vector; histórico não exercitaria nada disso e dobraria a
superfície a validar.

Orquestra e não calcula: recuperar -> montar contexto -> gerar -> comparar com a
frase de escape. O diagnóstico por estágio sai pela porta `IngestionLog`, cujo
adaptador é o presenter — a facade não sabe se alguém está lendo (regra 2.2 da
guideline).
"""

import time

from ..domain.models import Answer, RetrievalResult, SearchHit
from ..service.generation_service import GenerationService
from ..service.ingestion_log import IngestionLog, NullIngestionLog
from ..service.prompt_builder import ESCAPE_PHRASE, PromptBuilder
from ..service.retrieval.retrieval_service import RetrievalService


class QueryFacade:
    """Orquestra recuperar -> montar o prompt -> gerar -> classificar recusa."""

    def __init__(
        self,
        retrieval: RetrievalService,
        prompts: PromptBuilder,
        generation: GenerationService,
        log: IngestionLog | None = None,
    ) -> None:
        self._retrieval = retrieval
        self._prompts = prompts
        self._generation = generation
        self._log = log or NullIngestionLog()

    @property
    def k(self) -> int:
        return self._retrieval.k

    def open_index(self, collection: str) -> int:
        """Confirma que há o que consultar e devolve quantas representações há.

        Chamado pelo entrypoint ANTES de `ask`, e é a razão de existir separado:
        índice vazio precisa custar zero chamada paga.

        Raises:
            EmptyIndexException: se a coleção não existe ou está vazia.
        """
        return self._retrieval.require_index(collection)

    def retrieve(self, question: str) -> RetrievalResult:
        """Só a recuperação, sem gerar — o caminho do `--sem-geracao` da medição.

        Existe como método PÚBLICO em vez de a medição alcançar o
        `RetrievalService` por dentro da facade: medir metade do pipeline é uso
        legítimo (a recuperação é o que o golden set cobra por âncora), e um
        consumidor que precisa furar o encapsulamento para isso denuncia que
        falta o método, não que o consumidor está errado.

        Custa uma embedagem da pergunta e nenhuma geração.
        """
        return self._retrieval.retrieve(question)

    def ask(self, question: str) -> Answer:
        """Responde a pergunta a partir do corpus multimodal.

        **`refused` é decidido AQUI**, comparando o texto com a frase de escape,
        e não no presenter: uma invariante que só existe na apresentação não vale
        em lugar nenhum, e o `ask.py` e a rota precisam da mesma verdade.
        """
        marker = time.perf_counter()
        retrieval = self._retrieval.retrieve(question)
        search_s = time.perf_counter() - marker

        if not retrieval.hits:
            # Índice não vazio e busca sem retorno aproveitável — inclusive o
            # caso em que TODOS os hits eram órfãos. Tratado como ausência de
            # contexto, e não como erro: a resposta honesta é a recusa, e ela
            # não custa uma geração.
            self._log.stage(
                "[geração] pulada: nenhum trecho resolvido, recusa direta "
                f"({retrieval.discarded} hit(s) órfão(s) descartado(s))"
            )
            return self._refusal(search_s, retrieval.docstore_s)

        marker = time.perf_counter()
        text = self._generation.generate(self._prompts.build(question, retrieval.hits))
        generation_s = time.perf_counter() - marker

        refused = text.strip() == ESCAPE_PHRASE
        if refused:
            self._log.stage("[geração] RECUSOU: o contexto não sustentava a resposta")

        return Answer(
            text=text,
            refused=refused,
            hits=retrieval.hits,
            timings={
                # `search_s` é o TOTAL do estágio de recuperação e mantém o
                # significado que tem nos projetos 1 a 3. `dense_s` e
                # `docstore_s` o DECOMPÕEM: quem somar os três conta a
                # recuperação duas vezes. A decomposição existe porque a
                # resolução dos originais é o estágio novo deste projeto, e sem
                # medi-la em separado o custo dele não seria atribuível.
                "search_s": search_s,
                "dense_s": retrieval.dense_s,
                "docstore_s": retrieval.docstore_s,
                "generation_s": generation_s,
            },
        )

    @staticmethod
    def _refusal(search_s: float, docstore_s: float) -> Answer:
        """Recusa sem gastar geração, quando não há o que enviar ao modelo.

        Os tempos dos estágios que RODARAM continuam sendo reportados: a busca
        aconteceu e custou uma embedagem. `generation_s` vale zero porque o
        estágio realmente não rodou, e é a única leitura honesta disso.
        """
        empty: tuple[SearchHit, ...] = ()
        return Answer(
            text=ESCAPE_PHRASE,
            refused=True,
            hits=empty,
            timings={
                "search_s": search_s,
                "dense_s": search_s - docstore_s,
                "docstore_s": docstore_s,
                "generation_s": 0.0,
            },
        )
