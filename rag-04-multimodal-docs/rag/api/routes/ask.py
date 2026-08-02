"""POST /ask — pergunta ao corpus multimodal.

A rota faz três coisas: valida a borda, monta a facade que depende dos
parâmetros do corpo, e apresenta. **Nenhuma lógica de RAG aqui.**

A ORDEM das quatro primeiras linhas do corpo da função é a matriz de erros da
seção 6 do FDD executável, e ela é do mais barato para o mais caro:

1. pergunta vazia -> 422, sem tocar em nada;
2. `k` de tipo errado -> 422, sem tocar em nada;
3. `k` fora de 1 a 20 -> 422, na construção do `RetrievalService`;
4. índice vazio -> 409, uma consulta local ao Chroma;

e só depois disso a primeira chamada PAGA (a embedagem da pergunta) acontece.
"""

from fastapi import APIRouter

from ...config import DEFAULT_K
from ...exceptions import InvalidParameterException
from ...facade.query_facade import QueryFacade
from ...presenter.console_reporter import ConsoleReporter
from ...service.prompt_builder import PromptBuilder
from ...service.retrieval.retrieval_service import RetrievalService
from ..dependencies import (
    Docstore,
    Generation,
    Presenter,
    Properties,
    Vectors,
    read_int,
)
from ..schemas import AskRequest

router = APIRouter()


@router.post("/ask")
def ask(
    body: AskRequest,
    properties: Properties,
    docstore: Docstore,
    vectors: Vectors,
    generation: Generation,
    presenter: Presenter,
) -> dict:
    """Responde a pergunta e devolve o `Answer` da 1.3.0.

    A facade é montada aqui, e não injetada, porque `k` chega em `options`: é
    exatamente o caso que a regra 2.5 da guideline separa (container para o
    estável, construção explícita para o que vem da requisição).

    O log de estágio vai para o `ConsoleReporter` (stderr do servidor). É onde
    aparece a evidência do critério de sucesso do guia: o tamanho do contexto e
    quantas tabelas em HTML entraram nele.
    """
    if not body.question.strip():
        # Validado aqui, e não no modelo Pydantic: o 422 precisa sair no formato
        # `Problem` do contrato, e o erro de validação do framework não sai.
        raise InvalidParameterException(
            "a pergunta não pode ser vazia."
        )

    k = read_int(body.options, "k", DEFAULT_K)

    log = ConsoleReporter()
    facade = QueryFacade(
        retrieval=RetrievalService(vectors, docstore, k=k, log=log),
        prompts=PromptBuilder(log=log),
        generation=generation,
        log=log,
    )

    # Antes de qualquer chamada paga: índice vazio é 409, e não uma resposta
    # vazia que custou uma embedagem e uma geração.
    facade.open_index(properties.collection)

    return presenter.answer(facade.ask(body.question))
