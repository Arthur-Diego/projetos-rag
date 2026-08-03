"""Dublês da suíte.

Escopo de teste fixado em `docs/guidelines/README.md`: pytest com dublês, nada
tocando a API paga nem o `hi_res` real (lento demais para suíte). Estes são os
dublês que tornam isso possível — e cada um deles CONTA as invocações, porque
metade dos testes desta task não pergunta "o resultado está certo?" e sim
"quantas vezes isto foi chamado?". Idempotência e cache só são verificáveis
assim: um pipeline que repaga tudo devolve exatamente o mesmo resultado de um
pipeline que não repaga nada.
"""

from pathlib import Path
from typing import Any

from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models import SimpleChatModel
from langchain_core.messages import BaseMessage

from rag.domain.models import DocumentUnit, IndexMatch
from rag.exceptions import ServiceUnavailableException


class FakeDocstore:
    """Docstore em memória, no contrato do `DocstoreRepository`.

    `fail_on_count` simula docstore inacessível em disco (permissão, volume
    fora): `OSError`, e não a exceção de domínio, porque é exatamente o tipo
    cru que o `/health` precisa provar que traduz em `degraded`.
    """

    def __init__(self, fail_on_count: bool = False) -> None:
        self.units: dict[str, DocumentUnit] = {}
        self.puts = 0
        self.fail_on_count = fail_on_count

    def known(self, doc_ids: list[str]) -> set[str]:
        return {doc_id for doc_id in doc_ids if doc_id in self.units}

    def put(self, units: list[DocumentUnit]) -> None:
        self.puts += 1
        for unit in units:
            self.units[unit.doc_id] = unit

    def get(self, doc_ids: list[str]) -> dict[str, DocumentUnit]:
        return {
            doc_id: self.units[doc_id] for doc_id in doc_ids if doc_id in self.units
        }

    def count(self) -> int:
        if self.fail_on_count:
            raise OSError("falha injetada de I/O no docstore")
        return len(self.units)

    def reset(self) -> int:
        removed = len(self.units)
        self.units = {}
        return removed


class FakeVectors:
    """Índice em memória, no contrato do `VectorRepository`.

    `fail_on_add` existe para o T3.7: provar a ordem de gravação exige poder
    quebrar a segunda escrita e olhar o que sobrou da primeira.

    `matches` é a lista que `search` devolve, na ordem. Ela é escrita À MÃO
    pelos testes de consulta, e não derivada de `units`, porque o que a
    recuperação precisa dublar é o ÍNDICE — inclusive o estado em que ele aponta
    para um `doc_id` que o docstore não tem, que é a dessincronia do T4.2. Um
    dublê que só soubesse devolver o que o docstore contém tornaria o caso do
    hit órfão impossível de escrever.
    """

    def __init__(self, fail_on_add: bool = False, fail_on_count: bool = False) -> None:
        self.units: dict[str, DocumentUnit] = {}
        self.fail_on_add = fail_on_add
        self.fail_on_count = fail_on_count
        self.matches: list[IndexMatch] = []
        self.searches = 0

    def count(self) -> int:
        if self.fail_on_count:
            raise ServiceUnavailableException("falha injetada na contagem do índice")
        return len(self.units)

    def add(self, units: list[DocumentUnit]) -> None:
        if self.fail_on_add:
            raise ServiceUnavailableException("falha injetada na gravação vetorial")
        for unit in units:
            self.units[unit.doc_id] = unit

    def known(self, doc_ids: list[str]) -> set[str]:
        return {doc_id for doc_id in doc_ids if doc_id in self.units}

    def search(self, query: str, k: int) -> list[IndexMatch]:
        self.searches += 1
        return self.matches[:k]

    def reset(self) -> int:
        removed = len(self.units)
        self.units = {}
        self.matches = []
        return removed


class CountingGeneration:
    """Gerador dublê, no contrato do `GenerationService`.

    Conta as invocações e guarda o último prompt. As duas coisas são o que os
    testes desta task perguntam: o T4.3 quer saber se o gerador foi chamado
    (índice vazio não pode custar nada) e o T4.1 quer olhar o que foi para
    dentro do prompt.
    """

    def __init__(self, reply: str = "resposta gerada") -> None:
        self.calls = 0
        self.reply = reply
        self.prompt = ""

    def generate(self, prompt: str) -> str:
        self.calls += 1
        self.prompt = prompt
        return self.reply


class CountingChatModel(SimpleChatModel):
    """Modelo de chat dublê que conta as invocações.

    **É aqui que o dublê entra no resumo de tabelas, e não numa interface
    própria.** O ADR-006 rejeitou explicitamente um `Protocol` para o
    `TableSummaryService` — não há segunda implementação plausível que não seja
    "outro provedor de LLM". O ponto de substituição é o MODELO, que já chega
    atrás de uma interface do LangChain, e substituí-lo aqui tem um ganho a
    mais: o serviço real roda de verdade, com o prompt real e o `batch` real.

    A contagem é por PROMPT: `batch` invoca `_call` uma vez por entrada, então
    `calls` é exatamente "quantas tabelas foram resumidas" — a medida que os
    testes de idempotência precisam.
    """

    calls: int = 0

    @property
    def _llm_type(self) -> str:
        return "counting-fake"

    def _call(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> str:
        self.calls += 1
        # NÃO ecoa a entrada, de propósito: um dublê que devolvesse o HTML
        # recebido faria passar o teste que existe justamente para provar que o
        # índice recebe o resumo, e não a marcação.
        return f"resumo da tabela {self.calls}"


class CountingDescriptions:
    """Descritor de imagens dublê, no contrato do `ImageDescriptionService`."""

    def __init__(self) -> None:
        self.calls = 0
        self.described = 0
        self.tokens = 0

    def describe(self, figures: list[Path]) -> list[str]:
        self.calls += 1
        self.described += len(figures)
        self.tokens += 20 * len(figures)
        return [f"descrição de {figure.name}" for figure in figures]


class RecordingLog:
    """Log de estágio que guarda as linhas em vez de escrever."""

    def __init__(self) -> None:
        self.lines: list[str] = []

    def stage(self, message: str) -> None:
        self.lines.append(message)
