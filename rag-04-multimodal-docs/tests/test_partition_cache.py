"""T3.5 — o cache da partição (ADR-005).

O teste conta INVOCAÇÕES do particionador, e não mede tempo: "a segunda
execução foi mais rápida" é observação frágil numa suíte, enquanto "o
particionador não foi chamado" é a afirmação exata que o ADR-005 faz.

O particionador dublê é o que torna isto barato: o `hi_res` real levaria
minutos e provaria outra coisa.
"""

from pathlib import Path

import pytest
from unstructured.documents.elements import ElementMetadata, NarrativeText

from rag.repository.pdf_partitioner import FilePartitionCache, content_hash
from rag.service.partition_service import PartitionService
from tests.fakes import RecordingLog


class CountingPartitioner:
    """Particionador dublê: devolve sempre o mesmo elemento e conta as chamadas."""

    def __init__(self) -> None:
        self.calls = 0

    def partition(self, path: Path) -> list:
        self.calls += 1
        return [
            NarrativeText(
                text=f"conteúdo de {path.name}",
                metadata=ElementMetadata(page_number=1),
            )
        ]


@pytest.fixture
def pdf(tmp_path: Path) -> Path:
    """Um "PDF" qualquer: o cache é chaveado pelos BYTES, não pelo formato."""
    path = tmp_path / "relatorio.pdf"
    path.write_bytes(b"%PDF-1.7 conteudo de teste")
    return path


def _service(
    tmp_path: Path, partitioner: CountingPartitioner, log: RecordingLog
) -> PartitionService:
    return PartitionService(
        partitioner=partitioner,
        cache=FilePartitionCache(tmp_path / "particao", "hi_res"),
        log=log,
    )


def test_cache_valido_nao_invoca_o_particionador(tmp_path: Path, pdf: Path) -> None:
    partitioner, log = CountingPartitioner(), RecordingLog()
    service = _service(tmp_path, partitioner, log)

    primeiro = service.partition(pdf)
    segundo = service.partition(pdf)

    assert partitioner.calls == 1, "o hi_res rodou de novo com cache válido"
    assert [e.text for e in primeiro] == [e.text for e in segundo]
    assert any("acerto de cache" in line for line in log.lines)


def test_cache_corrompido_e_descartado_e_refeito(tmp_path: Path, pdf: Path) -> None:
    """EC-1 da US-002: o descarte acontece E é denunciado.

    Um cache truncado por interrupção no meio da gravação levantaria no meio da
    ingestão, minutos depois, com mensagem da biblioteca. Aqui vira uma
    repartição e uma linha de log.
    """
    partitioner, log = CountingPartitioner(), RecordingLog()
    service = _service(tmp_path, partitioner, log)
    service.partition(pdf)

    cache_file = tmp_path / "particao" / f"{content_hash(pdf)}-hi_res.json"
    cache_file.write_text("[{isto não é json válido", encoding="utf-8")

    elements = service.partition(pdf)

    assert partitioner.calls == 2
    assert len(elements) == 1
    assert any("DESCARTADO" in line for line in log.lines)
    # E o cache foi regravado, íntegro: a terceira execução volta a acertar.
    service.partition(pdf)
    assert partitioner.calls == 2


def test_pdf_alterado_invalida_o_cache(tmp_path: Path, pdf: Path) -> None:
    """A chave é o CONTEÚDO: trocar o arquivo no lugar não serve dado velho."""
    partitioner = CountingPartitioner()
    service = _service(tmp_path, partitioner, RecordingLog())

    service.partition(pdf)
    pdf.write_bytes(b"%PDF-1.7 outro conteudo")
    service.partition(pdf)

    assert partitioner.calls == 2


def test_o_mesmo_pdf_com_outro_nome_acerta_o_cache(tmp_path: Path, pdf: Path) -> None:
    """EC-3 da US-002: o efeito colateral bem-vindo de chavear por conteúdo."""
    partitioner = CountingPartitioner()
    service = _service(tmp_path, partitioner, RecordingLog())

    service.partition(pdf)
    renomeado = tmp_path / "copia.pdf"
    renomeado.write_bytes(pdf.read_bytes())
    service.partition(renomeado)

    assert partitioner.calls == 1


def test_a_estrategia_faz_parte_da_chave(tmp_path: Path, pdf: Path) -> None:
    """Cache de `fast` não pode ser servido para `hi_res`.

    Seria o risco 1 disfarçado de risco 2: `tabelas: 0` com o `hi_res` já
    funcionando, sem causa aparente.
    """
    partitioner = CountingPartitioner()
    directory = tmp_path / "particao"

    PartitionService(partitioner, FilePartitionCache(directory, "fast")).partition(pdf)
    PartitionService(partitioner, FilePartitionCache(directory, "hi_res")).partition(
        pdf
    )

    assert partitioner.calls == 2
