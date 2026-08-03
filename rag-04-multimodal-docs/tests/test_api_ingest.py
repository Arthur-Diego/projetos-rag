"""A borda HTTP do `POST /ingest`, sem tocar Chroma nem OpenAI.

O que se cobra aqui é a MATRIZ DE ERROS da seção 6 do FDD, não o pipeline: que
a rota existe, que a validação da borda acontece antes de qualquer custo e que
o erro sai no formato `Problem` do contrato compartilhado — e não no formato
próprio do Pydantic, que quebraria todo cliente do contrato.

As dependências pesadas são substituídas por `dependency_overrides`, o
mecanismo do próprio FastAPI: nenhuma requisição desta suíte abre conexão.
"""

from fastapi.testclient import TestClient

from rag.api import dependencies
from rag.api.app import create_app
from rag.config import RagProperties
from tests.fakes import FakeDocstore, FakeVectors


def _client(tmp_path) -> TestClient:  # type: ignore[no-untyped-def]
    app = create_app()
    properties = RagProperties(
        openai_api_key="sk-teste",
        pdf_dir=tmp_path / "pdfs",
        docstore_dir=tmp_path / "docstore",
        partition_cache_dir=tmp_path / "particao",
        figures_dir=tmp_path / "figuras",
    )
    app.dependency_overrides[dependencies.provide_properties] = lambda: properties
    app.dependency_overrides[dependencies.provide_docstore] = FakeDocstore
    app.dependency_overrides[dependencies.provide_vectors] = FakeVectors
    return TestClient(app)


def test_descrever_imagens_com_tipo_errado_e_422_no_formato_problem(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """Tipo errado é 422, e a 1.3.0 diz isso com todas as letras.

    Aceitar `"false"` como string por conveniência faria um cliente que pediu
    explicitamente para NÃO pagar visão pagar assim mesmo, sem sintoma nenhum
    além da fatura.
    """
    response = _client(tmp_path).post(
        "/ingest", json={"options": {"descrever_imagens": "false"}}
    )

    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "INVALID_PARAMETER"
    assert "descrever_imagens" in body["detail"]
    # Formato `Problem` do contrato, não o `{"detail": [...]}` do Pydantic.
    assert set(body) == {"title", "detail", "code"}


def test_corpus_vazio_e_422_antes_de_qualquer_custo(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """EC-1 da US-001: nenhum PDF é erro claro, não ingestão vazia bem-sucedida."""
    (tmp_path / "pdfs").mkdir()

    response = _client(tmp_path).post("/ingest", json={})

    assert response.status_code == 422
    assert response.json()["code"] == "EMPTY_CORPUS"


def test_configuracao_ausente_e_500_e_nao_503(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """A linha de cima da matriz de erros: configuração é 500, não dependência.

    E o ponto que só um teste de borda prova: a exceção é levantada DENTRO de um
    `Depends`, antes de a rota rodar. Se o tratador não alcançasse a resolução
    de dependências, o cliente receberia o 500 cru do framework, sem `Problem` e
    sem receita.
    """
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    client = TestClient(create_app(), raise_server_exceptions=False)

    response = client.post("/ingest", json={})

    assert response.status_code == 500
    body = response.json()
    assert body["code"] == "INVALID_CONFIGURATION"
    assert set(body) == {"title", "detail", "code"}


def test_corpo_ausente_usa_os_defaults_do_contrato(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """O `requestBody` é `required: false` no contrato: chamar sem corpo vale.

    O corpus continua vazio, então o resultado esperado é o 422 do caso acima —
    o que se prova aqui é que a AUSÊNCIA de corpo não vira erro de validação.
    """
    (tmp_path / "pdfs").mkdir()

    response = _client(tmp_path).post("/ingest")

    assert response.status_code == 422
    assert response.json()["code"] == "EMPTY_CORPUS"
