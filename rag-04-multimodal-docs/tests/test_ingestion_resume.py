"""EC-1 da US-003 e EC-4 da US-001 — retomada de falha parcial e guarda de custo.

Os dois cenários que a rodada de revisão 001 encontrou sem cobertura:

- **retomada**: falha entre as duas gravações deixa docstore=N e índice=0; a
  reexecução tem que COMPLETAR o lado vetorial sem repagar enriquecimento. A
  idempotência que só consulta o docstore deixaria esse estado irrecuperável —
  a receita do `/health` ("rode de novo: ingest.py") viraria mentira.
- **guarda de custo**: Chroma inacessível descoberto ANTES do estágio pago. O
  gerador dublê conta as chamadas, porque a afirmação a provar é "não gastou".
"""

from pathlib import Path

import pytest
from unstructured.documents.elements import Element, ElementMetadata, Table

from rag.exceptions import ServiceUnavailableException
from rag.facade.ingestion_facade import IngestionFacade
from rag.repository.pdf_partitioner import FilePartitionCache
from rag.service.enrichment_service import EnrichmentService
from rag.service.indexing_service import IndexingService
from rag.service.partition_service import PartitionService
from rag.service.routing_service import ElementRoutingService
from rag.service.table_summary_service import TableSummaryService
from tests.fakes import (
    CountingChatModel,
    CountingDescriptions,
    FakeDocstore,
    FakeVectors,
)

HTML = "<table><tr><th>Indicador</th><th>3T24</th></tr><tr><td>Receita</td><td>129,6</td></tr></table>"


class OneTablePartitioner:
    """Particionador dublê: sempre a mesma tabela, sem tocar PDF nenhum."""

    def partition(self, path: Path) -> list[Element]:
        meta = ElementMetadata(page_number=3, text_as_html=HTML)
        return [Table("Indicador 3T24 Receita 129,6", metadata=meta)]


class OnePdfReader:
    """Reader dublê no contrato do `CorpusReader`."""

    def __init__(self, pdf: Path) -> None:
        self._pdf = pdf

    def files(self) -> list[Path]:
        return [self._pdf]

    def require_files(self) -> list[Path]:
        return [self._pdf]


def _facade(
    tmp_path: Path,
    docstore: FakeDocstore,
    vectors: FakeVectors,
    model: CountingChatModel,
) -> IngestionFacade:
    pdf = tmp_path / "relatorio.pdf"
    pdf.write_bytes(b"%PDF-fake")
    return IngestionFacade(
        reader=OnePdfReader(pdf),
        partition=PartitionService(
            partitioner=OneTablePartitioner(),
            cache=FilePartitionCache(tmp_path / "particao", "fast"),
        ),
        routing=ElementRoutingService(tmp_path / "figuras"),
        docstore=docstore,
        vectors=vectors,
        enrichment=EnrichmentService(
            TableSummaryService(model), CountingDescriptions()
        ),
        indexing=IndexingService(docstore, vectors),
    )


def test_reingestao_apos_falha_parcial_completa_o_indice_sem_repagar(
    tmp_path: Path,
) -> None:
    """EC-1 da US-003: o que sobrou do lado certo é completado, não abandonado."""
    docstore, vectors = FakeDocstore(), FakeVectors(fail_on_add=True)
    model = CountingChatModel()

    with pytest.raises(ServiceUnavailableException):
        _facade(tmp_path, docstore, vectors, model).ingest(descrever_imagens=True)

    # O estado da falha parcial: original pago e gravado, índice vazio.
    assert len(docstore.units) == 1
    assert vectors.units == {}
    assert model.calls == 1

    vectors.fail_on_add = False
    report = _facade(tmp_path, docstore, vectors, model).ingest(
        descrever_imagens=True
    )

    assert len(vectors.units) == 1, "a reexecução não completou o lado vetorial"
    doc_id = next(iter(docstore.units))
    assert vectors.units[doc_id].representation.startswith("resumo da tabela")
    assert model.calls == 1, "a retomada repagou o resumo"
    assert report.elements.tabelas == 1


def test_chroma_inacessivel_falha_antes_do_estagio_pago(tmp_path: Path) -> None:
    """EC-4 da US-001: a guarda 3 roda antes de qualquer chamada de LLM."""
    docstore, vectors = FakeDocstore(), FakeVectors(fail_on_count=True)
    model = CountingChatModel()

    with pytest.raises(ServiceUnavailableException):
        _facade(tmp_path, docstore, vectors, model).ingest(descrever_imagens=True)

    assert model.calls == 0, "o enriquecimento rodou com o índice fora do ar"
    assert docstore.units == {}
