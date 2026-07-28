"""Persistência e consulta de vetores.

Camada de repositório, e a fronteira mais importante do projeto: é ela que o
critério de aceite 7 do PRD testa, trocando Qdrant por Chroma numa linha.

**ADR-001, regra dura:** nada do vocabulário do Qdrant atravessa este arquivo.
`payload`, `point_id`, `ScoredPoint`, `VectorParams` e `Distance` ficam aqui
dentro. O que sobe é `SearchHit`, com `distance` já no sentido do contrato.

O custo pedagógico está registrado na seção 3 da guideline de arquitetura: o
Protocol esconde as diferenças entre os armazéns, e conhecer essas diferenças é
objetivo declarado da trilha. Ao comparar Qdrant com Chroma, leia os
adaptadores, não o fluxo. A diferença mais visível está em `search()`.
"""

from typing import Protocol

from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_qdrant import QdrantVectorStore
from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, VectorParams

from ..domain.models import Chunk, SearchHit
from ..exceptions import ServiceUnavailableException


class VectorRepository(Protocol):
    """Contrato mínimo de um armazém vetorial para esta trilha.

    Cinco métodos. Os quatro primeiros são os do Projeto 1; `vector_size` é
    novo e existe porque o `HealthChecker` precisa comparar a dimensão do
    modelo de embedding configurado com a da coleção que já existe. Sem isso, o
    erro de dimensão só aparece na primeira consulta, com mensagem obscura do
    cliente, depois de a chamada paga já ter acontecido.
    """

    def count(self) -> int:
        """Quantos chunks existem. Zero também significa "não existe"."""
        ...

    def vector_size(self) -> int | None:
        """Dimensão dos vetores da coleção, ou None se ela não existe."""
        ...

    def recreate(self, dimensions: int) -> int:
        """Apaga o conteúdo anterior e devolve quantos chunks foram descartados."""
        ...

    def add(self, chunks: list[Chunk]) -> None:
        ...

    def search(self, query: str, k: int) -> list[SearchHit]:
        ...


def _to_documents(chunks: list[Chunk]) -> list[Document]:
    """Converte domínio em moeda do LangChain.

    A conversão vive no lado do adaptador, não no domínio: `Chunk` não conhece
    LangChain, e é essa ignorância que permite trocar o armazém sem tocar em
    `domain/`.
    """
    return [
        Document(
            page_content=chunk.text,
            metadata={"source": chunk.source, "page": chunk.page},
        )
        for chunk in chunks
    ]


class QdrantVectorRepository:
    """Adaptador do Qdrant em modo servidor (ADR-001).

    Cliente HTTP contra o container, nunca modo `:memory:` nem `path=`: o
    ADR-001 decidiu por serviço em container, e um cliente embarcado aqui
    contornaria a decisão em silêncio e apagaria a distinção entre "serviço
    fora do ar" e "índice vazio".

    A busca embute duas idas à rede: uma para a OpenAI, que converte a pergunta
    em vetor, e outra para o Qdrant, que compara com os vetores guardados. A
    primeira responde pela quase totalidade do tempo.
    """

    def __init__(
        self,
        host: str,
        port: int,
        collection: str,
        embeddings: Embeddings,
        timeout_s: float = 60.0,
    ) -> None:
        self._client = QdrantClient(url=f"http://{host}:{port}", timeout=int(timeout_s))
        self._collection = collection
        self._embeddings = embeddings
        self._cached_store: QdrantVectorStore | None = None

    def _unavailable(self, e: Exception) -> ServiceUnavailableException:
        return ServiceUnavailableException(
            f"Qdrant não respondeu ({type(e).__name__}).\n"
            "       suba com: docker compose up -d qdrant"
        )

    def _exists(self) -> bool:
        """A coleção existe?

        **Exceção aqui é serviço fora do ar, não coleção ausente**, e a
        distinção importa: engolir tudo e devolver False faria um Qdrant que
        caiu no meio da sessão virar `EmptyIndexException` e 409 "rode python
        ingest.py". O usuário reindexaria contra um serviço morto.

        É exatamente o risco "falha de infraestrutura confundida com falha do
        pipeline" que o HLD registra, e a primeira versão deste adaptador o
        cometia.
        """
        try:
            return self._client.collection_exists(self._collection)
        except Exception as e:
            raise self._unavailable(e) from e

    def count(self) -> int:
        if not self._exists():
            return 0
        try:
            return self._client.count(self._collection, exact=True).count
        except Exception as e:
            raise self._unavailable(e) from e

    def vector_size(self) -> int | None:
        if not self._exists():
            return None
        try:
            params = self._client.get_collection(self._collection).config.params
            vectors = params.vectors
            # Qdrant admite coleção com vetores nomeados; a nossa é a de vetor
            # único, e a diferença de forma fica contida aqui.
            if isinstance(vectors, dict):
                return next(iter(vectors.values())).size
            return vectors.size if vectors else None
        except Exception as e:
            raise self._unavailable(e) from e

    def recreate(self, dimensions: int) -> int:
        """Recria a coleção do zero e devolve quantos chunks foram descartados.

        Criar explicitamente, em vez de deixar o `QdrantVectorStore` criar na
        primeira escrita, é o que permite fixar a dimensão e a métrica em um
        lugar só e conferi-las depois em `/health`.
        """
        previous = self.count()
        if self._exists():
            self._client.delete_collection(self._collection)
        # O store guardado aponta para a coleção que acabou de ser apagada.
        # Descartar aqui força a reconstrução contra a coleção nova.
        self._cached_store = None
        self._client.create_collection(
            collection_name=self._collection,
            # COSINE porque os embeddings da OpenAI são unitários: cosseno e
            # produto interno coincidem, e o cosseno tem faixa conhecida
            # [-1, 1], o que torna a conversão para distância trivial e
            # auditável. Ver search().
            vectors_config=VectorParams(size=dimensions, distance=Distance.COSINE),
        )
        return previous

    def _store(self) -> QdrantVectorStore:
        """Constrói o store uma vez e reaproveita.

        **Isto não é micro-otimização; é dinheiro.** O `QdrantVectorStore` nasce
        com `validate_embeddings=True`, e essa validação embeda a string
        `'dummy_text'` para conferir se a dimensão do modelo bate com a da
        coleção. Uma chamada paga à OpenAI, na construção.

        A versão anterior deste método construía um store NOVO a cada `search()`,
        então toda busca custava DUAS chamadas de embedding em vez de uma: a
        validação e a query. Numa conversa de 10 turnos pelo `chat.py`, eram 10
        validações idênticas do mesmo par modelo/coleção.

        A validação em si é útil e fica: ela mede a dimensão real que o modelo
        produz, enquanto o `HealthChecker.check_dimensions` compara a dimensão
        *declarada* em `RagProperties` com a da coleção. Quem trocar
        `embedding_model` sem trocar `embedding_dimensions` só é pego por esta.
        O que muda é a frequência: uma vez por repositório, não por busca.
        """
        if self._cached_store is None:
            self._cached_store = QdrantVectorStore(
                client=self._client,
                collection_name=self._collection,
                embedding=self._embeddings,
            )
        return self._cached_store

    def add(self, chunks: list[Chunk]) -> None:
        self._store().add_documents(_to_documents(chunks))

    def search(self, query: str, k: int) -> list[SearchHit]:
        """Busca os k mais próximos.

        **Aqui está a diferença entre este adaptador e o do Chroma, e ela é o
        que o critério de aceite 7 do PRD manda observar.**

        O Chroma devolve L2 ao quadrado: já é distância, menor é mais próximo,
        e o Projeto 1 repassa o número como veio. O Qdrant com COSINE devolve
        SIMILARIDADE em [-1, 1], onde MAIOR é mais próximo. Repassar o valor
        cru inverteria a leitura na interface e faria o trecho mais relevante
        parecer o mais distante.

        A conversão `1 - similaridade` põe os dois na mesma escala mental:
        0 = idêntico, 1 = ortogonal, 2 = oposto. Ela é a razão de o Protocol
        chamar o campo de `distance` e não de `score`.
        """
        pairs = self._store().similarity_search_with_score(query, k=k)
        return [
            SearchHit(
                text=document.page_content,
                source=document.metadata.get("source", "?"),
                page=int(document.metadata.get("page", 0)),
                distance=round(1.0 - float(similarity), 6),
            )
            for document, similarity in pairs
        ]
