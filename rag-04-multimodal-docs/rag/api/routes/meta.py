"""GET /health e GET /capabilities.

As duas rotas que o frontend chama antes de habilitar a interface. Baratas e sem
efeito colateral: nenhuma delas gasta chamada paga.
"""

from fastapi import APIRouter

from ...service.health_checker import STATUS_DEGRADED, STATUS_OK, HealthChecker
from ..dependencies import Docstore, HealthyProperties, Vectors
from ..descriptor import CAPABILITIES

router = APIRouter()


@router.get("/health")
def health(
    properties: HealthyProperties, vectors: Vectors, docstore: Docstore
) -> dict:
    """O Chroma responde, o docstore responde, e os dois CONCORDAM?

    As três perguntas são distintas e a terceira é a que este projeto acrescenta.
    "Container fora do ar" e "índice vazio" produzem sintomas parecidos na
    consulta, e confundi-los custa uma tarde de depuração no lugar errado — mas
    o caso realmente perigoso é o terceiro, porque não produz sintoma nenhum:
    dois armazéns no ar, populados, e com contagens diferentes. Cada `doc_id`
    sobrando no índice é uma fonte que a consulta descarta em silêncio (risco 4
    do FDD).

    `HealthyProperties` já falhou com 503 se o Chroma não respondeu. Chegar aqui
    significa que ele responde — e por isso a dessincronia é **200 com
    `degraded`**, nunca erro: o serviço está de pé e o relatório é o produto
    desta rota.

    `docstore_originals` é o nome publicado na 1.3.0 (task_02). Ele vale CONTRA
    `indexed_chunks`: é a comparação dos dois que denuncia o órfão.
    """
    indexed = vectors.count()
    try:
        originals: int | None = docstore.count()
    except OSError:
        # Docstore inacessível (permissão, disco) é `degraded` com evidência,
        # nunca 500: a seção 5 do FDD reserva o `degraded` exatamente para
        # isto, e o serviço está de pé — o relatório é o produto desta rota.
        originals = None

    if originals is None:
        evidence: str | None = (
            f"o docstore em '{properties.docstore_dir}' não respondeu à "
            "contagem. Sem ele nenhum original é resolvível: todo hit da "
            "consulta seria descartado. Confira permissão e disco."
        )
    else:
        evidence = HealthChecker(properties).synchrony(indexed, originals)

    body = {
        "status": STATUS_OK if evidence is None else STATUS_DEGRADED,
        "project": CAPABILITIES["project"],
        "collection": properties.collection,
        "indexed_chunks": indexed,
        "embedding_model": properties.embedding_model,
        "embedding_dimensions": properties.embedding_dimensions,
    }
    if originals is not None:
        body["docstore_originals"] = originals
    if evidence is not None:
        # A evidência é o que separa um diagnóstico de um adjetivo. `degraded`
        # sozinho não diz qual lado está sobrando, e a receita muda conforme
        # isso: índice sobrando pede reset, docstore sobrando pede reingestão.
        body["degraded_reason"] = evidence
    return body


@router.get("/capabilities")
def capabilities() -> dict:
    """O que este backend sabe fazer e quais parâmetros aceita.

    Sem dependência nenhuma, de propósito: o frontend precisa poder descobrir a
    forma da interface mesmo com o Chroma fora do ar. Exigir infraestrutura aqui
    deixaria a tela em branco quando ela deveria mostrar "backend no ar, índice
    indisponível".
    """
    return CAPABILITIES
