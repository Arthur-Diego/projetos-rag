"""Divisão dos documentos em chunks.

O parâmetro que mais afeta a qualidade de um RAG e o que menos se discute.
Ver a seção 12 do FDD para a medição feita neste corpus.
"""

from typing import Protocol

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from ..exceptions import InvalidConfigurationException


class ChunkingService(Protocol):
    """Contrato de qualquer estratégia de divisão."""

    def split(self, documents: list[Document]) -> list[Document]:
        ...


class RecursiveChunkingService:
    """Quebra em parágrafo; se ainda for grande, em frase; depois em palavra.

    Respeita a estrutura do texto em vez de cortar a cada N caracteres
    cegamente. Os metadados da página de origem são herdados por cada chunk,
    o que é o que torna a citação possível depois.

    Atenção: a divisão acontece POR DOCUMENTO, e o reader entrega um Document
    por página. Logo nenhum chunk atravessa a virada de página, e a sobreposição
    zera na fronteira.
    """

    def __init__(self, size: int = 1000, overlap: int = 150) -> None:
        if overlap >= size:
            raise InvalidConfigurationException(
                f"--chunk-overlap ({overlap}) deve ser menor que "
                f"--chunk-size ({size})."
            )
        self.size = size
        self.overlap = overlap
        self._splitter = RecursiveCharacterTextSplitter(
            chunk_size=size,
            chunk_overlap=overlap,
        )

    def split(self, documents: list[Document]) -> list[Document]:
        return self._splitter.split_documents(documents)
