"""Rotas de introspecção: o backend se descreve.

`/health` e `/capabilities` estão juntos porque compartilham a natureza: são
GET sem corpo, sem efeito colateral, e nenhum dos dois usa facade. O frontend
chama os dois ao conectar.
"""

from fastapi import APIRouter

from ..dependencies import HealthyProperties, Repository
from ..descriptor import CAPABILITIES, PROJECT

router = APIRouter(tags=["meta"])


@router.get("/health")
def health(properties: HealthyProperties, repository: Repository) -> dict:
    """Serviço de pé e índice com conteúdo.

    O `HealthyProperties` já verificou o Chroma; se ele estiver parado, a
    requisição nem chega aqui: vira 503 no error_handler.
    """
    return {
        "status": "ok",
        "project": PROJECT,
        "collection": properties.collection,
        "indexed_chunks": repository.count(),
        "embedding_model": properties.embedding_model,
        "embedding_dimensions": 1536,
    }


@router.get("/capabilities")
def capabilities() -> dict:
    """Descritor estático. Não toca no Chroma nem na OpenAI, por isso não
    depende de nada: o frontend pode chamá-lo mesmo com o índice fora do ar."""
    return CAPABILITIES
