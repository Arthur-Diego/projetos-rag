"""Provedores de dependência da camada HTTP.

Dois modelos de injeção convivem neste projeto, e a regra entre eles é a da
seção 2.5 da guideline: **container para o que é estável, construção explícita
para o que depende da requisição.**

As CLIs montam tudo à mão em `composition.py`. Aqui o container do FastAPI
resolve o que é estável. Os dois grafos existem em paralelo, e isso é o preço
registrado de ter dois modelos de injeção: trocar um armazém mexe em dois
lugares, não em um.

O que **não** vem por `Depends`: `descrever_imagens`. Chega em `options`, então
a facade que o usa é montada dentro da rota.
"""

from typing import Annotated

import chromadb
from chromadb.api import ClientAPI
from fastapi import Depends
from langchain_classic.storage import LocalFileStore

from .. import config
from ..config import RagProperties
from ..exceptions import InvalidParameterException
from ..presenter.json_presenter import JsonPresenter
from ..repository.docstore_repository import (
    DocstoreRepository,
    FileDocstoreRepository,
)
from ..repository.vector_repository import ChromaVectorRepository, VectorRepository
from ..service.generation_service import GenerationService, OpenAiGenerationService
from ..service.health_checker import HealthChecker
from ..service.openai_models import create_chat_model, create_embeddings

#: Clientes do Chroma por endereço. Ver `_client`.
_CLIENTS: dict[str, ClientAPI] = {}


def provide_properties() -> RagProperties:
    """Recarrega a cada requisição: o .env pode mudar sem reiniciar o servidor."""
    return config.load()


Properties = Annotated[RagProperties, Depends(provide_properties)]


def provide_healthy_properties(properties: Properties) -> RagProperties:
    """As propriedades, DEPOIS de confirmar que o Chroma responde.

    Existe para o `GET /health`, que precisa responder 503 quando o container
    está fora do ar — e não 200 com contagens que ele não conseguiu ler. A
    verificação é `urllib` puro contra o heartbeat: barata e independente do
    cliente do Chroma.

    O `POST /ask` NÃO usa esta dependência, de propósito: lá o próprio
    repositório traduz a falha em 503 na primeira chamada (`require_index`), e
    somar um heartbeat antes seria uma ida à rede a mais por consulta para
    chegar ao mesmo status.

    Raises:
        ServiceUnavailableException: vira 503 no tratador de erros.
    """
    HealthChecker(properties).check()
    return properties


HealthyProperties = Annotated[RagProperties, Depends(provide_healthy_properties)]


def _client(properties: RagProperties) -> ClientAPI:
    """Cliente do Chroma, um por processo e por endereço.

    **Cache de processo, e ele não é opcional.** `provide_properties` roda a
    cada requisição, então um cliente construído aqui sem cache abriria um pool
    de conexões novo por chamada. É a mesma lição registrada no
    `composition.py`: escopo de processo, nunca de requisição.
    """
    key = properties.chroma_url
    if key not in _CLIENTS:
        _CLIENTS[key] = chromadb.HttpClient(
            host=properties.chroma_host, port=properties.chroma_port
        )
    return _CLIENTS[key]


def provide_vectors(properties: Properties) -> VectorRepository:
    """Trocar de armazém mexe aqui e em `composition.build_vector_repository`."""
    return ChromaVectorRepository(
        client=_client(properties),
        collection=properties.collection,
        embeddings=create_embeddings(properties),
    )


Vectors = Annotated[VectorRepository, Depends(provide_vectors)]


def provide_docstore(properties: Properties) -> DocstoreRepository:
    """O armazém dos originais: a fonte de verdade (ADR-001)."""
    properties.docstore_dir.mkdir(parents=True, exist_ok=True)
    return FileDocstoreRepository(LocalFileStore(properties.docstore_dir))


Docstore = Annotated[DocstoreRepository, Depends(provide_docstore)]

Presenter = Annotated[JsonPresenter, Depends(JsonPresenter)]


def provide_generation(properties: Properties) -> GenerationService:
    """O gerador de respostas. Trocar de provedor mexe aqui e em `composition`."""
    return OpenAiGenerationService(create_chat_model(properties, properties.chat_model))


Generation = Annotated[GenerationService, Depends(provide_generation)]


def read_bool(options: dict, key: str, default: bool) -> bool:
    """Lê um booleano de `options`. Chave ausente cai no default; TIPO ERRADO é 422.

    A assimetria é exigência do contrato, não zelo: a 1.3.0 declara que "um
    parâmetro declarado boolean em `/capabilities` recebendo string ou número"
    é 422, porque o pedido é que está malformado.

    Por que não aceitar `"true"` por conveniência: `descrever_imagens` controla
    o gasto de uma chamada de VISÃO por figura. Um cliente que mandasse
    `"false"` como string e fosse tratado como default silenciosamente pagaria
    o que pediu explicitamente para não pagar, e não haveria sintoma nenhum além
    da fatura.

    Raises:
        InvalidParameterException: se a chave existe com valor não booleano.
    """
    if key not in options:
        return default
    value = options[key]
    if isinstance(value, bool):
        return value
    raise InvalidParameterException(
        f"options.{key} deve ser booleano (true ou false); "
        f"recebido {type(value).__name__} ({value!r})."
    )


def read_int(options: dict, key: str, default: int) -> int:
    """Lê um inteiro de `options`. Chave ausente cai no default; TIPO ERRADO é 422.

    Mesma assimetria de `read_bool`, e pelo mesmo motivo do contrato.

    **`bool` é recusado explicitamente**, apesar de ser subclasse de `int` em
    Python: `{"k": true}` chegaria como `k=1` e a consulta devolveria um único
    trecho sem sintoma nenhum. A faixa (1 a 20) NÃO é verificada aqui — quem a
    impõe é o `RetrievalService`, na construção, para que o limite valha também
    para as CLIs, que não passam por esta função.

    Raises:
        InvalidParameterException: se a chave existe com valor não inteiro.
    """
    if key not in options:
        return default
    value = options[key]
    if isinstance(value, bool) or not isinstance(value, int):
        raise InvalidParameterException(
            f"options.{key} deve ser um número inteiro; "
            f"recebido {type(value).__name__} ({value!r})."
        )
    return value
