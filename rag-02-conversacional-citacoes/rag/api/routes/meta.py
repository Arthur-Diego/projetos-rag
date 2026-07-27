"""GET /health e GET /capabilities.

As duas rotas que o frontend chama antes de habilitar a interface. Baratas e
sem efeito colateral: nenhuma delas gasta chamada paga.
"""

from fastapi import APIRouter

from ..dependencies import HealthyProperties, Repository
from ..descriptor import CAPABILITIES

router = APIRouter()


@router.get("/health")
def health(properties: HealthyProperties, repository: Repository) -> dict:
    """O serviço está de pé e o índice tem conteúdo?

    Distingue os dois, e a distinção é o ponto: "Qdrant fora do ar" e "índice
    vazio" produzem sintomas parecidos na consulta, e confundi-los custa uma
    tarde de depuração no lugar errado.

    `HealthyProperties` já falhou com 503 se o Qdrant não respondeu. Chegar
    aqui significa que ele responde; o que resta é dizer se há o que consultar.
    """
    indexed = repository.count()
    return {
        "status": "ok" if indexed else "degraded",
        "project": CAPABILITIES["project"],
        "collection": properties.collection,
        "indexed_chunks": indexed,
        "embedding_model": properties.embedding_model,
        # A dimensão real da coleção, quando ela existe, e não a configurada:
        # é a divergência entre as duas que causa o erro obscuro de dimensão, e
        # reportar a configurada esconderia exatamente o que se quer ver.
        "embedding_dimensions": repository.vector_size()
        or properties.embedding_dimensions,
    }


@router.get("/capabilities")
def capabilities() -> dict:
    """O que este backend sabe fazer e quais parâmetros aceita.

    Sem dependência nenhuma, de propósito: o frontend precisa poder descobrir a
    forma da interface mesmo com o Qdrant fora do ar. Exigir infraestrutura
    aqui deixaria a tela em branco quando ela deveria mostrar "backend no ar,
    índice indisponível".
    """
    return CAPABILITIES
