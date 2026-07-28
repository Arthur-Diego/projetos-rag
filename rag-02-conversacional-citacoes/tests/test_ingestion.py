"""Ordem e contagens da ingestão.

Este arquivo existe por um motivo específico: a ordem das operações em
`IngestionFacade.ingest` é uma decisão com consequência observável, e ela já foi
invertida uma vez sem ninguém perceber. Comentário não impede regressão; teste
impede.

A decisão, herdada do Projeto 1: **a coleção é apagada ANTES da leitura.** Falha
depois disso deixa o índice vazio, e a próxima consulta devolve 409 "rode
ingest.py". Na ordem inversa, a falha deixaria o índice ANTIGO no lugar e a
próxima consulta responderia com dados velhos, sem sintoma nenhum.
"""

import pytest
from conftest import FakeVectorRepository

from rag.domain.models import Page
from rag.exceptions import EmptyCorpusException, NoExtractableTextException
from rag.facade.ingestion_facade import IngestionFacade
from rag.service.chunking_service import RecursiveChunkingService

DIMENSIONS = 1536


class FakeReader:
    """Leitor com o corpus fixado pelo teste."""

    def __init__(
        self,
        pages: list[Page] | None = None,
        discarded: int = 0,
        arquivos: list[str] | None = None,
        erro: Exception | None = None,
    ) -> None:
        self._pages = pages or []
        self._discarded = discarded
        self._arquivos = arquivos if arquivos is not None else ["corpus.pdf"]
        self._erro = erro
        self.leituras = 0

    def files(self):
        from pathlib import Path

        return [Path(nome) for nome in self._arquivos]

    def read(self) -> tuple[list[Page], int]:
        self.leituras += 1
        if self._erro:
            raise self._erro
        return list(self._pages), self._discarded


def build(reader: FakeReader, repository: FakeVectorRepository) -> IngestionFacade:
    return IngestionFacade(
        reader=reader,
        chunking=RecursiveChunkingService(chunk_size=1000, chunk_overlap=150),
        repository=repository,
        dimensions=DIMENSIONS,
    )


PAGINAS = [
    Page(text="Primeira página com bastante texto.", source="corpus.pdf", number=1),
    Page(text="Segunda página, também com texto.", source="corpus.pdf", number=2),
]


def test_recria_antes_de_ler():
    """A ordem que importa, afirmada diretamente.

    Se alguém mover o `recreate` para depois do `split`, este teste falha.
    """
    reader = FakeReader(PAGINAS)
    repository = FakeVectorRepository([])
    ordem: list[str] = []

    recreate_real = repository.recreate
    read_real = reader.read

    def recreate_espiao(dimensions):
        ordem.append("recreate")
        return recreate_real(dimensions)

    def read_espiao():
        ordem.append("read")
        return read_real()

    repository.recreate = recreate_espiao  # type: ignore[method-assign]
    reader.read = read_espiao  # type: ignore[method-assign]

    build(reader, repository).ingest()

    assert ordem == ["recreate", "read"]


def test_falha_na_leitura_deixa_o_indice_vazio_nao_obsoleto():
    """O caso que a ordem existe para tratar.

    Falha depois de recriar produz índice vazio, que é barulhento. Índice antigo
    preservado seria silencioso, e o usuário consultaria dados velhos achando
    que reindexou.
    """
    repository = FakeVectorRepository([])
    reader = FakeReader(erro=OSError("PDF corrompido"))

    with pytest.raises(OSError):
        build(reader, repository).ingest()

    assert repository.recreated_with == [DIMENSIONS]
    assert repository.added == []
    assert repository.count() == 0


def test_corpus_vazio_preserva_o_indice():
    """A guarda barata que roda ANTES de destruir.

    Não conseguir ler é imprevisível e justifica ficar sem índice. Rodar com a
    pasta vazia é verificável de graça, e destruir aí seria punição sem
    informação.
    """
    repository = FakeVectorRepository([])
    reader = FakeReader(arquivos=[])

    with pytest.raises(EmptyCorpusException):
        build(reader, repository).ingest()

    assert repository.recreated_with == []


def test_nenhuma_pagina_com_texto_e_erro():
    repository = FakeVectorRepository([])
    reader = FakeReader(pages=[], discarded=274)

    with pytest.raises(NoExtractableTextException):
        build(reader, repository).ingest()


def test_le_o_corpus_uma_vez_so():
    """`discarded` vem do mesmo laço da leitura.

    Uma versão anterior tinha um `total_pages()` separado que reabria todos os
    PDFs só para contar, dobrando o I/O sem ganho.
    """
    reader = FakeReader(PAGINAS, discarded=3)
    report = build(reader, FakeVectorRepository([])).ingest()

    assert reader.leituras == 1
    assert report.discarded_pages == 3
    assert report.pages == 2


def test_relatorio_reporta_os_chunks_descartados_da_colecao_anterior():
    from rag.domain.models import SearchHit

    anterior = [
        SearchHit(text="antigo", source="velho.pdf", page=1, distance=0.1),
    ]
    repository = FakeVectorRepository(anterior)
    report = build(FakeReader(PAGINAS), repository).ingest()

    assert report.previous_chunks == 1
    assert report.chunks > 0
    assert repository.added != []


# ---------------------------------------------------------------------------
# Reaproveitamento do store
# ---------------------------------------------------------------------------


def test_recreate_descarta_o_store_guardado():
    """O store guardado aponta para a coleção antiga; recriar precisa invalidá-lo.

    Sem isso, o adaptador continuaria escrevendo através de um objeto que
    aponta para uma coleção que não existe mais.

    O reaproveitamento em si é medido contra o Qdrant real (ver
    docs/operations/): o `QdrantVectorStore` embeda 'dummy_text' na construção
    para validar a dimensão, e construir um a cada busca dobrava as chamadas
    pagas de embedding.
    """
    from rag.repository.vector_repository import QdrantVectorRepository

    repo = QdrantVectorRepository.__new__(QdrantVectorRepository)
    repo._collection = "normas"
    repo._cached_store = object()  # simula um store já construído

    class ClienteFalso:
        def collection_exists(self, _):
            return False

        def create_collection(self, **_):
            pass

        def count(self, *a, **k):
            raise AssertionError("nao deveria contar: colecao inexistente")

    repo._client = ClienteFalso()

    repo.recreate(1536)

    assert repo._cached_store is None
