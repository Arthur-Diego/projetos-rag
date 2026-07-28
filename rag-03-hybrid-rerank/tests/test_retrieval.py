"""Testes do funil de recuperação.

Cobrem os critérios de aceite 4, 5 e 6 da seção 9 do FDD: a reordenação manda na
ordem, o corte é respeitado, e os tempos por estágio são honestos sobre o que
rodou.

Nenhum toca Elasticsearch nem API paga. Os dublês vivem no conftest.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest  # noqa: E402
from conftest import (  # noqa: E402
    FakeKeywordRepository,
    FakeVectorRepository,
    InvertingReranker,
    PassThroughReranker,
)

from rag.domain.models import SearchHit  # noqa: E402
from rag.exceptions import InvalidParameterException  # noqa: E402
from rag.service.retrieval.fusion_service import FusionService  # noqa: E402
from rag.service.retrieval.retrieval_service import RetrievalService  # noqa: E402


def hit(doc_id: str, page: int = 1) -> SearchHit:
    return SearchHit(
        text=f"texto de {doc_id}",
        source="harry-potter.pdf",
        page=page,
        doc_id=doc_id,
        distance=0.5,
    )


def build(
    dense: list[SearchHit] | None = None,
    keyword: list[SearchHit] | None = None,
    reranker=None,
    **kwargs,
) -> RetrievalService:
    return RetrievalService(
        FakeVectorRepository(dense if dense is not None else [hit("a")]),
        keywords=FakeKeywordRepository(keyword or []),
        fusion=FusionService(),
        reranker=reranker or PassThroughReranker(),
        **kwargs,
    )


# ---------------------------------------------------------------------------
# Critério 4: a reordenação manda na ordem final
# ---------------------------------------------------------------------------


def test_a_ordem_final_vem_do_reordenador_nao_da_entrada():
    """Com um reordenador que inverte, a saída sai invertida.

    Um reordenador que apenas repassasse passaria despercebido com qualquer
    dublê realista. Inverter é o que torna o critério verificável.
    """
    servico = build(
        dense=[hit("primeiro"), hit("segundo"), hit("terceiro")],
        reranker=InvertingReranker(),
        k=3,
        rerank=True,
    )

    resultado = servico.retrieve("qualquer")

    assert [h.doc_id for h in resultado.hits] == ["terceiro", "segundo", "primeiro"]


def test_sem_rerank_a_ordem_e_a_da_fusao():
    servico = build(
        dense=[hit("primeiro"), hit("segundo")],
        reranker=InvertingReranker(),
        k=2,
        rerank=False,
    )

    resultado = servico.retrieve("qualquer")

    assert [h.doc_id for h in resultado.hits] == ["primeiro", "segundo"]


def test_o_reordenador_preserva_a_procedencia_da_fusao():
    """Jogar fora as posições apagaria o dado que explica por que o trecho subiu."""
    servico = build(
        dense=[hit("comum")],
        keyword=[hit("comum")],
        k=1,
        rerank=True,
    )

    resultado = servico.retrieve("qualquer")

    provenance = resultado.hits[0].provenance
    assert provenance is not None
    assert set(provenance.paths) == {"densa", "bm25"}
    assert provenance.rrf_score is not None


# ---------------------------------------------------------------------------
# Critério 5: corte e faixas
# ---------------------------------------------------------------------------


def test_corta_em_k():
    servico = build(dense=[hit(f"d{i}") for i in range(10)], k=3, rerank=True)

    assert len(servico.retrieve("qualquer").hits) == 3


def test_menos_candidatos_que_k_devolve_o_que_ha_sem_erro():
    servico = build(dense=[hit("unico")], k=4, candidates=4, rerank=True)

    assert len(servico.retrieve("qualquer").hits) == 1


def test_k_maior_que_candidates_e_recusado():
    """Contradição de configuração, não valor fora de faixa.

    Cortar para `candidates` em silêncio esconderia um erro de quem chamou.
    """
    with pytest.raises(InvalidParameterException, match="não pode ser maior"):
        build(k=10, candidates=5)


@pytest.mark.parametrize(
    "kwargs, trecho",
    [
        ({"k": 0}, "k deve ser >= 1"),
        ({"k": 21, "candidates": 30}, "k deve ser <="),
        ({"candidates": 0}, "candidates deve ser >= 1"),
        ({"candidates": 51}, "candidates deve ser <="),
        ({"rrf_k": 0}, "rrf_k deve ser >= 1"),
        ({"rrf_k": 1001}, "rrf_k deve ser <="),
    ],
)
def test_faixas_sao_impostas_na_construcao(kwargs, trecho):
    """Declarar um limite em /capabilities e não impô-lo torna o descritor sugestão."""
    with pytest.raises(InvalidParameterException, match=trecho):
        build(**kwargs)


def test_candidates_nao_reaproveita_o_teto_de_k():
    """São grandezas de ordens diferentes, e o teste fixa isso.

    `k` no máximo é 20, porque acima disso o contexto dilui. `candidates` chega a
    50, porque 20 é o ponto de partida do funil e não o teto. Reaproveitar um
    teto só obrigaria a escolher entre limitar o funil e permitir uma janela de
    contexto absurda.
    """
    servico = build(k=4, candidates=50)
    assert servico.candidates == 50


# ---------------------------------------------------------------------------
# Critério 6: timings honestos
# ---------------------------------------------------------------------------


def test_com_tudo_ligado_os_quatro_tempos_estao_presentes():
    resultado = build(hybrid=True, rerank=True).retrieve("qualquer")

    assert resultado.dense_s is not None
    assert resultado.keyword_s is not None
    assert resultado.fusion_s is not None
    assert resultado.rerank_s is not None


def test_sem_hibrida_o_tempo_do_bm25_fica_AUSENTE_nao_zero():
    """Zero significaria "rodou e foi instantâneo", que é outra afirmação."""
    resultado = build(hybrid=False, rerank=True).retrieve("qualquer")

    assert resultado.keyword_s is None
    assert resultado.dense_s is not None


def test_sem_rerank_o_tempo_do_rerank_fica_AUSENTE_nao_zero():
    resultado = build(hybrid=True, rerank=False).retrieve("qualquer")

    assert resultado.rerank_s is None
    assert resultado.fusion_s is not None


def test_o_caminho_denso_sempre_executa():
    """Não existe `densa=False`: o diagnóstico só-BM25 não é parâmetro público."""
    repositorio = FakeVectorRepository([hit("a")])
    servico = RetrievalService(
        repositorio,
        keywords=FakeKeywordRepository(),
        fusion=FusionService(),
        reranker=PassThroughReranker(),
        hybrid=False,
    )

    servico.retrieve("pergunta")

    assert repositorio.queries == ["pergunta"]


def test_sem_hibrida_o_bm25_nem_e_consultado():
    keywords = FakeKeywordRepository([hit("lexico")])
    servico = RetrievalService(
        FakeVectorRepository([hit("denso")]),
        keywords=keywords,
        fusion=FusionService(),
        reranker=PassThroughReranker(),
        hybrid=False,
    )

    servico.retrieve("pergunta")

    assert keywords.queries == []


# ---------------------------------------------------------------------------
# Diagnóstico do critério 8
# ---------------------------------------------------------------------------


def test_keyword_only_consulta_apenas_o_caminho_lexico():
    """O comando que impede a conclusão do projeto de ser falsa.

    Se o mapping estiver errado, o BM25 devolve vazio em silêncio. Sem um jeito
    de interrogá-lo sozinho, a tabela mostraria "a híbrida não ajudou" quando a
    verdade seria que ela nunca rodou.
    """
    denso = FakeVectorRepository([hit("denso")])
    keywords = FakeKeywordRepository([hit("lexico")])
    servico = RetrievalService(
        denso,
        keywords=keywords,
        fusion=FusionService(),
        reranker=PassThroughReranker(),
    )

    resultado = servico.keyword_only("E-4021")

    assert [h.doc_id for h in resultado] == ["lexico"]
    assert denso.queries == []
