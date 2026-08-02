"""T3.1 — roteamento por categoria.

Um dos dois alvos de teste fixados em `docs/guidelines/README.md`, e o motivo
está na natureza da falha: se uma tabela for agrupada com o texto vizinho, nada
quebra. A ingestão conclui, o índice enche, as respostas saem — só que sem
tabela nenhuma, e a conclusão do projeto vira "multi-vector não ajudou".

A lista de elementos é SINTÉTICA de propósito: particionar um PDF de verdade
levaria minutos e provaria outra coisa (que o setup nativo funciona, que é o
papel do `test_smoke_partition.py`).
"""

from pathlib import Path

import pytest
from unstructured.documents.elements import (
    ElementMetadata,
    Image,
    NarrativeText,
    Table,
    Title,
)

from rag.service.routing_service import ElementRoutingService, count_elements


def _meta(page: int, **extra: object) -> ElementMetadata:
    return ElementMetadata(page_number=page, **extra)  # type: ignore[arg-type]


#: Seções longas o bastante para NÃO serem combinadas entre si.
#: `chunk_by_title` junta seções pequenas até encher a janela — é o que "agrupar
#: em ~1000 caracteres" significa —, então um fixture com duas frases curtas
#: sairia como uma unidade só e o teste de agrupamento por título não provaria
#: nada sobre o corte.
#: Cada uma cabe sozinha na janela de 1000 (não é dividida) e as duas juntas
#: não cabem (não são combinadas): é a faixa em que o corte por título é o
#: ÚNICO responsável pela quantidade de unidades.
RECEITA = (
    "A receita de vendas cresceu no trimestre por conta do preço do barril "
    "e do câmbio médio do período. " * 6
)
PRODUCAO = (
    "A produção de óleo e gás natural ficou estável no período, com os novos "
    "sistemas compensando o declínio natural dos campos maduros. " * 4
)


@pytest.fixture
def elements(tmp_path: Path) -> list:
    """Um documento sintético: dois assuntos, uma tabela e uma figura."""
    figure = tmp_path / "figure-3-1.jpg"
    figure.write_bytes(b"\xff\xd8\xff\xe0 bytes de uma figura")

    return [
        Title(text="Desempenho financeiro", metadata=_meta(1)),
        NarrativeText(text=RECEITA, metadata=_meta(1)),
        Table(
            text="Receita 129,6 EBITDA 61,7",
            metadata=_meta(2, text_as_html="<table><tr><td>129,6</td></tr></table>"),
        ),
        Title(text="Produção", metadata=_meta(3)),
        NarrativeText(text=PRODUCAO, metadata=_meta(3)),
        Image(text="", metadata=_meta(3, image_path=str(figure))),
    ]


def test_cada_categoria_produz_o_kind_correto(tmp_path: Path, elements: list) -> None:
    units = ElementRoutingService(tmp_path / "figuras").route(
        elements, source="relatorio.pdf"
    )

    kinds = {unit.kind for unit in units}
    assert kinds == {"texto", "tabela", "imagem"}
    assert count_elements(units) == (2, 1, 1)


def test_tabela_vira_unidade_propria_com_o_html(
    tmp_path: Path, elements: list
) -> None:
    """O HTML é o ORIGINAL. Perdê-lo aqui é perder o projeto inteiro."""
    units = ElementRoutingService(tmp_path / "figuras").route(
        elements, source="relatorio.pdf"
    )

    tabelas = [unit for unit in units if unit.kind == "tabela"]
    assert len(tabelas) == 1
    assert tabelas[0].content == "<table><tr><td>129,6</td></tr></table>"
    assert tabelas[0].page == 2
    # A representação fica VAZIA: preenchê-la é o estágio pago (ADR-002).
    assert tabelas[0].representation == ""


def test_tabela_e_imagem_nunca_sao_agrupadas_com_o_texto(
    tmp_path: Path, elements: list
) -> None:
    """A invariante central: o agrupamento não pode desfazer a partição.

    Uma unidade de texto que contivesse o HTML da tabela significaria que a
    tabela entrou no `chunk_by_title` — e daí ela chegaria ao índice como sopa
    de números, exatamente como no `PyPDFLoader` dos projetos 1 a 3.
    """
    units = ElementRoutingService(tmp_path / "figuras").route(
        elements, source="relatorio.pdf"
    )

    for texto in [unit for unit in units if unit.kind == "texto"]:
        assert "<table" not in texto.content
        assert "129,6" not in texto.content


def test_texto_narrativo_e_agrupado_por_titulo(tmp_path: Path, elements: list) -> None:
    """Dois títulos, duas unidades: o corte segue o documento, não o caractere."""
    units = ElementRoutingService(tmp_path / "figuras").route(
        elements, source="relatorio.pdf"
    )

    textos = [unit for unit in units if unit.kind == "texto"]
    assert len(textos) == 2
    assert "Desempenho financeiro" in textos[0].content
    assert "receita de vendas cresceu" in textos[0].content
    assert "Produção" in textos[1].content
    assert "produção de óleo" in textos[1].content
    # O corte é por TÍTULO: nenhum assunto vaza para a unidade do outro.
    assert "produção de óleo" not in textos[0].content
    # O texto é a própria representação: multi-vector SELETIVO (ADR-002).
    assert all(unit.content == unit.representation for unit in textos)


def test_imagem_vira_unidade_com_arquivo_nomeado_pelo_doc_id(
    tmp_path: Path, elements: list
) -> None:
    """O nome do arquivo deriva do `doc_id`, nunca do conteúdo do PDF (ADR-003)."""
    figures = tmp_path / "figuras"
    units = ElementRoutingService(figures).route(elements, source="relatorio.pdf")

    imagens = [unit for unit in units if unit.kind == "imagem"]
    assert len(imagens) == 1
    figure_path = Path(imagens[0].figure_path or "")
    assert figure_path.exists()
    assert figure_path.stem == imagens[0].doc_id
    assert figure_path.parent == figures


def test_conteudo_repetido_colapsa_num_unico_doc_id(tmp_path: Path) -> None:
    """Rodapé repetido não é erro: é deduplicação de graça (EC-2 da US-003)."""
    rodape = "Petrobras — Relatório de desempenho"
    elements = [
        Title(text="Seção A", metadata=_meta(1)),
        NarrativeText(text=rodape, metadata=_meta(1)),
        Title(text="Seção A", metadata=_meta(2)),
        NarrativeText(text=rodape, metadata=_meta(2)),
    ]

    units = ElementRoutingService(tmp_path / "figuras").route(
        elements, source="relatorio.pdf"
    )

    assert len({unit.doc_id for unit in units}) == len(units)


def test_relatorio_denuncia_ausencia_de_tabela(tmp_path: Path) -> None:
    """`tabelas: 0` é o sinal do risco 1, e precisa aparecer no log."""
    from tests.fakes import RecordingLog

    log = RecordingLog()
    ElementRoutingService(tmp_path / "figuras", log=log).route(
        [NarrativeText(text="Só texto aqui.", metadata=_meta(1))],
        source="relatorio.pdf",
    )

    assert any("nenhuma tabela detectada" in line.lower() for line in log.lines)
