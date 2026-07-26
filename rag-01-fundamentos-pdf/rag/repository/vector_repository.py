"""Persistência e consulta de vetores.

Camada de repositório. É aqui que o ADR-005 registra o maior custo pedagógico:
o Protocol esconde as diferenças entre os armazéns vetoriais, e conhecer essas
diferenças é objetivo declarado da trilha. Ao comparar Qdrant com Chroma no
Projeto 2, leia os adaptadores, não o fluxo.
"""

from typing import Protocol

import chromadb
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings

from ..domain.models import SearchHit


class VectorRepository(Protocol):
    """Contrato mínimo de um armazém vetorial para esta trilha.

    Quatro métodos: é o que os consumidores usam, e nada além. Um protocolo
    largo obrigaria toda implementação futura a preencher buracos que ninguém
    chama.
    """

    def count(self) -> int:
        """Quantos chunks existem. Zero também significa 'não existe'."""
        ...

    def recreate(self) -> int:
        """Apaga o conteúdo anterior e devolve quantos chunks foram descartados."""
        ...

    def add(self, chunks: list[Document]) -> None:
        ...

    def search(self, query: str, k: int) -> list[SearchHit]:
        ...


class ChromaVectorRepository:
    """Adaptador do Chroma em modo servidor.

    HttpClient, nunca PersistentClient: o ADR-001 decidiu por serviço em
    container, e um PersistentClient aqui contornaria essa decisão em silêncio.

    A busca embute duas idas à rede: uma para a OpenAI, que converte a pergunta
    em vetor, e outra para o Chroma, que compara com os vetores guardados. A
    primeira responde por cerca de 98% do tempo.
    """

    def __init__(
        self,
        host: str,
        port: int,
        collection: str,
        embeddings: Embeddings,
    ) -> None:
        self._client = chromadb.HttpClient(host=host, port=port)
        self._collection = collection
        self._embeddings = embeddings

    def count(self) -> int:
        try:
            return self._client.get_collection(self._collection).count()
        except Exception:
            # Coleção inexistente e coleção vazia dão no mesmo para o chamador.
            return 0

    def recreate(self) -> int:
        previous = self.count()
        if previous:
            self._client.delete_collection(self._collection)
        return previous

    def _store(self) -> Chroma:
        return Chroma(
            client=self._client,
            collection_name=self._collection,
            embedding_function=self._embeddings,
        )

    def add(self, chunks: list[Document]) -> None:
        self._store().add_documents(chunks)

    def search(self, query: str, k: int) -> list[SearchHit]:
        pares = self._store().similarity_search_with_score(query, k=k)
        return [SearchHit(document=d, distance=float(dist)) for d, dist in pares]
