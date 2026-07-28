"""Provedores de dependência da camada HTTP.

Dois modelos de injeção convivem neste projeto, e a regra entre eles é a da
seção 2.5 da guideline de arquitetura: **container para o que é estável,
construção explícita para o que depende da requisição.**

As CLIs montam tudo à mão em `composition.py`. Aqui o container do FastAPI
resolve o que é estável, e a cadeia `Properties -> HealthyProperties ->
Repository` dá um ganho que a montagem manual não tem: se `HealthyProperties`
já rodou o verificador, toda rota que a declarar herda a verificação, e uma
rota nova não pode esquecer de checar.

O que **não** vem por `Depends`: `k`, `history_window`, `conditional_rewrite`,
`chunk_size`. Chegam em `options`, então as facades que os usam são montadas na
própria rota.
"""

from typing import Annotated

from elasticsearch import Elasticsearch
from fastapi import Depends

from .. import config
from ..config import RagProperties
from ..domain.models import Conversation, Turn
from ..exceptions import InvalidParameterException
from ..presenter.json_presenter import JsonPresenter
from ..repository.keyword_repository import (
    ElasticKeywordRepository,
    KeywordRepository,
)
from ..repository.vector_repository import (
    ElasticVectorRepository,
    VectorRepository,
)
from ..service.citation_resolver import CitationResolver
from ..service.generation_service import (
    GenerationService,
    OpenAiGenerationService,
    create_embeddings,
)
from ..service.retrieval.fusion_service import FusionService
from ..service.health_checker import HealthChecker
from ..service.prompt_builder import PromptBuilder
from ..service.retrieval.rerank_service import CrossEncoderRerankService, RerankService


#: Clientes do Elasticsearch por endereço. Ver `_client`.
_CLIENTS: dict[str, Elasticsearch] = {}


def provide_properties() -> RagProperties:
    """Recarrega a cada requisição: o .env pode mudar sem reiniciar o servidor."""
    return config.load()


Properties = Annotated[RagProperties, Depends(provide_properties)]


def provide_healthy_properties(properties: Properties) -> RagProperties:
    """Propriedades, com o Elasticsearch já verificado."""
    HealthChecker(properties).check()
    return properties


HealthyProperties = Annotated[RagProperties, Depends(provide_healthy_properties)]


def _client(properties: RagProperties) -> Elasticsearch:
    """Cliente do motor, um por processo e por endereço.

    **Cache de processo, e ele não é opcional.** `provide_properties` roda a cada
    requisição, então um cliente construído aqui sem cache abriria um pool de
    conexões novo por `/ask`. É a mesma classe de defeito que o cache do vector
    store corrigiu no Projeto 2, onde o comentário diz "isto não é
    micro-otimização; é dinheiro".

    Os DOIS repositórios compartilham este cliente: eles falam com o mesmo
    container, sobre o mesmo índice (ADR-001).
    """
    key = properties.elastic_url
    if key not in _CLIENTS:
        _CLIENTS[key] = Elasticsearch(
            key, request_timeout=properties.request_timeout_s
        )
    return _CLIENTS[key]


def provide_repository(properties: HealthyProperties) -> VectorRepository:
    """Trocar de armazém mexe aqui e em `composition.build_repository`.

    Dois lugares, não um, e é o preço registrado de ter dois modelos de injeção.
    """
    return ElasticVectorRepository(
        client=_client(properties),
        index=properties.collection,
        embeddings=create_embeddings(
            properties.embedding_model,
            properties.max_retries,
            properties.request_timeout_s,
        ),
    )


def provide_keywords(properties: HealthyProperties) -> KeywordRepository:
    """O caminho léxico. Mesmo cliente, mesmo índice, mesmo documento."""
    return ElasticKeywordRepository(
        client=_client(properties), index=properties.collection
    )


Keywords = Annotated[KeywordRepository, Depends(provide_keywords)]

Fusion = Annotated[FusionService, Depends(FusionService)]


def provide_reranker(properties: Properties) -> RerankService:
    """O reordenador.

    Declara `Properties` e não `HealthyProperties` de propósito: carregar o
    modelo não depende do motor de busca estar no ar, e acoplar as duas coisas
    faria um Elasticsearch fora do ar impedir até o diagnóstico do reranker.

    O modelo em si é cacheado dentro do serviço, por nome, em nível de módulo.
    Sem isso, meio gigabyte seria carregado a cada requisição.
    """
    return CrossEncoderRerankService(properties.reranker_model)


Reranker = Annotated[RerankService, Depends(provide_reranker)]


Repository = Annotated[VectorRepository, Depends(provide_repository)]


def provide_checked_repository(
    properties: HealthyProperties, repository: Repository
) -> VectorRepository:
    """Repositório com a dimensão do índice já conferida contra o modelo.

    Separado de `provide_repository` porque a conferência precisa do
    repositório pronto. Rotas que tocam o índice declaram esta; a ingestão
    declara a anterior, já que ela recria o índice e a dimensão antiga não
    importa.

    **A conferência de MAPPING não entra aqui**, apesar de também precisar do
    repositório pronto. Ela depende de o caminho léxico ter sido pedido, e isso
    só se sabe ao ler `options` da requisição. Colocá-la aqui bloquearia a
    configuração puramente densa, que é a linha de base da tabela de medição.
    Quem a chama é a rota, depois de ler `hibrida`.
    """
    HealthChecker(properties).check_dimensions(repository)
    return repository


CheckedRepository = Annotated[VectorRepository, Depends(provide_checked_repository)]


def provide_generation(properties: HealthyProperties) -> GenerationService:
    return OpenAiGenerationService(
        properties.chat_model,
        properties.temperature,
        properties.max_retries,
        properties.request_timeout_s,
    )


Generation = Annotated[GenerationService, Depends(provide_generation)]

Prompts = Annotated[PromptBuilder, Depends(PromptBuilder)]
Citations = Annotated[CitationResolver, Depends(CitationResolver)]
Presenter = Annotated[JsonPresenter, Depends(JsonPresenter)]


def read_int(options: dict, key: str, default: int) -> int:
    """Lê um inteiro de `options`, caindo no default em silêncio.

    Chave desconhecida ou valor ilegível cai no default. É exigência do
    contrato: um frontend mais novo que o backend não pode quebrá-lo.

    Note a assimetria deliberada com `read_history`: valor MAL FORMADO de `k`
    é ignorado, valor mal formado de histórico é erro. A diferença é a
    consequência. Um `k` errado degrada a busca de um jeito que aparece; um
    histórico truncado em silêncio produz reescrita errada sem sintoma.
    """
    try:
        return int(options.get(key, default))
    except (TypeError, ValueError):
        return default


def read_bool(options: dict, key: str, default: bool) -> bool:
    value = options.get(key, default)
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "sim", "yes"}
    return default


def read_history(options: dict) -> Conversation:
    """Constrói a conversa a partir de `options.history`.

    **Turno malformado é 422, nunca descarte silencioso.** Um histórico
    parcialmente perdido produz uma reescrita que resolve o pronome contra a
    referência errada: a pergunta reescrita sai bem formada, sobre o assunto
    errado, e nada denuncia. Falhar alto aqui é mais barato que diagnosticar
    isso depois.

    Ausência de `history` é o caso normal do primeiro turno, e não é erro.
    """
    raw = options.get("history")
    if raw is None:
        return Conversation()

    if not isinstance(raw, list):
        raise InvalidParameterException(
            "options.history deve ser uma lista de turnos "
            "{question, answer}, do mais antigo para o mais recente."
        )

    turns: list[Turn] = []
    for position, item in enumerate(raw, 1):
        if not isinstance(item, dict):
            raise InvalidParameterException(
                f"turno {position} de options.history não é um objeto."
            )
        question = item.get("question")
        answer = item.get("answer")
        if not isinstance(question, str) or not isinstance(answer, str):
            raise InvalidParameterException(
                f"turno {position} de options.history precisa de 'question' e "
                "'answer', ambos texto."
            )
        turns.append(Turn(question=question, answer=answer))

    return Conversation(tuple(turns))
