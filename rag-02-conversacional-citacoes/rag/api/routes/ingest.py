"""POST /ingest — indexa o corpus, recriando a coleção.

Operação cara e destrutiva: apaga o índice anterior. O contrato instrui o
frontend a confirmar antes de chamar.

Declara `Repository`, não `CheckedRepository`: a ingestão recria a coleção com
a dimensão do modelo atual, então a dimensão da coleção antiga não importa.
Conferi-la aqui recusaria justamente a operação que conserta o problema.
"""

from fastapi import APIRouter

from ...config import DEFAULT_CHUNK_OVERLAP, DEFAULT_CHUNK_SIZE
from ...facade.ingestion_facade import IngestionFacade
from ...repository.document_reader import PdfDocumentReader
from ...service.chunking_service import RecursiveChunkingService
from ..dependencies import HealthyProperties, Presenter, Repository, read_int
from ..schemas import IngestRequest

router = APIRouter()


@router.post("/ingest")
def ingest(
    body: IngestRequest,
    properties: HealthyProperties,
    repository: Repository,
    presenter: Presenter,
) -> dict:
    chunk_size = read_int(body.options, "chunk_size", DEFAULT_CHUNK_SIZE)
    chunk_overlap = read_int(body.options, "chunk_overlap", DEFAULT_CHUNK_OVERLAP)

    facade = IngestionFacade(
        reader=PdfDocumentReader(properties.pdf_dir),
        # Validação de overlap contra size acontece na construção do serviço, e
        # vira 422 pelo error handler. Antes de ler um único PDF.
        chunking=RecursiveChunkingService(chunk_size, chunk_overlap),
        repository=repository,
        dimensions=properties.embedding_dimensions,
    )
    return presenter.ingestion(facade.ingest())
