"""T4.2 e T4.3 — resolução dos originais, hit órfão e guarda do índice vazio.

O que se cobra aqui são as duas decisões da entrevista sobre o caminho de
leitura:

- **hit órfão nunca derruba a consulta** (T4.2). Um `doc_id` no índice sem
  original no docstore é dessincronia (risco 4 do FDD), e o tratamento é
  descartar com warning e seguir. Um 500 aqui apagaria o resto da resposta por
  causa de um arquivo.
- **índice vazio custa zero** (T4.3). O gerador dublê CONTA as chamadas, porque
  a afirmação a provar não é "deu erro", e sim "não gastou".
"""

import pytest

from rag.config import MAX_K
from rag.domain.models import DocumentUnit, IndexMatch
from rag.exceptions import EmptyIndexException, InvalidParameterException
from rag.facade.query_facade import QueryFacade
from rag.service.prompt_builder import ESCAPE_PHRASE, PromptBuilder
from rag.service.retrieval.retrieval_service import RetrievalService
from tests.fakes import CountingGeneration, FakeDocstore, FakeVectors, RecordingLog


def _unit(doc_id: str, kind: str = "texto") -> DocumentUnit:
    return DocumentUnit(
        doc_id=doc_id,
        kind=kind,  # type: ignore[arg-type]
        content=f"conteúdo original de {doc_id}",
        representation=f"representação de {doc_id}",
        source="petrobras-desempenho-3t24.pdf",
        page=3,
    )


def _armazens(
    indexados: list[DocumentUnit], no_docstore: list[DocumentUnit]
) -> tuple[FakeVectors, FakeDocstore]:
    """Monta os dois armazéns podendo DIVERGIR de propósito.

    A separação das duas listas é o ponto: é ela que permite escrever o índice
    apontando para um original que não existe, que é o estado que o T4.2 exige e
    que nenhum caminho normal do código consegue produzir.
    """
    vectors = FakeVectors()
    vectors.add(indexados)
    vectors.matches = [
        IndexMatch(doc_id=unit.doc_id, distance=0.1 * (i + 1))
        for i, unit in enumerate(indexados)
    ]
    docstore = FakeDocstore()
    docstore.put(no_docstore)
    return vectors, docstore


def test_hit_orfao_e_descartado_com_warning_e_a_consulta_segue() -> None:
    """T4.2: `doc_id` sem original sai da lista; os demais respondem."""
    vivo, orfao = _unit("aaa"), _unit("bbb")
    vectors, docstore = _armazens([vivo, orfao], [vivo])
    log = RecordingLog()

    result = RetrievalService(vectors, docstore, k=4, log=log).retrieve("pergunta")

    assert [hit.excerpt for hit in result.hits] == [vivo.representation]
    assert result.discarded == 1
    assert any("órfão(s)" in line and "bbb" in line for line in log.lines)


def test_consulta_com_hit_orfao_responde_normalmente() -> None:
    """A outra metade do T4.2: a resposta sai, com os hits que sobraram."""
    vivo, orfao = _unit("aaa"), _unit("bbb")
    vectors, docstore = _armazens([vivo, orfao], [vivo])
    generation = CountingGeneration()
    facade = QueryFacade(
        retrieval=RetrievalService(vectors, docstore, k=4),
        prompts=PromptBuilder(),
        generation=generation,
    )

    answer = facade.ask("qual foi a receita no 3T24?")

    assert answer.refused is False
    assert len(answer.hits) == 1
    assert generation.calls == 1


def test_todos_os_hits_orfaos_viram_recusa_sem_gastar_geracao() -> None:
    """Dessincronia total é ausência de contexto, não erro — e não custa nada."""
    orfao = _unit("bbb")
    vectors, docstore = _armazens([orfao], [])
    generation = CountingGeneration()
    facade = QueryFacade(
        retrieval=RetrievalService(vectors, docstore, k=4),
        prompts=PromptBuilder(),
        generation=generation,
    )

    answer = facade.ask("qual foi a receita no 3T24?")

    assert answer.refused is True
    assert answer.text == ESCAPE_PHRASE
    assert generation.calls == 0


def test_indice_vazio_falha_antes_de_qualquer_chamada_ao_gerador() -> None:
    """T4.3: 409 é uma consulta local; a alternativa custaria duas chamadas."""
    vectors, docstore = _armazens([], [])
    generation = CountingGeneration()
    facade = QueryFacade(
        retrieval=RetrievalService(vectors, docstore, k=4),
        prompts=PromptBuilder(),
        generation=generation,
    )

    with pytest.raises(EmptyIndexException):
        facade.open_index("relatorios")

    assert generation.calls == 0
    # Nem a embedagem da pergunta: `require_index` só conta o que já está lá.
    assert vectors.searches == 0


@pytest.mark.parametrize("k", [0, -1, MAX_K + 1])
def test_k_fora_da_faixa_falha_na_construcao(k: int) -> None:
    """O limite declarado em `/capabilities` é imposto, não sugerido."""
    vectors, docstore = _armazens([], [])

    with pytest.raises(InvalidParameterException):
        RetrievalService(vectors, docstore, k=k)


def test_tabela_recuperada_traz_o_html_do_docstore_no_hit() -> None:
    """A ligação por `doc_id` (ADR-001) vista do lado da leitura."""
    tabela = DocumentUnit(
        doc_id="ccc",
        kind="tabela",
        content="<table><tr><td>129,6</td></tr></table>",
        representation="Tabela de resultados do 3T24 com receita e EBITDA.",
        source="petrobras-desempenho-3t24.pdf",
        page=3,
    )
    vectors, docstore = _armazens([tabela], [tabela])

    hits = RetrievalService(vectors, docstore, k=4).retrieve("receita").hits

    assert hits[0].kind == "tabela"
    assert hits[0].content_html == tabela.content
    assert hits[0].excerpt == tabela.representation
