"""A decisão de reescrita: quando gasta LLM, quando não, e por quê.

Cobre o conjunto fechado de `reason` (contrato 6 do FDD), a heurística léxica,
a precedência entre gatilhos, a janela de histórico e o fallback de falha.

O `reason` ser enumerado é o que torna o critério 5 do PRD agregável, e é por
isso que ele é testado valor a valor em vez de "existe alguma explicação".
"""

import pytest
from conftest import (
    FakeLLM,
    FakeVectorRepository,
    IN_CORPUS,
    answer_with_citation,
    build_facade,
    conversation_with,
)

from rag.domain.models import (
    REASON_ANAPHORIC_MARKER,
    REASON_FIRST_TURN,
    REASON_HISTORY_PRESENT,
    REASON_REWRITE_FAILED,
    REASON_SELF_CONTAINED,
    REASON_SHORT_QUESTION,
    REASONS_WITHOUT_CALL,
    Conversation,
)
from rag.service.query_rewrite_service import QueryRewriteService


def decide(question, conversation, conditional=False, rewrite="reescrita"):
    llm = FakeLLM(rewrite=rewrite)
    service = QueryRewriteService(llm, conditional=conditional)
    return service.decide(question, conversation), llm


def test_primeiro_turno_nao_gasta_chamada():
    decision, llm = decide("Quantos dias de férias eu tenho?", Conversation())

    assert decision.reason == REASON_FIRST_TURN
    assert decision.rewritten is False
    assert decision.used == "Quantos dias de férias eu tenho?"
    assert llm.rewrite_calls == 0


def test_com_historico_e_condicional_desligada_sempre_reescreve():
    decision, llm = decide(
        "uma pergunta razoavelmente longa e completamente autossuficiente aqui",
        conversation_with(1),
        conditional=False,
    )

    assert decision.reason == REASON_HISTORY_PRESENT
    assert decision.rewritten is True
    assert llm.rewrite_calls == 1


def test_condicional_pula_pergunta_autossuficiente():
    """O caso que economiza dinheiro, e o modo de falha do critério 5."""
    decision, llm = decide(
        "qual prazo o empregador precisa observar para conceder as férias anuais",
        conversation_with(1),
        conditional=True,
    )

    assert decision.reason == REASON_SELF_CONTAINED
    assert decision.rewritten is False
    assert llm.rewrite_calls == 0


@pytest.mark.parametrize(
    "question",
    [
        "e se eu vender dez?",
        "e nesse caso?",
        "quantos dias?",
    ],
)
def test_condicional_reescreve_pergunta_curta(question):
    decision, llm = decide(question, conversation_with(1), conditional=True)

    assert decision.reason == REASON_SHORT_QUESTION
    assert llm.rewrite_calls == 1


@pytest.mark.parametrize(
    "question",
    [
        "o mesmo vale para o empregado que trabalha em regime de tempo parcial?",
        "isso se aplica também ao contrato de experiência firmado por escrito?",
        "mas o prazo continua sendo contado da mesma forma nessa hipótese aqui?",
    ],
)
def test_condicional_reescreve_por_marcador_anaforico(question):
    decision, llm = decide(question, conversation_with(1), conditional=True)

    assert decision.reason == REASON_ANAPHORIC_MARKER
    assert llm.rewrite_calls == 1


def test_precedencia_comprimento_vence_marcador():
    """"E se eu vender dez?" dispara comprimento E conjunção inicial.

    O FDD fixa a precedência: vence o comprimento. Sem regra, o `reason` seria
    não determinístico e o critério 5 deixaria de agregar.
    """
    decision, _ = decide("e se eu vender dez?", conversation_with(1), conditional=True)

    assert decision.reason == REASON_SHORT_QUESTION


def test_marcador_nao_casa_substring():
    """`essencial` não pode disparar `esse`.

    A heurística tokeniza por palavra inteira. Sem isso, quase toda pergunta
    conteria algum marcador e a reescrita condicional não economizaria nada.
    """
    decision, llm = decide(
        "qual documento essencial comprova o vinculo empregaticio do trabalhador",
        conversation_with(1),
        conditional=True,
    )

    assert decision.reason == REASON_SELF_CONTAINED
    assert llm.rewrite_calls == 0


def test_falha_de_reescrita_cai_para_a_original_e_marca():
    """O único fallback do fluxo, e ele é visível.

    Cair para a pergunta original devolve o comportamento do Projeto 1. Isso é
    aceitável; o inaceitável seria acontecer em silêncio.
    """
    decision, llm = decide(
        "e nesse caso?",
        conversation_with(1),
        rewrite=TimeoutError("a OpenAI não respondeu"),
    )

    assert decision.reason == REASON_REWRITE_FAILED
    assert decision.rewritten is False
    assert decision.used == "e nesse caso?"
    assert llm.rewrite_calls == 1


def test_falha_de_reescrita_nao_derruba_a_consulta():
    llm = FakeLLM(
        answer=answer_with_citation, rewrite=TimeoutError("a OpenAI não respondeu")
    )
    facade = build_facade(llm, FakeVectorRepository(list(IN_CORPUS)))

    answer = facade.ask("e nesse caso?", conversation_with(1))

    assert answer.refused is False
    assert answer.rewrite.reason == REASON_REWRITE_FAILED
    assert llm.answer_calls == 1


def test_aspas_do_modelo_nao_entram_na_query():
    """O modelo às vezes devolve entre aspas apesar da instrução.

    A aspa entraria no vetor de busca e deslocaria o embedding.
    """
    decision, _ = decide(
        "e nesse caso?", conversation_with(1), rewrite='"Quantos dias posso vender?"'
    )

    assert decision.used == "Quantos dias posso vender?"


def test_reescrita_vazia_e_tratada_como_falha():
    decision, _ = decide("e nesse caso?", conversation_with(1), rewrite="   ")

    assert decision.reason == REASON_REWRITE_FAILED
    assert decision.used == "e nesse caso?"


# ---------------------------------------------------------------------------
# Janela de histórico
# ---------------------------------------------------------------------------


def test_janela_trunca_o_que_chega_ao_prompt_de_reescrita():
    """A janela é aplicada no SERVIDOR (ADR-002), sobre o que o cliente mandou."""
    llm = FakeLLM(answer=answer_with_citation, rewrite="reescrita")
    facade = build_facade(
        llm, FakeVectorRepository(list(IN_CORPUS)), history_window=2
    )

    facade.ask("e nesse caso?", conversation_with(10))

    prompt = llm.rewrite_prompts[0]
    assert "pergunta anterior número 10" in prompt
    assert "pergunta anterior número 9" in prompt
    assert "pergunta anterior número 8" not in prompt


def test_janela_zero_equivale_a_primeiro_turno():
    """Caso válido, não erro: é como se desliga o histórico.

    É o lado "sem histórico" da comparação do critério 5, sem precisar de outro
    parâmetro.
    """
    llm = FakeLLM(answer=answer_with_citation)
    facade = build_facade(
        llm, FakeVectorRepository(list(IN_CORPUS)), history_window=0
    )

    answer = facade.ask("e nesse caso?", conversation_with(5))

    assert answer.rewrite.reason == REASON_FIRST_TURN
    assert llm.rewrite_calls == 0


# ---------------------------------------------------------------------------
# Invariantes de tempo e custo
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "conditional,question,previous,expected_reason",
    [
        (False, "e nesse caso?", 0, REASON_FIRST_TURN),
        (True, "e nesse caso?", 0, REASON_FIRST_TURN),
        (
            True,
            "qual prazo o empregador precisa observar para conceder as férias anuais",
            1,
            REASON_SELF_CONTAINED,
        ),
    ],
)
def test_rewrite_s_e_exatamente_zero_quando_nao_houve_chamada(
    conditional, question, previous, expected_reason
):
    """Invariante 3 do FDD, na forma "se e somente se", lado do "se".

    Zero EXATO, não aproximadamente zero: a facade zera explicitamente em vez de
    deixar o cronômetro devolver 0.000004, e é isso que permite afirmar a
    invariante por igualdade.
    """
    llm = FakeLLM(answer=answer_with_citation)
    facade = build_facade(
        llm, FakeVectorRepository(list(IN_CORPUS)), conditional_rewrite=conditional
    )

    answer = facade.ask(question, conversation_with(previous))

    assert answer.rewrite.reason == expected_reason
    assert answer.rewrite.reason in REASONS_WITHOUT_CALL
    assert answer.rewrite_s == 0.0


def test_rewrite_s_maior_que_zero_quando_houve_chamada():
    """O outro lado do "se e somente se"."""
    llm = FakeLLM(answer=answer_with_citation, rewrite="reescrita")
    facade = build_facade(llm, FakeVectorRepository(list(IN_CORPUS)))

    answer = facade.ask("e nesse caso?", conversation_with(1))

    assert answer.rewrite.reason not in REASONS_WITHOUT_CALL
    assert answer.rewrite_s > 0.0


def test_custo_da_reescrita_condicional_e_mensuravel():
    """Critério 5 do PRD: quantas chamadas a condicional evita, numa conversa.

    Este teste é a forma executável da medição. Ele não afirma um número de
    economia (depende das perguntas), afirma que a economia é CONTÁVEL, que é o
    que faltaria se `reason` fosse texto livre.
    """
    perguntas = [
        "qual prazo o empregador precisa observar para conceder as férias anuais",
        "e nesse caso?",
        "qual documento essencial comprova o vinculo empregaticio do trabalhador",
    ]

    def rodar(conditional: bool) -> int:
        llm = FakeLLM(answer=answer_with_citation, rewrite="reescrita")
        facade = build_facade(
            llm, FakeVectorRepository(list(IN_CORPUS)), conditional_rewrite=conditional
        )
        conversation = conversation_with(1)
        for pergunta in perguntas:
            facade.ask(pergunta, conversation)
        return llm.rewrite_calls

    sempre = rodar(conditional=False)
    condicional = rodar(conditional=True)

    assert sempre == 3
    assert condicional == 1  # só "e nesse caso?" dispara
    assert sempre - condicional == 2
