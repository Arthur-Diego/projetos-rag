"""T3.8 — o relatório da ingestão, com zeros explícitos.

Ingestão sintética de ponta a ponta: reader, particionador e armazéns dublês,
roteamento e enriquecimento reais. Nada toca disco de verdade, rede ou API.

O que se cobra: `elements` traz as TRÊS contagens sempre, e categoria que não
ocorreu vale ZERO EXPLÍCITO. Ausência significaria "não sei"; zero significa
"procurei e não achei", que é o sinal do risco 1 do FDD.
"""

from pathlib import Path

import pytest
from unstructured.documents.elements import (
    ElementMetadata,
    NarrativeText,
    Table,
    Title,
)

from rag.facade.ingestion_facade import IngestionFacade
from rag.presenter.json_presenter import JsonPresenter
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
    RecordingLog,
)


class StubReader:
    def __init__(self, paths: list[Path]) -> None:
        self._paths = paths

    def files(self) -> list[Path]:
        return self._paths

    def require_files(self) -> list[Path]:
        return self._paths


class StubPartitioner:
    def __init__(self, elements: list) -> None:
        self._elements = elements

    def partition(self, path: Path) -> list:
        return self._elements


class StubCache:
    """Cache que nunca acerta: aqui o alvo é o relatório, não o cache."""

    last_discard: str | None = None

    def load(self, key: str) -> list | None:
        return None

    def save(self, key: str, elements: list) -> None:
        return None


def _facade(
    tmp_path: Path,
    elements: list,
    model: CountingChatModel | None = None,
) -> tuple[IngestionFacade, FakeDocstore, FakeVectors]:
    docstore, vectors = FakeDocstore(), FakeVectors()
    log = RecordingLog()
    pdf = tmp_path / "relatorio.pdf"
    pdf.write_bytes(b"%PDF")

    facade = IngestionFacade(
        reader=StubReader([pdf]),
        partition=PartitionService(StubPartitioner(elements), StubCache(), log),
        routing=ElementRoutingService(tmp_path / "figuras", log=log),
        docstore=docstore,
        vectors=vectors,
        enrichment=EnrichmentService(
            TableSummaryService(model or CountingChatModel()),
            CountingDescriptions(),
            log,
        ),
        indexing=IndexingService(docstore, vectors, log),
        log=log,
    )
    return facade, docstore, vectors


@pytest.fixture
def so_texto() -> list:
    return [
        Title(text="Desempenho", metadata=ElementMetadata(page_number=1)),
        NarrativeText(
            text="A receita cresceu no trimestre.",
            metadata=ElementMetadata(page_number=1),
        ),
    ]


def test_categoria_ausente_vale_zero_explicito(tmp_path: Path, so_texto: list) -> None:
    facade, _, _ = _facade(tmp_path, so_texto)

    report = facade.ingest(descrever_imagens=True)

    assert report.elements.textos == 1
    assert report.elements.tabelas == 0
    assert report.elements.imagens == 0
    assert report.pages == 1
    assert report.chunks == 1


def test_o_json_do_relatorio_traz_as_tres_contagens(
    tmp_path: Path, so_texto: list
) -> None:
    """A regra da omissão de opcionais PARA no nível do objeto `elements`.

    O contrato declara `required: [textos, tabelas, imagens]` dentro dele:
    omitir `tabelas` por ser zero diria "não sei" no lugar de "não achei".
    """
    facade, _, _ = _facade(tmp_path, so_texto)

    body = JsonPresenter().ingestion(facade.ingest(descrever_imagens=True))

    assert body["elements"] == {"textos": 1, "tabelas": 0, "imagens": 0}
    assert set(body) == {"pages", "chunks", "seconds", "elements"}
    # Opcional que não se aplica é OMITIDO, nunca `null` (regra do rag-03).
    assert all(value is not None for value in body.values())


def test_reingestao_do_corpus_inalterado_nao_gasta_api(tmp_path: Path) -> None:
    """O critério de aceite do custo: `novos=0, reaproveitados=N`.

    É a prova de que o ADR-003 vale de ponta a ponta, e ela é feita no contador
    do resumidor: o relatório da segunda execução é idêntico ao da primeira
    tanto no caminho barato quanto no caro.
    """
    elements = [
        Title(text="Desempenho", metadata=ElementMetadata(page_number=1)),
        Table(
            text="Receita 129,6",
            metadata=ElementMetadata(
                page_number=2, text_as_html="<table><td>129,6</td></table>"
            ),
        ),
    ]
    model = CountingChatModel()
    facade, docstore, vectors = _facade(tmp_path, elements, model)

    primeiro = facade.ingest(descrever_imagens=True)
    assert model.calls == 1
    assert primeiro.elements.tabelas == 1

    segundo = facade.ingest(descrever_imagens=True)

    assert model.calls == 1, "reingestão repagou o resumo da tabela"
    assert segundo.elements == primeiro.elements
    assert segundo.chunks == primeiro.chunks
    assert len(docstore.units) == len(vectors.units) == 2


def test_o_log_declara_novos_e_reaproveitados(tmp_path: Path, so_texto: list) -> None:
    log = RecordingLog()
    docstore, vectors = FakeDocstore(), FakeVectors()
    pdf = tmp_path / "relatorio.pdf"
    pdf.write_bytes(b"%PDF")
    facade = IngestionFacade(
        reader=StubReader([pdf]),
        partition=PartitionService(StubPartitioner(so_texto), StubCache(), log),
        routing=ElementRoutingService(tmp_path / "figuras", log=log),
        docstore=docstore,
        vectors=vectors,
        enrichment=EnrichmentService(
            TableSummaryService(CountingChatModel()), CountingDescriptions(), log
        ),
        indexing=IndexingService(docstore, vectors, log),
        log=log,
    )

    facade.ingest(descrever_imagens=True)
    facade.ingest(descrever_imagens=True)

    assert any("novos=1, reaproveitados=0" in line for line in log.lines)
    assert any("novos=0, reaproveitados=1" in line for line in log.lines)
