"""T4.4 — a regra dura da omissão, aplicada ao `SearchHit` da 1.3.0.

A asserção não é "o valor é nulo?", é "a CHAVE existe?". A diferença é o
contrato: um cliente do 1.2.0 que receba `content_html: null` num hit de texto
passa a ter que distinguir ausente de vazio numa chave que ele nem conhece.
"""

from rag.domain.models import Answer, SearchHit
from rag.presenter.json_presenter import EXCERPT_CHARS, JsonPresenter

_TABELA = SearchHit(
    source="petrobras-desempenho-3t24.pdf",
    page=3,
    kind="tabela",
    excerpt="Tabela de resultados consolidados do 3T24.",
    score=0.62,
    content_html="<table><tr><td>129,6</td></tr></table>",
)
_TEXTO = SearchHit(
    source="petrobras-desempenho-3t24.pdf",
    page=1,
    kind="texto",
    excerpt="Desempenho operacional estável no trimestre.",
    score=0.41,
)
_IMAGEM = SearchHit(
    source="petrobras-desempenho-3t24.pdf",
    page=7,
    kind="imagem",
    excerpt="Gráfico de barras da produção por trimestre.",
)


def test_hit_de_texto_nao_carrega_a_chave_content_html() -> None:
    """A chave é OMITIDA, não emitida com null."""
    body = JsonPresenter().hit(_TEXTO)

    assert "content_html" not in body
    assert body["kind"] == "texto"


def test_hit_de_imagem_nao_carrega_a_chave_content_html() -> None:
    """`content_html` é exclusivo de tabela, e imagem também é fonte visual."""
    assert "content_html" not in JsonPresenter().hit(_IMAGEM)


def test_hit_de_tabela_carrega_o_html_original() -> None:
    assert JsonPresenter().hit(_TABELA)["content_html"] == _TABELA.content_html


def test_html_nunca_aparece_dentro_de_excerpt() -> None:
    """Invariante da seção 6 do FDD: `excerpt` é sempre texto exibível."""
    body = JsonPresenter().hit(_TABELA)

    assert "<table" not in body["excerpt"]
    assert body["excerpt"] == _TABELA.excerpt


def test_score_ausente_e_omitido_e_provenance_nunca_aparece() -> None:
    """Só há caminho denso: procedência com um caminho só seria ruído."""
    body = JsonPresenter().hit(_IMAGEM)

    assert "score" not in body
    assert "provenance" not in body


def test_nenhum_campo_do_hit_sai_como_null() -> None:
    presenter = JsonPresenter()

    for hit in (_TABELA, _TEXTO, _IMAGEM):
        body = presenter.hit(hit)
        assert all(value is not None for value in body.values()), body


def test_excerpt_e_truncado_para_exibicao() -> None:
    """O que vai ao modelo é o original íntegro; isto aqui é a vitrine."""
    longo = _TEXTO._replace(excerpt="palavra " * 200)

    assert len(JsonPresenter().hit(longo)["excerpt"]) <= EXCERPT_CHARS


def test_answer_nao_emite_citations_nem_rewritten_question() -> None:
    """Este projeto não faz nenhum dos dois: `[]` diria que procurou e não achou."""
    answer = Answer(
        text="A receita foi de R$ 129,6 bilhões [1].",
        refused=False,
        hits=(_TABELA,),
        timings={"search_s": 0.18, "generation_s": 2.4},
    )

    body = JsonPresenter().answer(answer)

    assert set(body) == {"text", "refused", "hits", "timings"}
    assert body["hits"][0]["kind"] == "tabela"
    assert all(value is not None for value in body["timings"].values())
