"""Caso de uso de ingestão.

Mesma regra da QueryFacade: nenhuma escrita em tela, nenhum argparse. Devolve
um IngestionReport e deixa a apresentação para quem chamou.
"""

import time
from pathlib import Path

from ..domain.models import IngestionReport
from ..repository.document_reader import DocumentReader
from ..repository.vector_repository import VectorRepository
from ..service.chunking_service import ChunkingService


class IngestionFacade:
    """Orquestra load -> split -> embed -> store."""

    def __init__(
        self,
        reader: DocumentReader,
        chunking: ChunkingService,
        repository: VectorRepository,
        chunk_size: int,
        chunk_overlap: int,
    ) -> None:
        self._reader = reader
        self._chunking = chunking
        self._repository = repository
        self._chunk_size = chunk_size
        self._chunk_overlap = chunk_overlap

    def files(self) -> list[Path]:
        """Os arquivos que serão indexados, antes de qualquer trabalho.

        Exposto separadamente de propósito: o chamador lista o que vai entrar
        no índice antes de a ingestão começar. É a mitigação do risco do
        ADR-004, porque torna visível um corpus de controle indexado por engano.
        """
        return self._reader.files()

    def ingest(self) -> IngestionReport:
        """Indexa o corpus, recriando a coleção.

        A coleção é apagada ANTES da leitura dos arquivos. Se a leitura falhar
        depois disso, o resultado é ficar sem índice: ruidoso e óbvio. Na ordem
        inversa, uma falha parcial deixaria o índice antigo intacto e daria a
        impressão de que a reindexação funcionou.
        """
        started = time.perf_counter()

        previous = self._repository.recreate()
        pages, discarded = self._reader.read()
        chunks = self._chunking.split(pages)
        self._repository.add(chunks)

        return IngestionReport(
            pages=len(pages),
            chunks=len(chunks),
            discarded_pages=discarded,
            previous_chunks=previous,
            chunk_size=self._chunk_size,
            chunk_overlap=self._chunk_overlap,
            seconds=time.perf_counter() - started,
        )
