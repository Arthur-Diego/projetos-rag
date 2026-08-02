"""Construção dos clientes da OpenAI, num lugar só.

Não é uma camada nem uma classe: são duas funções que concentram os parâmetros
de resiliência (timeout e retries) para que eles não sejam esquecidos em um dos
pontos de construção. São três consumidores — o resumidor de tabelas, o
descritor de imagens e o embedador —, e três construções soltas divergiriam no
dia em que o timeout mudasse.

Retries com backoff exponencial ficam SÓ nas chamadas da OpenAI, como manda a
seção 6 do FDD: o Chroma é local e uma falha dele é o container fora do ar, que
retry nenhum conserta.

A geração (task_04) reaproveita `create_chat_model`.
"""

from langchain_core.embeddings import Embeddings
from langchain_core.language_models import BaseChatModel
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

from ..config import RagProperties


def create_embeddings(properties: RagProperties) -> Embeddings:
    """O embedador das REPRESENTAÇÕES.

    Devolve a interface `Embeddings` do LangChain, não a classe concreta: é ela
    que o `ChromaVectorRepository` declara, e é o que permite trocar o provedor
    sem tocar no repositório.
    """
    return OpenAIEmbeddings(
        model=properties.embedding_model,
        api_key=properties.openai_api_key,  # type: ignore[arg-type]
        max_retries=properties.max_retries,
        timeout=properties.request_timeout_s,
    )


def create_chat_model(properties: RagProperties, model: str) -> BaseChatModel:
    """Um cliente de chat pelo NOME do modelo.

    O nome chega por parâmetro porque os dois usos divergem no `.env`: o resumo
    de tabela usa `chat_model` e a descrição de imagem usa `vision_model`. Hoje
    são o mesmo `gpt-4o-mini`, mas o ADR-006 prevê a troca do descritor por um
    modelo local, e fixar um nome aqui apagaria o ponto de troca.

    `temperature=0`: resumo e descrição alimentam um ÍNDICE. Variação entre
    execuções mudaria a representação de conteúdo idêntico e faria a mesma
    tabela ser recuperada por perguntas diferentes a cada reingestão.
    """
    return ChatOpenAI(
        model=model,
        api_key=properties.openai_api_key,  # type: ignore[arg-type]
        temperature=properties.temperature,
        max_retries=properties.max_retries,
        timeout=properties.request_timeout_s,
    )
