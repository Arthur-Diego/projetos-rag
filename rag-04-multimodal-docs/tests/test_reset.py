"""T4.7 — o reset zera os dois armazéns numa operação e é idempotente.

As duas asserções são inseparáveis: zerar um armazém só é a maneira mais direta
de PRODUZIR a dessincronia do risco 4 do FDD, e um reset que falha na segunda
execução obriga o operador a saber em que estado estava antes.
"""

from rag.domain.models import DocumentUnit
from rag.facade.reset_facade import ResetFacade
from tests.fakes import FakeDocstore, FakeVectors, RecordingLog


def _unit(doc_id: str) -> DocumentUnit:
    return DocumentUnit(
        doc_id=doc_id,
        kind="texto",
        content=f"original {doc_id}",
        representation=f"representação {doc_id}",
        source="petrobras-desempenho-3t24.pdf",
        page=1,
    )


def _populados() -> tuple[FakeVectors, FakeDocstore]:
    units = [_unit("a"), _unit("b")]
    vectors = FakeVectors()
    vectors.add(units)
    docstore = FakeDocstore()
    docstore.put(units)
    return vectors, docstore


def test_reset_zera_os_dois_armazens_na_mesma_operacao() -> None:
    vectors, docstore = _populados()

    report = ResetFacade(docstore, vectors).reset()

    assert vectors.count() == 0
    assert docstore.count() == 0
    assert (report.indexed_removed, report.originals_removed) == (2, 2)


def test_segunda_execucao_nao_falha_e_relata_zero() -> None:
    """Idempotência (EC-1 da US-013): armazém já vazio é o estado desejado."""
    vectors, docstore = _populados()
    facade = ResetFacade(docstore, vectors)
    facade.reset()

    report = facade.reset()

    assert (report.indexed_removed, report.originals_removed) == (0, 0)
    assert vectors.count() == 0
    assert docstore.count() == 0


def test_reset_de_armazem_ja_vazio_conclui_sem_erro() -> None:
    report = ResetFacade(FakeDocstore(), FakeVectors()).reset()

    assert (report.indexed_removed, report.originals_removed) == (0, 0)


def test_log_registra_a_preservacao_do_cache_de_particao() -> None:
    """AC-2 da US-013: zerar armazém não pode custar o `hi_res` de novo."""
    vectors, docstore = _populados()
    log = RecordingLog()

    ResetFacade(docstore, vectors, log=log).reset()

    assert any("cache de partição PRESERVADO" in line for line in log.lines)
