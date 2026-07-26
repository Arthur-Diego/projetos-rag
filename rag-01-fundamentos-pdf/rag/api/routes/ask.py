"""Rota de consulta.

A rota faz três coisas: lê os parâmetros do corpo, monta a facade que depende
deles e apresenta o resultado. **Nenhuma lógica de RAG mora aqui** — se aparecer
uma, ela está no lugar errado.
"""

from fastapi import APIRouter

from ...facade.query_facade import QueryFacade
from ...service.retrieval_service import RetrievalService
from ..dependencies import (
    Generation,
    HealthyProperties,
    Presenter,
    Prompts,
    Repository,
    read_int,
)
from ..schemas import AskRequest

router = APIRouter(tags=["rag"])


@router.post("/ask")
def ask(
    req: AskRequest,
    properties: HealthyProperties,
    repository: Repository,
    prompts: Prompts,
    generation: Generation,
    presenter: Presenter,
) -> dict:
    # `k` vem do corpo, então esta parte não pode vir por Depends: a facade
    # depende da requisição. Montagem explícita, como nos entrypoints de CLI.
    facade = QueryFacade(
        retrieval=RetrievalService(repository, k=read_int(req.options, "k", 4)),
        prompts=prompts,
        generation=generation,
    )
    facade.open_index(properties.collection)
    return presenter.answer(facade.ask(req.question))
