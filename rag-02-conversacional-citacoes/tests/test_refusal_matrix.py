"""A matriz de recusa. Critério de aceite 4 do PRD, o mais importante do projeto.

A pergunta que estes testes respondem: **a recusa sobrevive ao histórico?**

No Projeto 1 a recusa era um caso simples: pergunta fora do corpus, contexto
irrelevante, frase de escape. Aqui há dois agravantes que não existiam:

1. O histórico entra no prompt de resposta. É contexto extra que empurra o
   modelo a responder do que já sabe, em vez de recusar.
2. A reescrita pode transformar uma pergunta fora do corpus numa pergunta que
   PARECE pertencer a ele, e aí o sistema responde em vez de recusar.

Um RAG que recusa no turno 1 e cede no turno 3 não recusa: adia.

A matriz é turno (1, 2, 3) × dentro/fora do corpus × reescrita ligada/desligada.
"""

import pytest
from conftest import (
    FakeLLM,
    FakeVectorRepository,
    IN_CORPUS,
    OUT_OF_CORPUS,
    answer_with_citation,
    build_facade,
    conversation_with,
)

from rag.service.prompt_builder import ESCAPE_PHRASE

TURNS = [0, 1, 2]  # turnos anteriores; 0 = primeiro turno da conversa
CONDITIONAL = [False, True]


@pytest.mark.parametrize("previous_turns", TURNS)
@pytest.mark.parametrize("conditional", CONDITIONAL)
def test_recusa_fora_do_corpus_em_qualquer_turno(previous_turns, conditional):
    """Fora do corpus recusa no turno 1, 2 e 3, com e sem reescrita.

    Este é o teste que o projeto existe para ter.
    """
    llm = FakeLLM(answer=ESCAPE_PHRASE, rewrite="pergunta reescrita e autossuficiente")
    facade = build_facade(
        llm,
        FakeVectorRepository(list(OUT_OF_CORPUS)),
        conditional_rewrite=conditional,
    )

    answer = facade.ask("e nesse caso?", conversation_with(previous_turns))

    assert answer.refused is True
    assert answer.text == ESCAPE_PHRASE
    # Invariante 1 do FDD: recusa não cita. Uma recusa com citação transferiria
    # confiança que não foi conquistada.
    assert answer.citations == []
    assert answer.unresolved_labels == []


@pytest.mark.parametrize("previous_turns", TURNS)
@pytest.mark.parametrize("conditional", CONDITIONAL)
def test_responde_dentro_do_corpus_em_qualquer_turno(previous_turns, conditional):
    """O contraponto: dentro do corpus, responde e cita, em qualquer turno.

    Sem este par, um sistema que recusasse SEMPRE passaria no teste acima.
    """
    llm = FakeLLM(answer=answer_with_citation, rewrite="quantos dias posso vender?")
    facade = build_facade(
        llm,
        FakeVectorRepository(list(IN_CORPUS)),
        conditional_rewrite=conditional,
    )

    answer = facade.ask("e se eu vender dez?", conversation_with(previous_turns))

    assert answer.refused is False
    assert [c.label for c in answer.citations] == [1, 2]
    assert answer.citations[0].source == "clt.pdf"
    assert answer.citations[0].page == 47


def test_recusa_com_hits_nao_vazios():
    """Recusar não significa não ter recuperado nada.

    A busca sempre devolve k trechos, mesmo quando nenhum serve: não há limiar
    de distância, por decisão do HLD. A distância alta é a evidência de que a
    recuperação falhou, e ela precisa chegar ao cliente junto da recusa.
    """
    llm = FakeLLM(answer=ESCAPE_PHRASE)
    facade = build_facade(llm, FakeVectorRepository(list(OUT_OF_CORPUS)))

    answer = facade.ask("o que diz o código de defesa do consumidor?")

    assert answer.refused is True
    assert answer.hits != []
    assert answer.hits[0].distance > 0.9


def test_recusa_nao_gasta_parse_de_citacao():
    """Recusa curto-circuita o resolvedor.

    Se o modelo devolver a frase de escape COM um rótulo alucinado grudado, o
    rótulo não pode virar procedência de uma resposta que não existe.
    """
    llm = FakeLLM(answer=ESCAPE_PHRASE)
    facade = build_facade(llm, FakeVectorRepository(list(OUT_OF_CORPUS)))

    answer = facade.ask("pergunta qualquer")

    assert answer.refused is True
    assert answer.citations == []


def test_indice_sem_resultado_recusa_sem_chamar_o_modelo():
    """Busca sem retorno recusa antes da geração, e não gasta chamada."""
    llm = FakeLLM(answer=answer_with_citation)
    facade = build_facade(llm, FakeVectorRepository([]))

    answer = facade.ask("qualquer coisa")

    assert answer.refused is True
    assert answer.text == ESCAPE_PHRASE
    assert llm.answer_calls == 0


def test_a_query_buscada_e_a_reescrita_nunca_a_original():
    """Objetivo técnico 1 do FDD, verificado no ponto onde ele pode falhar.

    Se a facade passasse `question` em vez de `decision.used` ao retriever, tudo
    o mais continuaria funcionando: a resposta sairia, a citação resolveria, e o
    projeto inteiro estaria quebrado em silêncio.
    """
    repository = FakeVectorRepository(list(IN_CORPUS))
    llm = FakeLLM(
        answer=answer_with_citation,
        rewrite="Quantos dias de férias posso converter em abono pecuniário?",
    )
    facade = build_facade(llm, repository)

    facade.ask("e se eu vender dez?", conversation_with(1))

    assert repository.queries == [
        "Quantos dias de férias posso converter em abono pecuniário?"
    ]
