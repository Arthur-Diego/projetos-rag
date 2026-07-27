"""Caso de uso de indexação.

Mesmas regras da QueryFacade: nada de terminal aqui dentro. Recebe nada, devolve
um `IngestionReport`, e quem apresenta decide como mostrar.
"""

import time

from ..domain.models import IngestionReport
from ..exceptions import NoExtractableTextException
from ..repository.document_reader import DocumentReader
from ..repository.vector_repository import VectorRepository
from ..service.chunking_service import RecursiveChunkingService


class IngestionFacade:
    """Orquestra ler -> dividir -> recriar -> gravar."""

    def __init__(
        self,
        reader: DocumentReader,
        chunking: RecursiveChunkingService,
        repository: VectorRepository,
        dimensions: int,
    ) -> None:
        self._reader = reader
        self._chunking = chunking
        self._repository = repository
        self._dimensions = dimensions

    def files(self) -> list[str]:
        """O que SERÁ indexado, antes de indexar.

        Exposto separado de `ingest()` porque o chamador precisa ver a lista
        antes do trabalho começar. É a mitigação do risco do glob: um PDF do
        corpus de controle indexado por engano aparece aqui, em vez de ser
        descoberto quando o teste negativo parar de falhar.
        """
        return [path.name for path in self._reader.files()]

    def ingest(self) -> IngestionReport:
        """Recria a coleção e indexa o corpus.

        Recriar, e não acrescentar: rodar duas vezes sem recriar produziria
        duplicatas, e duplicata em índice vetorial é pior que ausência, porque
        ocupa vaga entre os k mais próximos com o mesmo conteúdo.

        Raises:
            EmptyCorpusException: se não há PDF em pdfs/.
            NoExtractableTextException: se nenhuma página rendeu texto.
        """
        started = time.perf_counter()

        total_pages = self._reader.total_pages()
        pages = self._reader.read()
        if not pages:
            raise NoExtractableTextException(
                "os PDFs não produziram texto extraível.\n"
                "       quase sempre é PDF escaneado: imagem sem camada de texto.\n"
                "       OCR está fora do escopo deste projeto (entra no Projeto 4)."
            )

        chunks = self._chunking.split(pages)
        previous = self._repository.recreate(self._dimensions)
        self._repository.add(chunks)

        return IngestionReport(
            pages=len(pages),
            chunks=len(chunks),
            discarded_pages=total_pages - len(pages),
            previous_chunks=previous,
            chunk_size=self._chunking.chunk_size,
            chunk_overlap=self._chunking.chunk_overlap,
            seconds=time.perf_counter() - started,
        )
