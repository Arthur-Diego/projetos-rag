"""Armazém das REPRESENTAÇÕES: busca densa sobre o que embeda bem (ADR-001).

Camada de repositório, e a fronteira que o ADR-001 protege do outro lado.

**Regra dura, herdada do rag-03: nada do vocabulário do Chroma atravessa este
arquivo.** `collection`, `metadatas`, `ids`, `include` e o formato do retorno
ficam aqui dentro. O que sobe é domínio puro.

O que este armazém guarda **não é o documento**: é a representação — o texto
narrativo direto, o resumo da tabela, a descrição da imagem (ADR-002). O
original vive no docstore, e a ligação é o `doc_id`, que viaja como metadado.
Confundir os dois é o defeito central que este projeto existe para não cometer:
entregar ao LLM o resumo em vez da tabela.

**Por que o cliente cru e não o `Chroma` do LangChain**, pelo mesmo motivo do
rag-03 com o Elasticsearch: o wrapper cria a coleção implicitamente, com a
métrica padrão, e a métrica errada não dá erro nenhum — só piora a ordem. Criar
explicitamente fixa `cosine` em um lugar só e permite conferi-la depois.
"""

from typing import Any, Protocol

from chromadb.api import ClientAPI
from langchain_core.embeddings import Embeddings

from ..domain.models import DocumentUnit, IndexMatch
from ..exceptions import ServiceUnavailableException

#: Metadados de cada representação. Constantes porque a ingestão escreve e a
#: consulta (task_04) lê: divergir aqui faria a resolução do original procurar
#: uma chave que ninguém grava, e o sintoma seria hit órfão, não erro.
META_DOC_ID = "doc_id"
META_KIND = "kind"
META_PAGE = "page"
META_SOURCE = "source"

#: Distância do cosseno. Os embeddings da OpenAI são unitários, então cosseno e
#: produto interno coincidem; o cosseno tem faixa conhecida, o que torna a
#: leitura da distância auditável. O default do Chroma é `l2`.
SPACE = "cosine"


class VectorRepository(Protocol):
    """Contrato do armazém das representações."""

    def count(self) -> int:
        """Quantas representações existem. Zero também significa "não existe"."""
        ...

    def add(self, units: list[DocumentUnit]) -> None:
        """Indexa a REPRESENTAÇÃO das unidades, com `doc_id` como identidade.

        Escrever sob o próprio `doc_id` é o que fecha a idempotência do ADR-003
        no lado vetorial: reingerir sobrescreve com o mesmo conteúdo em vez de
        acrescentar uma duplicata, e duplicata em índice vetorial é pior que
        ausência, porque ocupa vaga entre os k mais próximos sem informação nova.
        """
        ...

    def search(self, query: str, k: int) -> list[IndexMatch]:
        """Os `k` `doc_id`s cujas REPRESENTAÇÕES mais se aproximam da pergunta.

        Devolve identificadores, e não conteúdo, de propósito: o que está aqui é
        o resumo da tabela, e devolvê-lo faria a chamada parecer completa quando
        falta justamente a metade que importa. Quem tem o original é o docstore
        (ADR-001).
        """
        ...

    def reset(self) -> int:
        """Apaga a coleção inteira e devolve quantas representações havia.

        Operação do script de reset, nunca da ingestão: aqui a ingestão
        RECONCILIA (ADR-003). Devolve a contagem anterior porque um comando
        destrutivo precisa dizer o tamanho do que destruiu.
        """
        ...


class ChromaVectorRepository:
    """Adaptador do Chroma em container (porta 8002), via HttpClient.

    Cliente HTTP contra o container, nunca embarcado: o ADR-001 decidiu por
    serviço em container, e um cliente embarcado contornaria a decisão em
    silêncio e apagaria a distinção entre "serviço fora do ar" e "índice vazio".
    """

    def __init__(
        self,
        client: ClientAPI,
        collection: str,
        embeddings: Embeddings,
    ) -> None:
        self._client = client
        self._collection = collection
        self._embeddings = embeddings

    def _unavailable(self, e: Exception) -> ServiceUnavailableException:
        return ServiceUnavailableException(
            f"Chroma não respondeu ({type(e).__name__}).\n"
            "       suba com: docker compose up -d chroma\n"
            "       confira com: curl localhost:8002/api/v2/heartbeat"
        )

    def _handle(self) -> Any:
        """A coleção, criada com a métrica explícita se ainda não existir."""
        try:
            return self._client.get_or_create_collection(
                name=self._collection,
                metadata={"hnsw:space": SPACE},
            )
        except Exception as e:
            raise self._unavailable(e) from e

    def count(self) -> int:
        try:
            return int(self._handle().count())
        except ServiceUnavailableException:
            raise
        except Exception as e:
            raise self._unavailable(e) from e

    def add(self, units: list[DocumentUnit]) -> None:
        """Embeda as representações em lote e grava com `doc_id` como id.

        `upsert` e não `add`: a idempotência do ADR-003 significa que a mesma
        chave pode ser gravada de novo (reingestão após falha parcial, EC-1 da
        US-003), e `add` com id repetido é erro no Chroma. Sobrescrever com o
        mesmo conteúdo é o comportamento correto e barato.

        Uma chamada de embedding para o lote inteiro, não uma por unidade.
        """
        if not units:
            return
        handle = self._handle()
        try:
            vectors = self._embeddings.embed_documents(
                [unit.representation for unit in units]
            )
        except Exception as e:
            # Falha aqui é a OpenAI, não o Chroma. A mensagem precisa dizer isso:
            # mandar o operador subir o container não resolveria nada.
            raise ServiceUnavailableException(
                f"a API de embeddings não respondeu ({type(e).__name__}).\n"
                "       as unidades já gravadas FICAM; rode de novo para retomar."
            ) from e

        try:
            handle.upsert(
                ids=[unit.doc_id for unit in units],
                embeddings=vectors,
                documents=[unit.representation for unit in units],
                metadatas=[
                    {
                        META_DOC_ID: unit.doc_id,
                        META_KIND: unit.kind,
                        META_PAGE: unit.page,
                        META_SOURCE: unit.source,
                    }
                    for unit in units
                ],
            )
        except Exception as e:
            raise self._unavailable(e) from e

    def search(self, query: str, k: int) -> list[IndexMatch]:
        """Embeda a pergunta e devolve os `k` mais próximos, já em domínio.

        A embedagem da pergunta é a única chamada PAGA da consulta antes da
        geração, e é por isso que `require_index` roda antes: perguntar contra
        índice vazio não deve custar nem este embedding.

        `include=["distances"]` e nada mais: documento e metadado do índice
        carregam a REPRESENTAÇÃO, e trazê-los daqui convidaria alguém a montar o
        prompt com o resumo — o defeito que este projeto existe para não
        cometer. O que sobe é `doc_id` e distância.
        """
        try:
            vector = self._embeddings.embed_query(query)
        except Exception as e:
            raise ServiceUnavailableException(
                f"a API de embeddings não respondeu ({type(e).__name__}).\n"
                "       confira a chave, o crédito da conta e a conexão."
            ) from e

        handle = self._handle()
        try:
            found = handle.query(
                query_embeddings=[vector],
                n_results=k,
                include=["distances"],
            )
        except Exception as e:
            raise self._unavailable(e) from e

        ids = (found.get("ids") or [[]])[0]
        distances = (found.get("distances") or [[]])[0]
        return [
            IndexMatch(doc_id=str(doc_id), distance=float(distance))
            for doc_id, distance in zip(ids, distances, strict=True)
        ]

    def reset(self) -> int:
        """Apaga a coleção e devolve quantas representações ela tinha.

        `delete_collection` e não `delete(ids=...)`: apagar item a item deixaria
        para trás a configuração da coleção (a métrica `cosine` fixada em
        `_handle`), e uma coleção zerada com a métrica errada é pior que
        nenhuma — ela não dá erro, só piora a ordem em silêncio.

        Idempotente: coleção inexistente é o estado desejado, não uma falha.
        """
        previous = self.count()
        try:
            self._client.delete_collection(name=self._collection)
        except ServiceUnavailableException:
            raise
        except Exception:
            # Chegar aqui com o `count()` acima tendo respondido significa que a
            # coleção não existe mais: o resultado pedido já vale.
            return previous
        return previous
