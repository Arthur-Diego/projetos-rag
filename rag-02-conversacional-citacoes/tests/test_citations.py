"""Resolução das citações. Critério 3 do PRD e ADR-004.

O teste mais importante deste arquivo é
`test_reordenar_hits_depois_nao_muda_as_citacoes`: ele é a forma executável do
ADR-004. Sem ele, a decisão de resolver por referência explícita seria uma
intenção, e a implementação poderia deslizar de volta para o acoplamento
posicional sem que nada acusasse.
"""

from conftest import (
    FakeLLM,
    FakeVectorRepository,
    IN_CORPUS,
    build_facade,
)

from rag.domain.models import SearchHit
from rag.service.citation_resolver import CitationResolver
from rag.service.prompt_builder import PromptBuilder

HITS = [
    SearchHit(text="primeiro trecho", source="clt.pdf", page=47, distance=0.1),
    SearchHit(text="segundo trecho", source="clt.pdf", page=48, distance=0.2),
    SearchHit(text="terceiro trecho", source="clt.pdf", page=49, distance=0.3),
]


def test_resolve_rotulos_presentes():
    resolved, unresolved = CitationResolver().resolve(
        "Afirmação um [1]. Afirmação dois [3].", HITS
    )

    assert [c.label for c in resolved] == [1, 3]
    assert [c.page for c in resolved] == [47, 49]
    assert resolved[0].excerpt == "primeiro trecho"
    assert unresolved == []


def test_deduplica_preservando_a_ordem_de_primeira_aparicao():
    """Uma resposta que cita [1] três vezes tem uma citação, não três."""
    resolved, _ = CitationResolver().resolve("[2] a [1] b [2] c [1]", HITS)

    assert [c.label for c in resolved] == [2, 1]


def test_rotulo_inexistente_e_sinalizado_nunca_engolido():
    """Modelo citou [7] com três trechos. Não vira citação, e aparece."""
    resolved, unresolved = CitationResolver().resolve("Afirmação [7].", HITS)

    assert resolved == []
    assert unresolved == [7]


def test_rotulo_zero_e_invalido():
    """A numeração é 1-based; [0] não existe em nenhum contexto."""
    resolved, unresolved = CitationResolver().resolve("Afirmação [0].", HITS)

    assert resolved == []
    assert unresolved == [0]


def test_texto_sem_citacao_nao_e_erro():
    """Modelo pode responder sem citar.

    Detectar afirmação sem procedência é avaliação, e avaliação entra no
    Projeto 3. O que este projeto garante é que o que FOR citado resolve.
    """
    resolved, unresolved = CitationResolver().resolve("Uma resposta sem rótulos.", HITS)

    assert resolved == []
    assert unresolved == []


def test_reordenar_hits_depois_nao_muda_as_citacoes():
    """**ADR-004, na forma executável.**

    Se a resolução dependesse da posição em `hits`, reordenar a lista depois
    faria `[1]` apontar para outro trecho. As citações são materializadas antes
    de qualquer transformação de apresentação, então elas não se mexem.
    """
    hits = list(HITS)
    resolved, _ = CitationResolver().resolve("[1] e [3]", hits)

    paginas_antes = [c.page for c in resolved]

    hits.reverse()
    hits.append(SearchHit(text="intruso", source="outro.pdf", page=1, distance=0.9))

    assert [c.page for c in resolved] == paginas_antes
    assert [c.page for c in resolved] == [47, 49]
    assert all(c.source == "clt.pdf" for c in resolved)


def test_numeracao_do_prompt_bate_com_a_resolucao():
    """A mesma numeração dos dois lados. É a invariante 5 do FDD.

    O `PromptBuilder` numera de 1 a k e o `CitationResolver` resolve contra a
    mesma lista. Se um deles mudasse a base, a citação passaria a apontar para
    o vizinho, silenciosamente.
    """
    contexto = PromptBuilder.format_context(HITS)

    assert "[1] (fonte: clt.pdf, página 47)" in contexto
    assert "[2] (fonte: clt.pdf, página 48)" in contexto
    assert "[3] (fonte: clt.pdf, página 49)" in contexto

    resolved, _ = CitationResolver().resolve("[2]", HITS)
    assert resolved[0].page == 48


def test_facade_expoe_rotulos_nao_resolvidos():
    """Ponta a ponta: o rótulo alucinado chega ao chamador."""
    llm = FakeLLM(answer="Afirmação com fonte inventada [9].")
    facade = build_facade(llm, FakeVectorRepository(list(IN_CORPUS)))

    answer = facade.ask("qualquer pergunta")

    assert answer.refused is False
    assert answer.citations == []
    assert answer.unresolved_labels == [9]


def test_json_presenter_omite_campos_vazios_nunca_emite_null():
    """Garantia de compatibilidade do ADR-005.

    Um cliente do contrato 1.0.0 não pode receber chave que não conhece com
    valor nulo e ter que distinguir "ausente" de "vazio".
    """
    from rag.presenter.json_presenter import JsonPresenter

    llm = FakeLLM(answer="Resposta sem citação nenhuma.")
    facade = build_facade(llm, FakeVectorRepository(list(IN_CORPUS)))

    body = JsonPresenter().answer(facade.ask("qualquer pergunta"))

    assert "citations" not in body
    assert "meta" not in body
    # Os que este backend promete sempre (invariantes 2 e 3 do FDD).
    assert body["rewritten_question"]["reason"] == "primeiro_turno"
    assert body["timings"]["rewrite_s"] == 0.0
