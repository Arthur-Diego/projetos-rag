"""Divisão dos documentos em pedaços indexáveis.

Uma responsabilidade: transformar páginas em chunks preservando a procedência.
Se `source` e `page` se perderem aqui, `Citation` deixa de ser verificável e o
projeto inteiro perde o sentido.
"""

from typing import Protocol

from langchain_text_splitters import RecursiveCharacterTextSplitter

from ..config import MAX_CHUNK_OVERLAP, MAX_CHUNK_SIZE, MIN_CHUNK_SIZE
from ..domain.models import Chunk, Page
from ..exceptions import InvalidParameterException


class ChunkingService(Protocol):
    """Contrato de qualquer estratégia de divisão."""

    def split(self, pages: list[Page]) -> list[Chunk]:
        ...


class RecursiveChunkingService:
    """Divisão recursiva por separadores, do mais forte ao mais fraco.

    Tenta quebrar em parágrafo; se o pedaço ainda passa do tamanho, tenta
    linha, depois frase, depois palavra. É o que evita cortar no meio de uma
    palavra quando dá para cortar no meio de um parágrafo.

    Em texto normativo isso importa mais que em narrativa: um artigo cortado ao
    meio produz dois chunks que, isolados, dizem coisas diferentes do que o
    artigo diz.
    """

    def __init__(self, chunk_size: int = 1000, chunk_overlap: int = 150) -> None:
        # As faixas são as mesmas declaradas em /capabilities. Declarar um
        # limite lá e não impô-lo aqui faria do descritor uma sugestão.
        if not MIN_CHUNK_SIZE <= chunk_size <= MAX_CHUNK_SIZE:
            raise InvalidParameterException(
                f"chunk_size deve estar entre {MIN_CHUNK_SIZE} e {MAX_CHUNK_SIZE} "
                f"(recebido: {chunk_size})."
            )
        if not 0 <= chunk_overlap <= MAX_CHUNK_OVERLAP:
            raise InvalidParameterException(
                f"chunk_overlap deve estar entre 0 e {MAX_CHUNK_OVERLAP} "
                f"(recebido: {chunk_overlap})."
            )
        if chunk_overlap >= chunk_size:
            # Sobreposição maior que o pedaço faria cada chunk conter o
            # anterior inteiro: o índice cresce sem acrescentar informação.
            raise InvalidParameterException(
                f"chunk_overlap ({chunk_overlap}) deve ser menor que "
                f"chunk_size ({chunk_size})."
            )

        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self._splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )

    def split(self, pages: list[Page]) -> list[Chunk]:
        chunks: list[Chunk] = []
        for page in pages:
            for piece in self._splitter.split_text(page.text):
                chunks.append(
                    Chunk(text=piece, source=page.source, page=page.number)
                )
        return chunks
