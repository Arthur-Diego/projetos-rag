"""T4.6 — `GET /health` e a detecção de dessincronia entre os dois armazéns.

O caso que importa é o do meio: os dois armazéns NO AR, populados, e com
contagens diferentes. Não há erro nenhum para observar — é por isso que a
comparação precisa existir. Cada `doc_id` sobrando no índice é uma fonte que a
consulta descarta em silêncio (risco 4 do FDD).

`provide_healthy_properties` é substituído nos casos de sucesso: ele bate no
heartbeat do Chroma por `urllib`, e nenhum teste desta suíte abre conexão.
"""

from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from rag.api import dependencies
from rag.api.app import create_app
from rag.config import RagProperties
from rag.domain.models import DocumentUnit
from rag.exceptions import ServiceUnavailableException
from tests.fakes import FakeDocstore, FakeVectors


def _unit(doc_id: str) -> DocumentUnit:
    return DocumentUnit(
        doc_id=doc_id,
        kind="texto",
        content=f"original {doc_id}",
        representation=f"representação {doc_id}",
        source="petrobras-desempenho-3t24.pdf",
        page=1,
    )


def _app(tmp_path: Path, indexados: list[str], originais: list[str]) -> FastAPI:
    """Monta o app com as duas contagens INDEPENDENTES.

    Poder informar listas diferentes é o que torna a dessincronia injetável: no
    código real ela só aparece por falha parcial ou remoção manual de arquivo.
    """
    app = create_app()
    properties = RagProperties(
        openai_api_key="sk-teste",
        pdf_dir=tmp_path / "pdfs",
        docstore_dir=tmp_path / "docstore",
        partition_cache_dir=tmp_path / "particao",
        figures_dir=tmp_path / "figuras",
    )

    vectors = FakeVectors()
    vectors.add([_unit(doc_id) for doc_id in indexados])
    docstore = FakeDocstore()
    docstore.put([_unit(doc_id) for doc_id in originais])

    app.dependency_overrides[dependencies.provide_healthy_properties] = (
        lambda: properties
    )
    app.dependency_overrides[dependencies.provide_properties] = lambda: properties
    app.dependency_overrides[dependencies.provide_docstore] = lambda: docstore
    app.dependency_overrides[dependencies.provide_vectors] = lambda: vectors
    return app


def _client(tmp_path: Path, indexados: list[str], originais: list[str]) -> TestClient:
    return TestClient(_app(tmp_path, indexados, originais))


def test_armazens_consistentes_reportam_ok(tmp_path: Path) -> None:
    response = _client(tmp_path, ["a", "b"], ["a", "b"]).get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["indexed_chunks"] == 2
    assert body["docstore_originals"] == 2
    assert "degraded_reason" not in body
    # Campos opcionais do contrato preenchidos (seção 5 do FDD).
    assert {"collection", "embedding_model", "embedding_dimensions"} <= set(body)


def test_contagens_divergentes_reportam_degraded_com_evidencia(tmp_path: Path) -> None:
    """T4.6: índice com um `doc_id` a mais é órfão, e o /health diz qual lado."""
    response = _client(tmp_path, ["a", "b", "c"], ["a", "b"]).get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "degraded"
    assert body["indexed_chunks"] == 3
    assert body["docstore_originals"] == 2
    assert "órfão" in body["degraded_reason"]
    assert "reset.py" in body["degraded_reason"]


def test_docstore_a_frente_do_indice_tambem_e_degraded(tmp_path: Path) -> None:
    """Ingestão que parou no meio: original gravado, representação não.

    A receita muda de lado — aqui reingerir basta, e mandar zerar tudo custaria
    de volta o enriquecimento já pago.
    """
    body = _client(tmp_path, ["a"], ["a", "b"]).get("/health").json()

    assert body["status"] == "degraded"
    assert "ingest.py" in body["degraded_reason"]


def test_armazens_vazios_sao_consistentes(tmp_path: Path) -> None:
    """Estado normal antes da primeira ingestão: não há dessincronia nenhuma.

    Quem denuncia índice vazio é o `POST /ask`, com 409 — a seção 5 do FDD
    reserva `degraded` para incompatibilidade entre os armazéns.
    """
    assert _client(tmp_path, [], []).get("/health").json()["status"] == "ok"


def test_chroma_fora_do_ar_e_503_no_formato_problem(tmp_path: Path) -> None:
    """Saúde reporta ESTADO enquanto o serviço responde; sem ele, é 503."""
    app = _app(tmp_path, ["a"], ["a"])

    def indisponivel() -> RagProperties:
        raise ServiceUnavailableException("Chroma não respondeu.")

    app.dependency_overrides[dependencies.provide_healthy_properties] = indisponivel

    response = TestClient(app).get("/health")

    assert response.status_code == 503
    assert response.json()["code"] == "SERVICE_UNAVAILABLE"


def test_capabilities_declara_o_que_este_backend_faz(tmp_path: Path) -> None:
    """Sem `history` e sem `stream` (adr-002 da sessão e seção 3 do FDD)."""
    body = _client(tmp_path, [], []).get("/capabilities").json()

    assert set(body["features"]) == {"ask", "ingest", "sources"}

    k = body["parameters"]["k"]
    assert (k["type"], k["default"], k["minimum"], k["maximum"]) == (
        "integer",
        4,
        1,
        20,
    )
    assert k["applies_to"] == ["ask"]

    imagens = body["parameters"]["descrever_imagens"]
    assert (imagens["type"], imagens["default"]) == ("boolean", True)
    assert imagens["applies_to"] == ["ingest"]
