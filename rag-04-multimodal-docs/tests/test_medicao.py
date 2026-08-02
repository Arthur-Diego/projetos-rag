"""T6.1, T6.2 e T6.3 — o golden set e o script de medição.

O que se cobra aqui é o que torna a medição CONFIÁVEL, e não o que ela mede:

- **T6.1**: o golden set tem a forma que o script pressupõe. Um `perguntas.json`
  com uma pergunta factual sem âncora produziria acerto zero eternamente, e a
  conclusão publicada seria "o pipeline não recupera tabela" quando o defeito
  está no arquivo de dados.
- **T6.2**: a normalização da âncora sobrevive ao corpus real. O OCR do `hi_res`
  come acento e a tabela chega em HTML; comparar cru mediria tipografia.
- **T6.3**: `--sem-geracao` não gasta geração NENHUMA. O dublê conta as
  invocações, porque a afirmação a provar é "não gastou", e uma medição que
  cobra a API do autor quando ele pediu para não cobrar é um defeito caro.

O script mora em `docs/operations/` e tem hífen no nome (é ferramenta de
operação, não módulo importável de `rag/`), então entra por `importlib`.
"""

import importlib.util
import json
import re
from pathlib import Path
from types import ModuleType

import pytest

from rag.domain.models import DocumentUnit, IndexMatch, SearchHit
from rag.facade.query_facade import QueryFacade
from rag.service.prompt_builder import ESCAPE_PHRASE, PromptBuilder
from rag.service.retrieval.retrieval_service import RetrievalService
from tests.fakes import CountingGeneration, FakeDocstore, FakeVectors

OPERATIONS = Path(__file__).resolve().parent.parent / "docs" / "operations"
PERGUNTAS = OPERATIONS / "perguntas.json"

#: Mínimos exigidos pela task: a medição por classe só separa o sintoma se cada
#: classe tiver massa suficiente para uma fração significar alguma coisa.
MINIMO_POR_CLASSE = {"tabela": 4, "texto": 3, "imagem": 2, "negativo": 2}

CLASSES_FACTUAIS = ("tabela", "texto")


def _carrega_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "tabela_medicao", OPERATIONS / "tabela-medicao.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


medicao = _carrega_script()


@pytest.fixture(scope="module")
def golden() -> dict:
    carregado: dict = json.loads(PERGUNTAS.read_text())
    return carregado


# --------------------------------------------------------------------------
# T6.1 — estrutura do golden set
# --------------------------------------------------------------------------


def test_golden_set_declara_corpus_e_fonte_do_controle_negativo(golden: dict) -> None:
    """Sem as duas fontes declaradas, ninguém reproduz a rodada publicada."""
    assert golden["corpus"] == "petrobras-desempenho-3t24.pdf"
    assert "fora-do-corpus" in golden["fora_do_corpus"]


def test_toda_pergunta_tem_id_unico_classe_conhecida_e_enunciado(golden: dict) -> None:
    ids = [item["id"] for item in golden["perguntas"]]
    assert len(ids) == len(set(ids))
    for item in golden["perguntas"]:
        assert item["classe"] in medicao.CLASSES
        assert item["pergunta"].strip()


def test_pergunta_factual_tem_ancora_nao_vazia(golden: dict) -> None:
    """Âncora vazia em classe factual reprovaria o sistema por defeito do dado."""
    for item in golden["perguntas"]:
        if item["classe"] in CLASSES_FACTUAIS:
            assert item["ancora"].strip(), f"{item['id']} sem âncora"
            assert item["pagina"] > 0


def test_imagem_nao_tem_ancora_e_declara_o_esperado_qualitativo(golden: dict) -> None:
    """adr-003: imagem não promete valor exato, então não pode ter âncora literal.

    Uma âncora aqui contrabandearia a promessa de valor exato para a classe que a
    decisão excluiu dela — e o resultado publicado voltaria a cobrar do modelo de
    visão o que ele reconhecidamente erra.
    """
    imagens = [i for i in golden["perguntas"] if i["classe"] == "imagem"]
    for item in imagens:
        assert item["ancora"] == ""
        assert item["esperado_qualitativo"].strip()


def test_controle_negativo_e_marcado_e_aponta_a_fonte_fora_do_corpus(
    golden: dict,
) -> None:
    negativos = [i for i in golden["perguntas"] if i["classe"] == "negativo"]
    for item in negativos:
        assert item["ancora"] == ""
        assert "bcb" in item["fonte"].lower()


def test_cada_classe_tem_a_massa_minima_da_task(golden: dict) -> None:
    for classe, minimo in MINIMO_POR_CLASSE.items():
        quantas = sum(1 for i in golden["perguntas"] if i["classe"] == classe)
        assert quantas >= minimo, f"classe {classe}: {quantas} < {minimo}"


def test_a_pergunta_criterio_do_guia_esta_marcada_uma_unica_vez(golden: dict) -> None:
    """O critério do guia precisa ser localizável no relatório, não deduzido."""
    criterio = [i for i in golden["perguntas"] if i.get("criterio_do_guia")]
    assert len(criterio) == 1
    assert "receita" in criterio[0]["pergunta"].lower()
    assert "3t24" in criterio[0]["pergunta"].lower()
    assert criterio[0]["classe"] == "tabela"


def test_ancoras_factuais_existem_no_pdf_pelo_caminho_independente(
    golden: dict, corpus_pdf: Path
) -> None:
    """Anticircularidade, verificada: `pypdf`, nunca o `unstructured` do sistema.

    Este teste é o guardião da regra herdada do rag-03. Ele relê o PDF pelo
    caminho INDEPENDENTE e exige que cada âncora esteja lá — uma âncora que só
    existisse na saída do pipeline tornaria o acerto tautológico.
    """
    pypdf = pytest.importorskip("pypdf")

    paginas = pypdf.PdfReader(corpus_pdf).pages
    texto = medicao.normaliza(
        " ".join(pagina.extract_text() or "" for pagina in paginas)
    )
    for item in golden["perguntas"]:
        if item["classe"] in CLASSES_FACTUAIS:
            assert medicao.normaliza(item["ancora"]) in texto, item["id"]


# --------------------------------------------------------------------------
# T6.2 — normalização da âncora
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "bruto,esperado",
    [
        ("Receita de Vendas", "receita de vendas"),
        ("adesão à transação tributária", "adesao a transacao tributaria"),
        ("linha\nquebrada   por    espaço", "linha quebrada por espaco"),
        ("  sobrando nas pontas  ", "sobrando nas pontas"),
    ],
)
def test_normalizacao_achata_caixa_acento_e_espaco(bruto: str, esperado: str) -> None:
    assert medicao.normaliza(bruto) == esperado


def test_ancora_casa_com_a_mesma_frase_deformada_pelo_ocr() -> None:
    """O caso real: o `hi_res` devolve a frase sem acento e em outra caixa."""
    ancora = "adesão à transação tributária"
    do_ocr = "os custos relacionados à ADESAO A TRANSACAO TRIBUTARIA no trimestre"

    assert medicao.normaliza(ancora) in medicao.normaliza(do_ocr)


def test_normalizacao_troca_tag_por_espaco_e_nao_cola_celulas() -> None:
    """Tag some virando ESPAÇO, e a diferença importa nos dois sentidos.

    Colar as células produziria `vendas129.582`, que perde o acerto legítimo de
    `Receita de vendas` — e criaria casamentos que o documento não tem.
    """
    html = "<tr><td>Receita de vendas</td><td>129.582</td></tr>"

    assert medicao.normaliza(html) == "receita de vendas 129.582"
    assert "receita de vendas" in medicao.normaliza(html)


def test_ancora_no_hit_procura_no_html_e_nao_so_no_resumo() -> None:
    """O número da célula vive no original; o resumo raramente o repete."""
    hit = SearchHit(
        source="petrobras-desempenho-3t24.pdf",
        page=5,
        kind="tabela",
        excerpt="A tabela apresenta dados financeiros da Petrobras no 3T24.",
        content_html="<table><tr><td>Receita de vendas</td><td>129.582</td></tr></table>",
    )

    assert medicao.ancora_no_hit("129.582", hit) is True
    assert medicao.ancora_no_html("129.582", (hit,)) is True
    assert medicao.ancora_no_html("999.999", (hit,)) is False


def test_acerto_de_texto_nao_conta_como_evidencia_de_html() -> None:
    """Um hit de texto que contém a âncora acerta, mas não prova o critério.

    A distinção é o projeto inteiro: `acertou` diz que a recuperação trouxe a
    resposta; `html_no_hit` diz que ela veio da TABELA íntegra.
    """
    hit = SearchHit(
        source="petrobras-desempenho-3t24.pdf",
        page=6,
        kind="texto",
        excerpt="a receita de vendas somou 129.582 milhões no trimestre",
    )

    assert medicao.ancora_no_hit("129.582", hit) is True
    assert medicao.ancora_no_html("129.582", (hit,)) is False


# --------------------------------------------------------------------------
# T6.3 — `--sem-geracao` não gasta geração
# --------------------------------------------------------------------------


def _unidade(doc_id: str, kind: str, content: str, representation: str) -> DocumentUnit:
    return DocumentUnit(
        doc_id=doc_id,
        kind=kind,  # type: ignore[arg-type]
        content=content,
        representation=representation,
        source="petrobras-desempenho-3t24.pdf",
        page=5,
    )


def _facade_dublada() -> tuple[QueryFacade, CountingGeneration, FakeVectors]:
    """Corpus mínimo com as três classes, e um gerador que CONTA as chamadas."""
    unidades = [
        _unidade(
            "tab",
            "tabela",
            "<table><tr><td>Receita de vendas</td><td>129.582</td></tr></table>",
            "Resumo da tabela de resultados consolidados do 3T24.",
        ),
        _unidade(
            "txt",
            "texto",
            "As despesas caíram pela adesão à transação tributária.",
            "As despesas caíram pela adesão à transação tributária.",
        ),
        _unidade(
            "img",
            "imagem",
            "Gráfico de barras do EBITDA por trimestre.",
            "Gráfico de barras do EBITDA por trimestre.",
        ),
    ]
    vectors = FakeVectors()
    vectors.add(unidades)
    vectors.matches = [
        IndexMatch(doc_id=unidade.doc_id, distance=0.1 * (posicao + 1))
        for posicao, unidade in enumerate(unidades)
    ]
    docstore = FakeDocstore()
    docstore.put(unidades)

    generation = CountingGeneration()
    facade = QueryFacade(
        retrieval=RetrievalService(vectors, docstore, k=4),
        prompts=PromptBuilder(),
        generation=generation,
    )
    return facade, generation, vectors


PERGUNTAS_DUBLE = [
    {"id": "T1", "classe": "tabela", "pergunta": "receita?", "ancora": "129.582"},
    {"id": "X1", "classe": "texto", "pergunta": "despesas?", "ancora": "transação"},
    {"id": "G1", "classe": "imagem", "pergunta": "gráfico?", "ancora": ""},
    {"id": "N1", "classe": "negativo", "pergunta": "selic?", "ancora": ""},
]


def test_sem_geracao_mede_recuperacao_sem_chamar_o_gerador() -> None:
    """T6.3: quatro perguntas, quatro buscas, ZERO gerações."""
    facade, generation, vectors = _facade_dublada()

    resultados = medicao.mede(facade, PERGUNTAS_DUBLE, sem_geracao=True)

    assert generation.calls == 0
    assert vectors.searches == len(PERGUNTAS_DUBLE)
    assert resultados["T1"]["acertou"] is True
    assert resultados["T1"]["html_no_hit"] is True
    assert resultados["X1"]["acertou"] is True
    assert resultados["G1"]["acertou"] is True
    # A classe cujo acerto é a recusa não é mensurável sem geração, e sai como
    # `None` — nunca como falso, que seria reprovar o que não foi medido.
    assert resultados["N1"]["acertou"] is None


def test_sem_geracao_imprime_a_tabela_por_classe(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A tabela é o entregável: `--sem-geracao` não pode devolver saída muda."""
    facade, _, _ = _facade_dublada()

    resultados = medicao.mede(facade, PERGUNTAS_DUBLE, sem_geracao=True)
    medicao.imprime(PERGUNTAS_DUBLE, resultados, sem_geracao=True)
    saida = capsys.readouterr().out

    assert "ACERTO POR CLASSE DE ALVO" in saida
    for classe in ("tabela", "texto", "imagem", "negativo"):
        assert re.search(rf"{classe}\s+\(\d+\)", saida)
    # Sem geração não há recusa medida, e a seção não aparece anunciando zeros.
    assert "TAXA DE RECUSA" not in saida
    assert "âncora no content_html" in saida
    assert "n/a" in saida


def test_com_geracao_o_negativo_acerta_quando_o_sistema_recusa() -> None:
    """A outra metade: com geração, recusa vira o acerto da classe `negativo`."""
    facade, generation, _ = _facade_dublada()
    generation.reply = ESCAPE_PHRASE

    resultados = medicao.mede(facade, PERGUNTAS_DUBLE, sem_geracao=False)

    assert generation.calls == len(PERGUNTAS_DUBLE)
    assert resultados["N1"]["recusou"] is True
    assert resultados["N1"]["acertou"] is True


def test_classe_desconhecida_no_golden_set_falha_alto() -> None:
    """Erro de digitação em `classe` não pode virar acerto zero silencioso."""
    facade, _, _ = _facade_dublada()

    with pytest.raises(ValueError, match="classe desconhecida"):
        medicao.mede(
            facade,
            [{"id": "Z1", "classe": "tablea", "pergunta": "?", "ancora": "x"}],
            sem_geracao=True,
        )
