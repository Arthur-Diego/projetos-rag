"""POST /ingest — ingere o corpus multimodal, reconciliando.

**Esta rota NÃO é destrutiva, e é a exceção que a 1.3.0 declarou.** O contrato
descreve `/ingest` como "cara e destrutiva: apaga o índice anterior", e nos
projetos 1 a 3 era. Aqui a ingestão é idempotente: reprocessa o que mudou,
preserva o que não mudou e não apaga nada. Zerar os armazéns é operação
separada, por script CLI (task_04). O motivo está no ADR-003: recriar do zero
repagaria minutos de `hi_res` e uma chamada por tabela e por imagem.

Cara ela continua sendo: a primeira execução leva minutos.
"""

from fastapi import APIRouter

from ...config import DEFAULT_DESCREVER_IMAGENS
from ...facade.ingestion_facade import IngestionFacade
from ...presenter.console_reporter import ConsoleReporter
from ...repository.corpus_reader import PdfCorpusReader
from ...repository.pdf_partitioner import FilePartitionCache, UnstructuredPartitioner
from ...service.enrichment_service import EnrichmentService
from ...service.image_description_service import OpenAiImageDescriptionService
from ...service.indexing_service import IndexingService
from ...service.partition_service import PartitionService
from ...service.routing_service import ElementRoutingService
from ...service.table_summary_service import TableSummaryService
from ..dependencies import (
    Docstore,
    Presenter,
    Properties,
    Vectors,
    chat_model_for,
    read_bool,
)
from ..schemas import IngestRequest

router = APIRouter()


@router.post("/ingest")
def ingest(
    properties: Properties,
    docstore: Docstore,
    vectors: Vectors,
    presenter: Presenter,
    # Corpo OPCIONAL, e o `= None` é exigência do contrato: a 1.3.0 declara
    # `requestBody: required: false`. Com o corpo obrigatório na assinatura, uma
    # chamada sem corpo é recusada pelo PYDANTIC, antes do error handler, e a
    # resposta sai no formato dele em vez do `Problem` do contrato — o cliente
    # cai no ramo degradado e mostra "HTTP 422" sem explicação.
    #
    # Fica por último na assinatura porque é o único parâmetro com valor padrão.
    body: IngestRequest | None = None,
) -> dict:
    """Ingere o corpus e devolve o `IngestionReport` da 1.3.0.

    A facade é montada aqui, e não injetada, porque `descrever_imagens` chega no
    corpo: é exatamente o caso que a regra 2.5 da guideline separa.

    O log de estágio vai para o `ConsoleReporter` (stderr do servidor). Numa
    operação que leva minutos, um processo silencioso é indistinguível de um
    processo travado, e o cliente HTTP só vê o resultado no fim.
    """
    options = body.options if body is not None else {}
    descrever_imagens = read_bool(
        options, "descrever_imagens", DEFAULT_DESCREVER_IMAGENS
    )

    log = ConsoleReporter()
    facade = IngestionFacade(
        reader=PdfCorpusReader(properties.pdf_dir),
        partition=PartitionService(
            partitioner=UnstructuredPartitioner(
                properties.partition_strategy, properties.figures_dir
            ),
            cache=FilePartitionCache(
                properties.partition_cache_dir, properties.partition_strategy
            ),
            log=log,
        ),
        routing=ElementRoutingService(properties.figures_dir, log=log),
        docstore=docstore,
        vectors=vectors,
        enrichment=EnrichmentService(
            summaries=TableSummaryService(
                chat_model_for(properties, properties.chat_model)
            ),
            descriptions=OpenAiImageDescriptionService(
                chat_model_for(properties, properties.vision_model)
            ),
            log=log,
        ),
        indexing=IndexingService(docstore, vectors, log=log),
        log=log,
    )
    return presenter.ingestion(facade.ingest(descrever_imagens))
