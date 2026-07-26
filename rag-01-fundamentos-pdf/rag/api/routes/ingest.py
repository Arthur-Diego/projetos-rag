"""Rota de indexação.

Operação cara e destrutiva: apaga a coleção anterior. O frontend confirma antes
de chamar; aqui não há confirmação, por desenho — uma API não pergunta.
"""

from fastapi import APIRouter

from ...facade.ingestion_facade import IngestionFacade
from ...repository.document_reader import PdfDocumentReader
from ...service.chunking_service import RecursiveChunkingService
from ..dependencies import HealthyProperties, Presenter, Repository, read_int
from ..schemas import IngestRequest

router = APIRouter(tags=["rag"])


@router.post("/ingest")
def ingest(
    req: IngestRequest,
    properties: HealthyProperties,
    repository: Repository,
    presenter: Presenter,
) -> dict:
    size = read_int(req.options, "chunk_size", 1000)
    overlap = read_int(req.options, "chunk_overlap", 150)

    facade = IngestionFacade(
        reader=PdfDocumentReader(properties.pdf_dir),
        # Valida overlap < size na construção. Falha antes de ler qualquer PDF,
        # e a exceção vira 422 no error_handler.
        chunking=RecursiveChunkingService(size, overlap),
        repository=repository,
        chunk_size=size,
        chunk_overlap=overlap,
    )
    return presenter.ingestion(facade.ingest())
