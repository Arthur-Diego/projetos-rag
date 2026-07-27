"""Caso de uso de indexação.

Mesmas regras da QueryFacade: nada de terminal aqui dentro. Recebe nada, devolve
um `IngestionReport`, e quem apresenta decide como mostrar.
"""

import time

from ..domain.models import IngestionReport
from ..exceptions import EmptyCorpusException, NoExtractableTextException
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

        **A ORDEM É DELIBERADA, e o motivo é herdado do Projeto 1.**

        A coleção é apagada ANTES da leitura. Se a leitura ou a divisão falhar
        depois disso, o resultado é ficar sem índice: a próxima consulta devolve
        409 "rode python ingest.py", que é ruidoso e óbvio.

        Na ordem inversa (dividir primeiro, recriar depois), uma falha deixaria
        o índice ANTIGO intacto, e a próxima consulta responderia com dados
        velhos sem nenhum sintoma. Uma versão anterior deste arquivo fazia
        exatamente isso, contrariando a decisão documentada do Projeto 1 sem
        registrá-la. Falhar barulhento vale mais que preservar dado obsoleto.

        A única coisa checada ANTES de destruir é a existência de PDFs, que é
        barata e não depende de conseguir ler nenhum deles: destruir o índice
        porque alguém rodou com a pasta vazia seria punição sem informação.

        Raises:
            EmptyCorpusException: se não há PDF em pdfs/. Índice preservado.
            NoExtractableTextException: se nenhuma página rendeu texto.
        """
        started = time.perf_counter()

        if not self._reader.files():
            raise EmptyCorpusException(
                f"nenhum PDF para indexar.\n"
                "       o índice atual foi PRESERVADO: nada foi apagado."
            )

        previous = self._repository.recreate(self._dimensions)

        # A partir daqui, qualquer falha deixa o índice vazio, de propósito.
        pages, discarded = self._reader.read()
        if not pages:
            raise NoExtractableTextException(
                "os PDFs não produziram texto extraível.\n"
                "       quase sempre é PDF escaneado: imagem sem camada de texto.\n"
                "       OCR está fora do escopo deste projeto (entra no Projeto 4).\n"
                "       o índice ficou VAZIO: rode de novo com um corpus legível."
            )

        chunks = self._chunking.split(pages)
        self._repository.add(chunks)

        return IngestionReport(
            pages=len(pages),
            chunks=len(chunks),
            discarded_pages=discarded,
            previous_chunks=previous,
            chunk_size=self._chunking.chunk_size,
            chunk_overlap=self._chunking.chunk_overlap,
            seconds=time.perf_counter() - started,
        )
