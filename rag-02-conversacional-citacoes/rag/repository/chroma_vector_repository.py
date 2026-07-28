"""Adaptador do Chroma. Existe para o critério de aceite 7 do PRD.

**Este arquivo é o experimento, não a implementação principal.** O projeto roda
com Qdrant (ADR-001). O Chroma está aqui para provar que trocar o armazém
vetorial é uma linha no composition root, e para que a diferença entre os dois
seja legível lado a lado.

Como trocar:

    # composition.py, build_repository()
    - return QdrantVectorRepository(host=..., port=..., ...)
    + return ChromaVectorRepository(host=..., port=8000, ...)

    # rag/api/dependencies.py, provide_repository()
    idem

Dois lugares, e é o preço declarado de ter dois modelos de injeção.

**A diferença que importa, e que o Protocol esconde de propósito:** o Chroma
devolve L2 ao quadrado, que JÁ É distância (menor é mais próximo). O Qdrant com
COSINE devolve similaridade, onde maior é mais próximo, e o adaptador dele
converte. Compare `search()` dos dois arquivos: é ali que mora tudo o que a
guideline de arquitetura, seção 3, manda ir ler.
"""

import chromadb
from langchain_chroma import Chroma
from langchain_core.embeddings import Embeddings

from ..domain.models import Chunk, SearchHit
from .vector_repository import _to_documents


class ChromaVectorRepository:
    """Adaptador do Chroma em modo servidor.

    Precisa do container do Chroma no ar, na porta 8000. O
    `docker-compose.yml` deste projeto não o declara: acrescente o serviço do
    Projeto 1 se for rodar o experimento.
    """

    def __init__(
        self,
        host: str,
        port: int,
        collection: str,
        embeddings: Embeddings,
        timeout_s: float = 60.0,
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

    def vector_size(self) -> int | None:
        """O Chroma não expõe a dimensão da coleção sem ler um registro.

        Devolver None significa "não sei", e o HealthChecker trata isso como
        "não há o que conferir", que é honesto: aqui a incompatibilidade de
        dimensão só aparece na primeira escrita. É uma diferença REAL entre os
        dois armazéns, e é exatamente o tipo de coisa que só se descobre lendo
        o adaptador.
        """
        return None

    def recreate(self, dimensions: int) -> int:
        """`dimensions` é ignorado.

        O Chroma infere a dimensão do primeiro vetor gravado; não há criação
        explícita com tamanho fixo como no Qdrant. O parâmetro existe no
        Protocol porque o Qdrant precisa dele, e um Protocol não se molda ao
        adaptador mais permissivo.
        """
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

    def add(self, chunks: list[Chunk]) -> None:
        self._store().add_documents(_to_documents(chunks))

    def search(self, query: str, k: int) -> list[SearchHit]:
        """Sem conversão de escala: o Chroma já devolve distância.

        Escala do L2 ao quadrado com embeddings unitários: 0 = idêntico,
        2 = ortogonal, 4 = oposto. A do Qdrant convertido é 0, 1 e 2. Os dois
        respeitam "menor é mais próximo", mas os números NÃO são comparáveis
        entre si, e comparar distâncias de projetos diferentes é um erro fácil
        de cometer.
        """
        pairs = self._store().similarity_search_with_score(query, k=k)
        return [
            SearchHit(
                text=document.page_content,
                source=document.metadata.get("source", "?"),
                page=int(document.metadata.get("page", 0)),
                distance=round(float(distance), 6),
            )
            for document, distance in pairs
        ]
