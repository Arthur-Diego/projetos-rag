"""Dublês e fábricas para os testes.

**Nenhum teste deste projeto toca a API paga.** É condição, não conveniência: a
matriz de recusa do critério 4 do PRD tem dezenas de casos e roda a cada
mudança. Uma suíte que custa dinheiro deixa de ser rodada, e o que não é rodado
não protege nada.

Os dublês implementam os `Protocol` do projeto por conformidade estrutural, sem
herdar de nada. É o ganho do `typing.Protocol` sobre `ABC`, e o motivo de o
mypy ser obrigatório: nada verifica isso em tempo de execução.
"""

import sys
from pathlib import Path
from typing import Callable

import pytest

# O projeto não é instalado como pacote: os entrypoints vivem na raiz e importam
# `rag` diretamente. Os testes precisam da mesma raiz no path.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rag.domain.models import Chunk, Conversation, SearchHit, Turn  # noqa: E402
from rag.facade.query_facade import QueryFacade  # noqa: E402
from rag.service.citation_resolver import CitationResolver  # noqa: E402
from rag.service.prompt_builder import ESCAPE_PHRASE, PromptBuilder  # noqa: E402
from rag.service.query_rewrite_service import QueryRewriteService  # noqa: E402
from rag.service.retrieval_service import RetrievalService  # noqa: E402

# Marcadores que distinguem os dois prompts. Copiados do início de cada template
# de propósito: se um template mudar de abertura, o dublê passa a classificar
# errado e os testes falham alto, em vez de silenciosamente medirem outra coisa.
_ANSWER_MARKER = "Responda a pergunta usando SOMENTE"
_REWRITE_MARKER = "Dado o histórico da conversa"


class FakeLLM:
    """Gerador determinístico que distingue os dois estágios.

    O mesmo `GenerationService` serve reescrita e resposta no código real; o
    dublê precisa saber qual dos dois está respondendo, e conta cada um em
    separado. É essa contagem que torna o critério 5 do PRD verificável sem
    gastar um centavo.
    """

    def __init__(
        self,
        answer: str | Callable[[str], str] = ESCAPE_PHRASE,
        rewrite: str | Callable[[str], str] | Exception = "pergunta reescrita",
    ) -> None:
        self._answer = answer
        self._rewrite = rewrite
        self.answer_prompts: list[str] = []
        self.rewrite_prompts: list[str] = []

    @property
    def rewrite_calls(self) -> int:
        return len(self.rewrite_prompts)

    @property
    def answer_calls(self) -> int:
        return len(self.answer_prompts)

    @property
    def total_calls(self) -> int:
        return self.rewrite_calls + self.answer_calls

    def generate(self, prompt: str) -> str:
        if _REWRITE_MARKER in prompt:
            self.rewrite_prompts.append(prompt)
            if isinstance(self._rewrite, Exception):
                raise self._rewrite
            return self._rewrite(prompt) if callable(self._rewrite) else self._rewrite

        if _ANSWER_MARKER in prompt:
            self.answer_prompts.append(prompt)
            return self._answer(prompt) if callable(self._answer) else self._answer

        raise AssertionError(
            "prompt não reconhecido como reescrita nem como resposta. "
            "Algum template mudou de abertura sem atualizar os marcadores."
        )


class FakeVectorRepository:
    """Armazém em memória, com os trechos fixados pelo teste.

    `search` ignora a query e devolve sempre os mesmos trechos. É deliberado: o
    que estes testes verificam é o encanamento (a query CERTA foi buscada, a
    citação resolveu contra o trecho CERTO), não a qualidade da busca vetorial,
    que não é testável sem embeddings reais.

    A query recebida fica registrada em `queries`, e é sobre ela que se afirma
    que a reescrita chegou ao retriever.
    """

    def __init__(self, hits: list[SearchHit] | None = None) -> None:
        self._hits = hits if hits is not None else []
        self.queries: list[str] = []
        self.added: list[Chunk] = []
        self.recreated_with: list[int] = []

    def count(self) -> int:
        return len(self._hits)

    def vector_size(self) -> int | None:
        return 1536 if self._hits else None

    def recreate(self, dimensions: int) -> int:
        previous = len(self._hits)
        self.recreated_with.append(dimensions)
        self._hits = []
        return previous

    def add(self, chunks: list[Chunk]) -> None:
        self.added.extend(chunks)

    def search(self, query: str, k: int) -> list[SearchHit]:
        self.queries.append(query)
        return self._hits[:k]


# ---------------------------------------------------------------------------
# Corpora dos testes
# ---------------------------------------------------------------------------

#: Trechos do corpus INDEXADO. Texto normativo, com remissão cruzada, como o
#: PRD especifica.
IN_CORPUS = [
    SearchHit(
        text=(
            "Art. 143. É facultado ao empregado converter um terço do período de "
            "férias a que tiver direito em abono pecuniário."
        ),
        source="clt.pdf",
        page=47,
        distance=0.312,
    ),
    SearchHit(
        text=(
            "O abono de férias deverá ser requerido até 15 dias antes do término "
            "do período aquisitivo."
        ),
        source="clt.pdf",
        page=48,
        distance=0.401,
    ),
]

#: Trechos que a busca devolve quando a pergunta é sobre o CORPUS DE CONTROLE.
#: Distância alta: nada aqui sustenta a resposta, e é o incentivo máximo para o
#: modelo responder de memória.
OUT_OF_CORPUS = [
    SearchHit(
        text="Art. 2º Considera-se empregador a empresa, individual ou coletiva.",
        source="clt.pdf",
        page=12,
        distance=0.921,
    ),
]


def answer_with_citation(_: str) -> str:
    return (
        "A conversão é limitada a um terço do período [1], e deve ser requerida "
        "até 15 dias antes do término do período aquisitivo [2]."
    )


def build_facade(
    llm: FakeLLM,
    repository: FakeVectorRepository,
    k: int = 4,
    history_window: int = 6,
    conditional_rewrite: bool = False,
) -> QueryFacade:
    """Monta a facade com dublês, no mesmo formato do composition root real."""
    return QueryFacade(
        rewrite=QueryRewriteService(llm, conditional=conditional_rewrite),
        retrieval=RetrievalService(repository, k=k),
        prompts=PromptBuilder(),
        generation=llm,
        citations=CitationResolver(),
        history_window=history_window,
    )


def conversation_with(turns: int) -> Conversation:
    """Conversa sintética com N turnos já ocorridos."""
    return Conversation(
        tuple(
            Turn(
                question=f"pergunta anterior número {i}",
                answer=f"resposta anterior número {i} [1].",
            )
            for i in range(1, turns + 1)
        )
    )


@pytest.fixture
def in_corpus_repository() -> FakeVectorRepository:
    return FakeVectorRepository(list(IN_CORPUS))


@pytest.fixture
def out_of_corpus_repository() -> FakeVectorRepository:
    return FakeVectorRepository(list(OUT_OF_CORPUS))
