"""A camada HTTP contra o contrato compartilhado 1.1.0.

Estes testes executam as mesmas asserções que a coleção Postman declara, mas
sem exigir Qdrant, corpus nem chave da OpenAI: os provedores do container do
FastAPI são substituídos por dublês.

Não substituem a coleção. A coleção prova que o SERVIÇO REAL responde conforme;
estes provam que a camada HTTP traduz corretamente domínio em contrato, e
rodam a cada mudança sem infraestrutura. São perguntas diferentes.

O único teste que usa a infraestrutura de verdade é o do 503, e ele funciona
justamente porque não há Qdrant no ar.
"""

import pytest
from conftest import (
    FakeLLM,
    FakeKeywordRepository,
    FakeVectorRepository,
    PassThroughReranker,
    IN_CORPUS,
    OUT_OF_CORPUS,
    answer_with_citation,
)
from fastapi.testclient import TestClient

from rag.api import dependencies as deps
from rag.api.app import create_app
from rag.config import RagProperties
from rag.service.prompt_builder import ESCAPE_PHRASE

PROPERTIES = RagProperties(openai_api_key="sk-teste-nao-usada")

#: Porta onde não há nada escutando. Aponta o HealthChecker para o vazio de
#: propósito, em vez de contar com o Elasticsearch estar fora do ar: um teste que passa
#: só quando o ambiente está quebrado não testa nada, e falha quando o ambiente
#: melhora. Foi o que aconteceu na primeira versão deste arquivo.
PROPERTIES_SEM_MOTOR = RagProperties(
    openai_api_key="sk-teste-nao-usada", elastic_port=59_999
)


def make_client(
    hits,
    answer=answer_with_citation,
    rewrite="pergunta reescrita",
    keyword_hits=None,
):
    """App com as fronteiras externas substituídas por dublês.

    São SEIS provedores substituídos agora, não quatro: o funil acrescentou o
    repositório léxico, a fusão e o reordenador. A fusão NÃO é dublada, e é
    deliberado: ela é função pura, sem fronteira externa, e substituí-la
    esconderia justamente o comportamento que a rota deveria exercitar.
    """
    llm = FakeLLM(answer=answer, rewrite=rewrite)
    repository = FakeVectorRepository(list(hits))
    keywords = FakeKeywordRepository(list(keyword_hits or []))

    app = create_app()
    app.dependency_overrides[deps.provide_properties] = lambda: PROPERTIES
    app.dependency_overrides[deps.provide_healthy_properties] = lambda: PROPERTIES
    app.dependency_overrides[deps.provide_repository] = lambda: repository
    app.dependency_overrides[deps.provide_checked_repository] = lambda: repository
    app.dependency_overrides[deps.provide_keywords] = lambda: keywords
    app.dependency_overrides[deps.provide_reranker] = lambda: PassThroughReranker()
    app.dependency_overrides[deps.provide_generation] = lambda: llm

    return TestClient(app), llm, repository


# ---------------------------------------------------------------------------
# GET /capabilities
# ---------------------------------------------------------------------------


def test_capabilities_declara_history_e_os_nove_parametros():
    client, _, _ = make_client(IN_CORPUS)

    body = client.get("/capabilities").json()

    assert body["project"] == "rag-03-hybrid-rerank"
    assert set(body["features"]) == {"ask", "ingest", "history"}
    # Nove, e os quatro do funil são deste projeto. `k` NÃO ganhou irmão: ele já
    # É o corte final do funil, e um `top_n` ao lado seriam dois nomes para a
    # mesma grandeza.
    assert set(body["parameters"]) == {
        "k",
        "hibrida",
        "rerank",
        "candidates",
        "rrf_k",
        "history_window",
        "conditional_rewrite",
        "chunk_size",
        "chunk_overlap",
    }
    assert body["parameters"]["history_window"]["default"] == 6
    assert body["parameters"]["conditional_rewrite"]["default"] is False
    assert body["parameters"]["k"]["maximum"] == 20


def test_capabilities_nao_depende_de_infraestrutura():
    """Precisa responder mesmo com o Qdrant fora do ar.

    O frontend usa /capabilities para descobrir a forma da interface. Exigir
    infraestrutura aqui deixaria a tela em branco quando ela deveria dizer
    "backend no ar, índice indisponível".
    """
    app = create_app()
    app.dependency_overrides[deps.provide_properties] = lambda: PROPERTIES
    # Sem override de healthy_properties: se a rota dependesse dele, quebraria.
    assert TestClient(app).get("/capabilities").status_code == 200


# ---------------------------------------------------------------------------
# GET /health
# ---------------------------------------------------------------------------


def test_health_reporta_os_seis_campos():
    client, _, _ = make_client(IN_CORPUS)

    body = client.get("/health").json()

    assert body["status"] == "ok"
    assert body["project"] == "rag-03-hybrid-rerank"
    assert body["collection"] == "normas"
    assert body["indexed_chunks"] == 2
    assert body["embedding_model"] == "text-embedding-3-small"
    assert body["embedding_dimensions"] == 1536


def test_health_degradado_com_indice_vazio():
    """Distingue "no ar" de "tem conteúdo". São problemas diferentes."""
    client, _, _ = make_client([])

    body = client.get("/health").json()

    assert body["status"] == "degraded"
    assert body["indexed_chunks"] == 0


# ---------------------------------------------------------------------------
# POST /ask
# ---------------------------------------------------------------------------


def test_ask_primeiro_turno_sem_historico():
    client, llm, _ = make_client(IN_CORPUS)

    body = client.post("/ask", json={"question": "Quantos dias de férias eu tenho?"}).json()

    assert body["rewritten_question"]["reason"] == "primeiro_turno"
    assert body["rewritten_question"]["rewritten"] is False
    assert body["timings"]["rewrite_s"] == 0.0
    assert llm.rewrite_calls == 0


def test_ask_com_historico_reescreve_e_busca_o_texto_reescrito():
    client, llm, repository = make_client(
        IN_CORPUS, rewrite="Quantos dias de férias posso converter em abono?"
    )

    body = client.post(
        "/ask",
        json={
            "question": "E se eu vender dez?",
            "options": {
                "history": [
                    {
                        "question": "Quantos dias de férias eu tenho?",
                        "answer": "30 dias corridos [1].",
                    }
                ]
            },
        },
    ).json()

    assert body["rewritten_question"]["rewritten"] is True
    assert body["rewritten_question"]["reason"] == "historico_presente"
    assert body["rewritten_question"]["original"] == "E se eu vender dez?"
    assert body["rewritten_question"]["used"] == (
        "Quantos dias de férias posso converter em abono?"
    )
    # O que foi ao retriever é a query resolvida, e é isso que o projeto existe
    # para garantir.
    assert repository.queries == ["Quantos dias de férias posso converter em abono?"]
    assert llm.rewrite_calls == 1

    # `reason` é o sinal autoritativo de "houve chamada", não `rewrite_s`.
    # O presenter arredonda para 3 casas, e a reescrita do dublê leva
    # microssegundos: ela sai como 0.0 apesar de ter acontecido. Com um LLM real
    # isso não ocorre, mas afirmar `rewrite_s > 0` aqui seria afirmar algo que o
    # contrato não garante. A invariante estrita vale no domínio, e está testada
    # em test_rewrite.py::test_rewrite_s_maior_que_zero_quando_houve_chamada.
    assert body["rewritten_question"]["reason"] == "historico_presente"
    assert "rewrite_s" in body["timings"]


def test_ask_serializa_citacoes_com_fonte_e_pagina():
    client, _, _ = make_client(IN_CORPUS)

    body = client.post("/ask", json={"question": "quanto posso vender?"}).json()

    assert body["citations"] == [
        {
            "label": 1,
            "source": "clt.pdf",
            "page": 47,
            "excerpt": (
                "Art. 143. É facultado ao empregado converter um terço do "
                "período de férias a que tiver direito em abono pecuniário."
            ),
        },
        {
            "label": 2,
            "source": "clt.pdf",
            "page": 48,
            "excerpt": (
                "O abono de férias deverá ser requerido até 15 dias antes do "
                "término do período aquisitivo."
            ),
        },
    ]


def test_ask_recusa_nao_traz_citations():
    """Invariante 1, no formato do contrato: recusa é 200, e `citations` some."""
    client, _, _ = make_client(OUT_OF_CORPUS, answer=ESCAPE_PHRASE)

    response = client.post(
        "/ask",
        json={
            "question": "e nesse caso?",
            "options": {
                "history": [{"question": "e antes?", "answer": "resposta anterior [1]."}]
            },
        },
    )
    body = response.json()

    assert response.status_code == 200
    assert body["refused"] is True
    assert body["text"] == ESCAPE_PHRASE
    assert "citations" not in body
    # A busca trouxe trechos; a distância alta é a evidência de que não serviam.
    assert body["hits"][0]["distance"] > 0.9


def test_ask_ignora_chaves_desconhecidas_em_options():
    """Exigência do contrato: frontend mais novo não pode quebrar o backend."""
    client, _, _ = make_client(IN_CORPUS)

    response = client.post(
        "/ask",
        json={
            "question": "pergunta",
            "options": {"parametro_de_outro_projeto": 42, "graph_cycles": True},
        },
    )

    assert response.status_code == 200


def test_ask_history_window_zero_vira_primeiro_turno():
    client, llm, _ = make_client(IN_CORPUS)

    body = client.post(
        "/ask",
        json={
            "question": "e nesse caso?",
            "options": {
                "history_window": 0,
                "history": [{"question": "antes", "answer": "resposta [1]."}],
            },
        },
    ).json()

    assert body["rewritten_question"]["reason"] == "primeiro_turno"
    assert llm.rewrite_calls == 0


@pytest.mark.parametrize("k", [0, 21])
def test_ask_k_fora_da_faixa_e_422_no_formato_problem(k):
    client, _, _ = make_client(IN_CORPUS)

    response = client.post("/ask", json={"question": "pergunta", "options": {"k": k}})
    body = response.json()

    assert response.status_code == 422
    assert body["code"] == "INVALID_PARAMETER"
    assert set(body) == {"title", "detail", "code"}


def test_ask_turno_malformado_e_422_nunca_descarte_silencioso():
    """Histórico corrompido produziria reescrita errada sem nenhum sintoma."""
    client, _, _ = make_client(IN_CORPUS)

    response = client.post(
        "/ask",
        json={
            "question": "e nesse caso?",
            "options": {"history": [{"question": "faltou a resposta"}]},
        },
    )

    assert response.status_code == 422
    assert response.json()["code"] == "INVALID_PARAMETER"


def test_ask_indice_vazio_e_409_antes_de_qualquer_chamada_paga():
    client, llm, _ = make_client([])

    response = client.post("/ask", json={"question": "pergunta"})

    assert response.status_code == 409
    assert response.json()["code"] == "EMPTY_INDEX"
    assert llm.total_calls == 0


# ---------------------------------------------------------------------------
# POST /ingest
# ---------------------------------------------------------------------------


def test_ingest_overlap_maior_que_size_e_422():
    client, _, _ = make_client(IN_CORPUS)

    response = client.post(
        "/ingest", json={"options": {"chunk_size": 200, "chunk_overlap": 300}}
    )

    assert response.status_code == 422
    assert response.json()["code"] == "INVALID_PARAMETER"


# ---------------------------------------------------------------------------
# Erros que precisam sair no formato Problem
#
# Os três testes abaixo cobrem defeitos reais encontrados pelo dd-doc-sync no
# fechamento do ciclo. Todos tinham a mesma forma: o erro acontecia, mas o corpo
# saía fora do schema `Problem` que o contrato declara, e o frontend caía no ramo
# degradado sem conseguir explicar nada ao usuário.
# ---------------------------------------------------------------------------


def test_pergunta_vazia_e_422_no_formato_problem():
    """Sem `min_length` no modelo, senão o Pydantic responde antes do handler.

    O corpo do Pydantic é `{"detail": [{"type": "string_too_short", ...}]}`, que
    não tem `title` nem `code` e não é o `Problem` do contrato.
    """
    client, _, _ = make_client(IN_CORPUS)

    for vazia in ("", "   "):
        response = client.post("/ask", json={"question": vazia})
        body = response.json()

        assert response.status_code == 422
        assert set(body) == {"title", "detail", "code"}
        assert body["code"] == "INVALID_PARAMETER"


def test_falha_da_openai_vira_503_no_formato_problem():
    """Sem tradução na fronteira, um timeout vira 500 em texto puro."""
    client, _, _ = make_client(IN_CORPUS)
    # Substitui o dublê por um que estoura como a OpenAI estouraria.
    from rag.service.generation_service import OpenAiGenerationService

    quebrado = OpenAiGenerationService.__new__(OpenAiGenerationService)

    class _Estourado:
        def invoke(self, _):
            raise TimeoutError("a OpenAI não respondeu")

    quebrado._llm = _Estourado()  # type: ignore[attr-defined]
    client.app.dependency_overrides[deps.provide_generation] = lambda: quebrado

    response = client.post("/ask", json={"question": "pergunta"})
    body = response.json()

    assert response.status_code == 503
    assert body["code"] == "SERVICE_UNAVAILABLE"
    assert "OpenAI" in body["detail"]


@pytest.mark.parametrize(
    "opcoes",
    [
        {"history_window": 999},
        {"chunk_size": 99},
    ],
)
def test_maximos_declarados_em_capabilities_sao_impostos(opcoes):
    """Declarar um limite e não impô-lo transforma o descritor em sugestão."""
    client, _, _ = make_client(IN_CORPUS)
    caminho = "/ingest" if "chunk_size" in opcoes else "/ask"
    corpo = (
        {"options": opcoes}
        if caminho == "/ingest"
        else {"question": "pergunta", "options": opcoes}
    )

    response = client.post(caminho, json=corpo)

    assert response.status_code == 422
    assert response.json()["code"] == "INVALID_PARAMETER"


# ---------------------------------------------------------------------------
# Infraestrutura real
# ---------------------------------------------------------------------------


def test_qdrant_fora_do_ar_vira_503_com_o_comando_a_rodar():
    """Único teste que exercita o HealthChecker de verdade, contra o vazio.

    A mensagem precisa dizer O QUE FAZER, não só que falhou: é a mitigação do
    risco "falha de infraestrutura confundida com falha do pipeline".
    """
    app = create_app()
    app.dependency_overrides[deps.provide_properties] = lambda: PROPERTIES_SEM_MOTOR

    response = TestClient(app).get("/health")
    body = response.json()

    assert response.status_code == 503
    assert body["code"] == "SERVICE_UNAVAILABLE"
    assert "docker compose up -d elasticsearch" in body["detail"]
