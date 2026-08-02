"""T4.5 e a borda HTTP do `POST /ask`, sem tocar Chroma nem OpenAI.

O que se cobra é a MATRIZ DE ERROS da seção 6 do FDD e a ORDEM dela: validação
de borda antes de custo, 409 antes de chamada paga, e todo erro no formato
`Problem` do contrato — não no formato do Pydantic, que quebraria todo cliente.

As dependências pesadas são substituídas por `dependency_overrides`, o mecanismo
do próprio FastAPI: nenhuma requisição desta suíte abre conexão.
"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from rag.api import dependencies
from rag.api.app import create_app
from rag.config import MAX_K, RagProperties
from rag.domain.models import DocumentUnit, IndexMatch
from tests.fakes import CountingGeneration, FakeDocstore, FakeVectors

_TABELA = DocumentUnit(
    doc_id="ccc",
    kind="tabela",
    content="<table><tr><td>129,6</td></tr></table>",
    representation="Tabela de resultados consolidados do 3T24.",
    source="petrobras-desempenho-3t24.pdf",
    page=3,
)


def _client(
    tmp_path: Path, generation: CountingGeneration, populado: bool = True
) -> TestClient:
    app = create_app()
    properties = RagProperties(
        openai_api_key="sk-teste",
        pdf_dir=tmp_path / "pdfs",
        docstore_dir=tmp_path / "docstore",
        partition_cache_dir=tmp_path / "particao",
        figures_dir=tmp_path / "figuras",
    )

    vectors = FakeVectors()
    docstore = FakeDocstore()
    if populado:
        vectors.add([_TABELA])
        vectors.matches = [IndexMatch(doc_id=_TABELA.doc_id, distance=0.38)]
        docstore.put([_TABELA])

    app.dependency_overrides[dependencies.provide_properties] = lambda: properties
    app.dependency_overrides[dependencies.provide_docstore] = lambda: docstore
    app.dependency_overrides[dependencies.provide_vectors] = lambda: vectors
    app.dependency_overrides[dependencies.provide_generation] = lambda: generation
    return TestClient(app)


def test_pergunta_vazia_e_422_no_formato_problem(tmp_path: Path) -> None:
    """T4.5: validação na borda, antes de qualquer custo."""
    generation = CountingGeneration()

    response = _client(tmp_path, generation).post("/ask", json={"question": "   "})

    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "INVALID_PARAMETER"
    assert set(body) == {"title", "detail", "code"}
    assert generation.calls == 0


@pytest.mark.parametrize("k", [0, MAX_K + 1])
def test_k_fora_de_faixa_e_422_sem_gastar_nada(tmp_path: Path, k: int) -> None:
    """T4.5: a faixa 1 a 20 declarada em `/capabilities` é imposta."""
    generation = CountingGeneration()

    response = _client(tmp_path, generation).post(
        "/ask", json={"question": "qual foi a receita no 3T24?", "options": {"k": k}}
    )

    assert response.status_code == 422
    assert response.json()["code"] == "INVALID_PARAMETER"
    assert generation.calls == 0


def test_k_com_tipo_errado_e_422_e_nao_default_silencioso(tmp_path: Path) -> None:
    """Mesma exigência da 1.3.0 aplicada ao `descrever_imagens` na task_03."""
    response = _client(tmp_path, CountingGeneration()).post(
        "/ask", json={"question": "receita?", "options": {"k": "4"}}
    )

    assert response.status_code == 422
    assert "k" in response.json()["detail"]


def test_indice_vazio_e_409_antes_de_qualquer_chamada_paga(tmp_path: Path) -> None:
    """T4.3 pela borda HTTP: 409 do contrato, gerador intocado."""
    generation = CountingGeneration()

    response = _client(tmp_path, generation, populado=False).post(
        "/ask", json={"question": "qual foi a receita no 3T24?"}
    )

    assert response.status_code == 409
    assert response.json()["code"] == "EMPTY_INDEX"
    assert generation.calls == 0


def test_resposta_de_tabela_sai_na_semantica_1_3_0(tmp_path: Path) -> None:
    """O hit da tabela carrega `kind`, o resumo em `excerpt` e o HTML original."""
    response = _client(tmp_path, CountingGeneration()).post(
        "/ask", json={"question": "qual foi a receita no 3T24?", "options": {"k": 4}}
    )

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"text", "refused", "hits", "timings"}

    hit = body["hits"][0]
    assert hit["kind"] == "tabela"
    assert hit["excerpt"] == _TABELA.representation
    assert hit["content_html"] == _TABELA.content
    assert "provenance" not in hit
    assert {"search_s", "generation_s"} <= set(body["timings"])


def test_recusa_do_modelo_vira_refused_true(tmp_path: Path) -> None:
    """Controle negativo: quem classifica a recusa é a facade, não o cliente."""
    from rag.service.prompt_builder import ESCAPE_PHRASE

    response = _client(tmp_path, CountingGeneration(reply=ESCAPE_PHRASE)).post(
        "/ask", json={"question": "qual a taxa Selic de 2019?"}
    )

    assert response.status_code == 200
    assert response.json()["refused"] is True
