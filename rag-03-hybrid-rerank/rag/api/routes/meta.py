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
    """O serviço está de pé, o índice tem conteúdo, e ele SERVE?

    Distingue os três, e a distinção é o ponto. "Motor fora do ar" e "índice
    vazio" produzem sintomas parecidos na consulta, e confundi-los custa uma
    tarde de depuração no lugar errado.

    O terceiro caso é novo neste projeto e é o mais perigoso, porque não produz
    sintoma nenhum: um índice no ar, populado, e com o campo de texto mapeado
    sem análise de termos. A busca léxica devolve vazio em silêncio, metade do
    funil híbrido morre, e a conclusão registrada seria "a busca híbrida não
    ajudou" quando a verdade é que ela nunca rodou.

    `HealthyProperties` já falhou com 503 se o motor não respondeu, ou se o
    cluster está vermelho. Chegar aqui significa que ele responde.
    """
    indexed = repository.count()
    analyzed = repository.text_field_analyzed()
    body = {
        # `degraded` cobre os dois modos de o índice não servir: vazio, e
        # presente mas inutilizável para busca léxica. São situações diferentes,
        # e por isso `text_field_analyzed` viaja ao lado: sem ele, um índice
        # cheio e quebrado apareceria como saudável.
        "status": "ok" if indexed and analyzed is not False else "degraded",
        "project": CAPABILITIES["project"],
        "collection": properties.collection,
        "indexed_chunks": indexed,
        "embedding_model": properties.embedding_model,
        # A dimensão real do índice, quando ele existe, e não a configurada:
        # é a divergência entre as duas que causa o erro obscuro de dimensão, e
        # reportar a configurada esconderia exatamente o que se quer ver.
        "embedding_dimensions": repository.vector_size()
        or properties.embedding_dimensions,
    }
    if analyzed is not None:
        body["text_field_analyzed"] = analyzed
    return body


@router.get("/capabilities")
def capabilities() -> dict:
    """O que este backend sabe fazer e quais parâmetros aceita.

    Sem dependência nenhuma, de propósito: o frontend precisa poder descobrir a
    forma da interface mesmo com o Qdrant fora do ar. Exigir infraestrutura
    aqui deixaria a tela em branco quando ela deveria mostrar "backend no ar,
    índice indisponível".
    """
    return CAPABILITIES
