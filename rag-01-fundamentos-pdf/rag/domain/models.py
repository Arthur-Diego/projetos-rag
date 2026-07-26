"""Objetos de domínio.

Note que não se chamam Entity: entidade implica identidade e ciclo de vida
persistido. Estes são objetos de valor, definidos apenas pelo conteúdo.

Os dois relatórios (Answer e IngestionReport) existem para que as facades
devolvam DADOS em vez de escreverem na tela. É o que permite ao mesmo caso de
uso servir uma CLI hoje e uma API HTTP amanhã.
"""

from typing import NamedTuple

from langchain_core.documents import Document


class SearchHit(NamedTuple):
    """Um chunk recuperado e sua DISTÂNCIA até a pergunta.

    Menor é mais próximo, não maior. O Chroma devolve L2 ao quadrado; como os
    embeddings da OpenAI são unitários, isso equivale a 2 x (1 - cosseno).
    Escala: 0 = idêntico, 2 = ortogonal, 4 = oposto.

    NamedTuple para continuar desempacotável como tupla (`doc, dist = hit`)
    e ao mesmo tempo legível por atributo (`hit.distance`).
    """

    document: Document
    distance: float


class Answer(NamedTuple):
    """Resultado de uma consulta, com a evidência que a torna verificável.

    Carrega os trechos usados e a latência de cada estágio porque, sem isso,
    não se distingue falha de recuperação de falha de geração, que é o objetivo
    declarado do projeto.
    """

    text: str
    hits: list[SearchHit]
    search_s: float
    generation_s: float


class IngestionReport(NamedTuple):
    """Resultado de uma indexação.

    `previous_chunks` maior que zero significa que havia coleção anterior e ela
    foi apagada. Recriar é decisão de desenho: acrescentar geraria duplicatas.
    """

    pages: int
    chunks: int
    discarded_pages: int
    previous_chunks: int
    chunk_size: int
    chunk_overlap: int
    seconds: float
