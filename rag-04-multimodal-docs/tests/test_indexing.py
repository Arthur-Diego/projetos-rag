"""T3.3, T3.4 e T3.7 — a ligação entre os dois armazéns.

O segundo alvo de teste fixado em `docs/guidelines/README.md`: a
correspondência resumo -> original por `doc_id`. Achar o resumo tem que devolver
o original certo, senão o multi-vector é só um índice pior com um custo maior.
"""

from pathlib import Path

import pytest

from rag.domain.models import DocumentUnit
from rag.exceptions import ServiceUnavailableException
from rag.repository.docstore_repository import FileDocstoreRepository
from rag.service.enrichment_service import EnrichmentService
from rag.service.indexing_service import IndexingService
from rag.service.table_summary_service import TableSummaryService
from tests.fakes import (
    CountingChatModel,
    CountingDescriptions,
    FakeDocstore,
    FakeVectors,
)

TABELA = DocumentUnit(
    doc_id="a1b2c3",
    kind="tabela",
    content="<table><tr><td>129,6</td></tr></table>",
    representation="",
    source="relatorio.pdf",
    page=3,
)


def test_representacao_e_original_compartilham_doc_id_e_kind() -> None:
    """T3.3 — as duas metades ficam ligadas depois de indexar.

    E a verificação que importa mais: o que está no ÍNDICE é o resumo, o que
    está no DOCSTORE é o HTML. Trocá-los seria entregar ao LLM o resumo — o
    defeito que este projeto inteiro existe para não cometer.
    """
    docstore, vectors = FakeDocstore(), FakeVectors()
    enrichment = EnrichmentService(
        TableSummaryService(CountingChatModel()), CountingDescriptions()
    )

    enriched = enrichment.enrich([TABELA], descrever_imagens=True)
    IndexingService(docstore, vectors).index(enriched)

    original = docstore.units[TABELA.doc_id]
    representacao = vectors.units[TABELA.doc_id]
    assert original.doc_id == representacao.doc_id == TABELA.doc_id
    assert original.kind == representacao.kind == "tabela"
    assert original.content == TABELA.content
    assert representacao.representation.startswith("resumo da tabela")
    assert representacao.content == TABELA.content, (
        "o docstore e o índice guardam a MESMA unidade; o que difere é qual "
        "campo cada um usa"
    )
    assert "<table" not in representacao.representation


def test_indexar_duas_vezes_nao_duplica_nem_repaga() -> None:
    """T3.4 — a idempotência, medida em CHAMADAS e não em resultado.

    O ponto sutil: um pipeline que repaga tudo devolve exatamente o mesmo
    conteúdo de um pipeline que não repaga nada. A diferença só aparece no
    contador do dublê — por isso o teste conta, em vez de comparar.
    """
    docstore, vectors = FakeDocstore(), FakeVectors()
    model = CountingChatModel()
    enrichment = EnrichmentService(
        TableSummaryService(model), CountingDescriptions()
    )
    indexing = IndexingService(docstore, vectors)

    indexing.index(enrichment.enrich([TABELA], descrever_imagens=True))
    assert model.calls == 1

    # Segunda passada: quem decide quem paga é o docstore, pelo `doc_id`.
    novos = [unit for unit in [TABELA] if unit.doc_id not in docstore.known(["a1b2c3"])]
    indexing.index(enrichment.enrich(novos, descrever_imagens=True))

    assert novos == []
    assert model.calls == 1, "a tabela foi resumida de novo: repagou"
    assert len(docstore.units) == 1
    assert len(vectors.units) == 1


def test_falha_no_indice_deixa_o_original_no_docstore() -> None:
    """T3.7 — a ordem de gravação é a mitigação do risco 4.

    Sobra dado do lado CERTO. Na ordem inversa sobraria um `doc_id` no índice
    sem original: um hit órfão, que na consulta é um trecho que some em
    silêncio.
    """
    docstore, vectors = FakeDocstore(), FakeVectors(fail_on_add=True)

    with pytest.raises(ServiceUnavailableException):
        IndexingService(docstore, vectors).index([TABELA._replace(representation="r")])

    assert TABELA.doc_id in docstore.units
    assert vectors.units == {}


def test_o_docstore_real_devolve_a_unidade_intacta(tmp_path: Path) -> None:
    """A serialização do armazém real preserva original e representação.

    Sem isto, os testes acima estariam provando o comportamento dos dublês.
    """
    from langchain_classic.storage import LocalFileStore

    repository = FileDocstoreRepository(LocalFileStore(tmp_path))
    unidade = TABELA._replace(representation="resumo", figure_path=None)

    repository.put([unidade])

    assert repository.known([unidade.doc_id]) == {unidade.doc_id}
    assert repository.get([unidade.doc_id])[unidade.doc_id] == unidade
    assert repository.count() == 1


def test_imagem_sem_descricao_nao_e_indexada() -> None:
    """`descrever_imagens=false`: extraída e contada, não indexada.

    Indexá-la com representação vazia seria pior que deixá-la pendente: um vetor
    de string vazia ocupa vaga entre os k mais próximos sem significar nada.
    """
    descriptions = CountingDescriptions()
    enrichment = EnrichmentService(
        TableSummaryService(CountingChatModel()), descriptions
    )
    imagem = DocumentUnit(
        doc_id="fig1",
        kind="imagem",
        content="",
        representation="",
        source="relatorio.pdf",
        page=4,
        figure_path="/tmp/fig1.jpg",
    )

    assert enrichment.enrich([imagem], descrever_imagens=False) == []
    assert descriptions.calls == 0
