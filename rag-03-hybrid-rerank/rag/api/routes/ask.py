"""POST /ask — pergunta ao corpus, ciente da conversa.

A rota faz três coisas: lê os parâmetros do corpo, monta a facade que depende
deles, e apresenta. **Nenhuma lógica de RAG aqui.** Se aparecer, algo foi para
o lugar errado.
"""

from fastapi import APIRouter

from ...config import (
    DEFAULT_CANDIDATES,
    DEFAULT_CONDITIONAL_REWRITE,
    DEFAULT_HISTORY_WINDOW,
    DEFAULT_HYBRID,
    DEFAULT_K,
    DEFAULT_RERANK,
    DEFAULT_RRF_K,
)
from ...exceptions import InvalidParameterException
from ...facade.query_facade import QueryFacade
from ...service.health_checker import HealthChecker
from ...service.query_rewrite_service import QueryRewriteService
from ...service.retrieval.retrieval_service import RetrievalService
from ..dependencies import (
    CheckedRepository,
    Citations,
    DenseSearch,
    Fusion,
    Generation,
    HealthyProperties,
    KeywordSearch,
    Presenter,
    Prompts,
    Reranker,
    read_bool,
    read_history,
    read_int,
)
from ..schemas import AskRequest

router = APIRouter()


@router.post("/ask")
def ask(
    body: AskRequest,
    properties: HealthyProperties,
    repository: CheckedRepository,
    generation: Generation,
    prompts: Prompts,
    citations: Citations,
    presenter: Presenter,
    dense: DenseSearch,
    keywords: KeywordSearch,
    fusion: Fusion,
    reranker: Reranker,
) -> dict:
    if not body.question.strip():
        # Validado aqui, e não no modelo Pydantic: o 422 precisa sair no formato
        # `Problem` do contrato, e um erro de validação do framework não sai.
        raise InvalidParameterException(
            "a pergunta não pode ser vazia."
        )

    k = read_int(body.options, "k", DEFAULT_K)
    window = read_int(body.options, "history_window", DEFAULT_HISTORY_WINDOW)
    conditional = read_bool(
        body.options, "conditional_rewrite", DEFAULT_CONDITIONAL_REWRITE
    )
    hybrid = read_bool(body.options, "hibrida", DEFAULT_HYBRID)
    rerank = read_bool(body.options, "rerank", DEFAULT_RERANK)
    candidates = read_int(body.options, "candidates", DEFAULT_CANDIDATES)
    rrf_k = read_int(body.options, "rrf_k", DEFAULT_RRF_K)

    # A conferência de mapping é CONDICIONAL ao caminho léxico ter sido pedido.
    # Com `hibrida` desligado a requisição passa mesmo com o índice mal mapeado,
    # porque a busca densa não depende daquele campo e não há nada de errado com
    # ela; e a configuração puramente densa é a linha de base da tabela de
    # medição, que ficaria bloqueada por um defeito que não a afeta.
    if hybrid:
        HealthChecker(properties).check_mapping(repository)

    # Turno malformado levanta aqui, e vira 422 no error handler. É a única
    # coisa em `options` que falha alto em vez de cair no default.
    conversation = read_history(body.options)

    facade = QueryFacade(
        rewrite=QueryRewriteService(generation, conditional=conditional),
        retrieval=RetrievalService(
            dense,
            keywords=keywords,
            fusion=fusion,
            reranker=reranker,
            k=k,
            candidates=candidates,
            rrf_k=rrf_k,
            hybrid=hybrid,
            rerank=rerank,
        ),
        prompts=prompts,
        generation=generation,
        citations=citations,
        history_window=window,
    )

    # Antes de qualquer chamada paga: índice vazio é 409, não uma resposta vazia
    # que custou duas chamadas de LLM.
    facade.open_index(properties.collection)

    return presenter.answer(facade.ask(body.question, conversation))
