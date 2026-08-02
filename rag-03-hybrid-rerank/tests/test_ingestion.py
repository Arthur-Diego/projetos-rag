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
# Mapping explícito do índice
# ---------------------------------------------------------------------------


def test_o_mapping_do_indice_e_explicito_e_o_texto_e_analisado():
    """O campo de texto NASCE analisado, e o vetor nasce com a dimensão certa.

    **Este teste guarda o risco número um do projeto.** Se o campo de texto for
    mapeado como valor único em vez de texto analisado, o BM25 passa a casar o
    campo inteiro e nunca os termos: metade do funil para de funcionar sem erro
    nenhum, e a conclusão registrada seria "a busca híbrida não ajudou" quando a
    verdade é que ela nunca rodou.

    Verifica o mapping que o adaptador ENVIA, sem precisar de Elasticsearch no
    ar. O comportamento contra o motor real é o critério de aceite 8, o teste de
    fumaça que busca um termo raro só pelo caminho léxico.

    Substitui o teste de cache do store que existia no Projeto 2: aquele
    verificava um detalhe do adaptador do Qdrant que não tem equivalente aqui,
    porque o cliente do Elasticsearch não embeda nada na construção.
    """
    from rag.repository.vector_repository import (
        FIELD_EMBEDDING,
        FIELD_TEXT,
        TEXT_ANALYZER,
        _mapping,
    )

    propriedades = _mapping(1536)["mappings"]["properties"]

    texto = propriedades[FIELD_TEXT]
    assert texto["type"] == "text", (
        "campo de texto precisa ser 'text' analisado; 'keyword' mata o BM25 em silêncio"
    )
    assert texto["analyzer"] == TEXT_ANALYZER

    vetor = propriedades[FIELD_EMBEDDING]
    assert vetor["type"] == "dense_vector"
    assert vetor["dims"] == 1536
    assert vetor["index"] is True
    assert vetor["similarity"] == "cosine"


def test_recreate_conta_antes_de_destruir():
    """`previous_chunks` precisa refletir o que HAVIA, não o que sobrou.

    Contar depois de apagar devolveria sempre zero, e o relatório de ingestão
    passaria a mentir sobre quantos trechos foram descartados. Silencioso, e
    exatamente o tipo de número que ninguém confere duas vezes.
    """
    repository = FakeVectorRepository(indexed=617)

    assert repository.recreate(1536) == 617
    assert repository.count() == 0
