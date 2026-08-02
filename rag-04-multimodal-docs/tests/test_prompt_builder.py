"""T4.1 — o que entra no contexto por tipo de fonte.

**Este é o teste do critério de sucesso do guia.** Tudo o mais neste projeto
existe para que esta asserção seja verdadeira: para um hit `kind=tabela`, o que
chega ao modelo é o HTML do docstore, e não o resumo que estava no índice.

O caso é escrito de modo que os dois conteúdos sejam distinguíveis à vista
(`<table>` versus "resumo da tabela"): um dublê que ecoasse o mesmo texto nos
dois campos faria o teste passar sem provar nada.
"""

from rag.domain.models import SearchHit
from rag.service.prompt_builder import MAX_TABLE_CHARS, PromptBuilder
from tests.fakes import RecordingLog

_HTML = "<table><tr><th>Indicador</th><th>3T24</th></tr>" "<tr><td>Receita</td><td>129,6</td></tr></table>"
_RESUMO = "Tabela de resultados consolidados do 3T24: receita, EBITDA e lucro."

_TABELA = SearchHit(
    source="petrobras-desempenho-3t24.pdf",
    page=3,
    kind="tabela",
    excerpt=_RESUMO,
    score=0.62,
    content_html=_HTML,
)
_TEXTO = SearchHit(
    source="petrobras-desempenho-3t24.pdf",
    page=1,
    kind="texto",
    excerpt="A companhia registrou desempenho operacional estável no trimestre.",
    score=0.41,
)
_IMAGEM = SearchHit(
    source="petrobras-desempenho-3t24.pdf",
    page=7,
    kind="imagem",
    excerpt="Gráfico de barras com a produção por trimestre, em tendência de alta.",
    score=0.33,
)


def test_tabela_entra_com_o_html_original_e_nunca_com_o_resumo() -> None:
    """A invariante central: o índice buscou pelo resumo, o LLM recebe o HTML."""
    context = PromptBuilder().format_context((_TABELA,))

    assert _HTML in context
    assert _RESUMO not in context


def test_texto_e_imagem_entram_com_o_proprio_conteudo() -> None:
    """Multi-vector SELETIVO (ADR-002): só tabela tem original diferente."""
    context = PromptBuilder().format_context((_TEXTO, _IMAGEM))

    assert _TEXTO.excerpt in context
    assert _IMAGEM.excerpt in context


def test_numeracao_e_1_based_e_na_ordem_dos_hits() -> None:
    """O modelo cita `[n]`, e `n` é a posição do hit. 1-based, não 0-based."""
    context = PromptBuilder().format_context((_TEXTO, _TABELA, _IMAGEM))

    assert context.startswith("[1] ")
    assert "[2] " in context
    assert "[3] " in context
    assert "[0] " not in context
    # A ordem é a da recuperação: o trecho [2] é o que tem o HTML.
    assert context.index("[2] ") < context.index(_HTML) < context.index("[3] ")


def test_o_tipo_de_cada_trecho_e_declarado_no_contexto() -> None:
    """Sem o rótulo, a instrução sobre gráfico não teria a que se aplicar."""
    context = PromptBuilder().format_context((_TABELA, _IMAGEM))

    assert "tipo: tabela em HTML" in context
    assert "tipo: descrição de imagem" in context


def test_tamanho_do_contexto_vai_para_o_log() -> None:
    """Métrica obrigatória da seção 7 do FDD, em toda consulta."""
    log = RecordingLog()

    context = PromptBuilder(log=log).format_context((_TEXTO, _TABELA))

    assert any(
        f"{len(context)} caractere(s)" in line and "1 tabela(s)" in line
        for line in log.lines
    )


def test_truncamento_de_tabela_grande_e_registrado_nunca_silencioso() -> None:
    """Risco 5 do FDD: cortar é aceitável; cortar sem avisar não é."""
    log = RecordingLog()
    gigante = _TABELA._replace(content_html="<table>" + "x" * MAX_TABLE_CHARS)

    context = PromptBuilder(log=log).format_context((gigante,))

    assert "TABELA TRUNCADA" in context
    assert any("truncada" in line and "risco 5" in line for line in log.lines)


def test_tabela_sem_html_degrada_para_o_resumo_e_denuncia() -> None:
    """Inconsistência do emissor: degradar é melhor que sumir com a fonte."""
    log = RecordingLog()
    inconsistente = _TABELA._replace(content_html=None)

    context = PromptBuilder(log=log).format_context((inconsistente,))

    assert _RESUMO in context
    assert any("nenhum content_html" in line for line in log.lines)
