"""Persistência e busca densa (kNN) no armazém.

Camada de repositório, e a fronteira que o ADR-001 protege.

**Regra dura:** nada do vocabulário do Elasticsearch atravessa este arquivo.
`_source`, `hits.hits`, `dense_vector`, corpo de query e `_id` ficam aqui
dentro. O que sobe é `SearchHit`, com `distance` já no sentido do contrato.

Agora são DOIS adaptadores sobre o mesmo motor, este e o
`keyword_repository.py`, o que dobra a superfície por onde o vocabulário pode
escapar. Os dois leem o MESMO índice e o MESMO documento (ADR-001), então este
arquivo é o dono do mapping e o outro apenas consulta.

**Por que o cliente cru e não o `ElasticsearchStore` do LangChain:** o wrapper
cria o índice implicitamente na primeira escrita, com mapping inferido. Mapping
inferido é o risco número um deste projeto, porque um campo de texto que vira
`keyword` faz o BM25 parar de funcionar sem erro nenhum. Criar o índice à mão,
com o mapping escrito no código, é a mitigação, e ela exige o cliente direto.
"""

from typing import Any, Protocol

from elasticsearch import Elasticsearch
from elasticsearch.helpers import bulk
from langchain_core.embeddings import Embeddings

from ..domain.models import Chunk, SearchHit
from ..exceptions import ServiceUnavailableException

#: Nomes dos campos do documento indexado. Constantes porque os DOIS
#: adaptadores dependem deles: divergir aqui faria a busca léxica procurar num
#: campo que a ingestão não escreve, e o sintoma seria resultado vazio, não erro.
FIELD_TEXT = "text"
FIELD_EMBEDDING = "embedding"
FIELD_SOURCE = "source"
FIELD_PAGE = "page"

#: Analisador de português do Elasticsearch: stemming e stopwords da língua.
#: Sem analisador de língua o BM25 não casa "invisibilidade" com "invisível",
#: que é metade do valor de ter busca léxica sobre um corpus em português.
TEXT_ANALYZER = "brazilian"


class VectorRepository(Protocol):
    """Contrato do armazém para o caminho denso e para a manutenção do índice.

    Seis métodos. Os cinco primeiros vêm do Projeto 2; `text_field_analyzed` é
    novo e existe pelo mesmo motivo que `vector_size` existia lá: o
    `HealthChecker` precisa conferir uma propriedade do índice que só o
    adaptador sabe ler, e sem o método o defeito só apareceria como resultado
    vazio, muito depois, sem mensagem.
    """

    def count(self) -> int:
        """Quantos chunks existem. Zero também significa "não existe"."""
        ...

    def vector_size(self) -> int | None:
        """Dimensão dos vetores do índice, ou None se ele não existe."""
        ...

    def text_field_analyzed(self) -> bool | None:
        """O campo de texto está preparado para busca por termos?

        None quando o índice não existe, que **não é erro**: é o mesmo
        tri-estado de `vector_size`, e o `HealthChecker` já trata ausência como
        sucesso silencioso porque índice inexistente é caso de reindexação, não
        de mapping errado.
        """
        ...

    def recreate(self, dimensions: int) -> int:
        """Apaga o conteúdo anterior e devolve quantos chunks foram descartados."""
        ...

    def add(self, chunks: list[Chunk]) -> None:
        ...

    def search(self, query: str, k: int) -> list[SearchHit]:
        ...


def _mapping(dimensions: int) -> dict[str, Any]:
    """O mapping EXPLÍCITO do índice. É a mitigação do risco número um.

    Se o campo de texto for mapeado como `keyword` em vez de `text` analisado, o
    BM25 passa a casar apenas o valor inteiro do campo e nunca os termos. Metade
    do funil para de funcionar **sem erro nenhum**, e a conclusão do projeto
    vira "a busca híbrida não ajudou" quando a verdade é que ela nunca rodou.

    O Elasticsearch infere `text` para strings por padrão, então o caso
    patológico não é o mais provável. Mas ele é o mais caro, é silencioso, e
    escrever quinze linhas o elimina de vez em vez de deixá-lo depender de um
    padrão do motor que pode mudar de versão.

    `similarity: cosine` porque os embeddings da OpenAI são unitários: cosseno e
    produto interno coincidem, e o cosseno tem faixa conhecida, o que torna a
    conversão para distância trivial e auditável. Ver `search()`.
    """
    return {
        "mappings": {
            "properties": {
                FIELD_TEXT: {"type": "text", "analyzer": TEXT_ANALYZER},
                FIELD_EMBEDDING: {
                    "type": "dense_vector",
                    "dims": dimensions,
                    "index": True,
                    "similarity": "cosine",
                },
                FIELD_SOURCE: {"type": "keyword"},
                FIELD_PAGE: {"type": "integer"},
            }
        }
    }


def to_hit(document_id: str, source: dict[str, Any], **extra: Any) -> SearchHit:
    """Converte um documento do armazém em tipo de domínio.

    Compartilhada com o adaptador léxico de propósito: os dois leem o MESMO
    documento, e duas conversões separadas divergiriam no dia em que um campo
    mudasse de nome. É função de módulo pública, e não privada importada entre
    arquivos como acontecia no Projeto 2 entre os adaptadores de Qdrant e Chroma.

    `doc_id` sobe porque é a chave de deduplicação da fusão (ADR-001). É o único
    identificador do armazém que atravessa a fronteira, e atravessa como string
    opaca: nada acima daqui interpreta o formato dele.
    """
    return SearchHit(
        text=source.get(FIELD_TEXT, ""),
        source=source.get(FIELD_SOURCE, "?"),
        page=int(source.get(FIELD_PAGE, 0)),
        doc_id=document_id,
        **extra,
    )


class ElasticVectorRepository:
    """Adaptador do Elasticsearch para o caminho denso e para o índice.

    Cliente HTTP contra o container, nunca embarcado: o ADR-001 decidiu por
    serviço em container, e um cliente embarcado contornaria a decisão em
    silêncio e apagaria a distinção entre "serviço fora do ar" e "índice vazio".

    A busca embute duas idas à rede: uma para a OpenAI, que converte a pergunta
    em vetor, e outra para o Elasticsearch. A primeira responde pela quase
    totalidade do tempo, e é por isso que o ADR-006 considera as duas buscas
    locais um alvo de otimização prematuro.
    """

    def __init__(
        self,
        client: Elasticsearch,
        index: str,
        embeddings: Embeddings,
    ) -> None:
        # O cliente chega pronto, e não é construído aqui, porque o adaptador
        # léxico usa o MESMO. Dois clientes contra o mesmo container seriam dois
        # pools de conexão para nada.
        self._client = client
        self._index = index
        self._embeddings = embeddings

    def _unavailable(self, e: Exception) -> ServiceUnavailableException:
        return ServiceUnavailableException(
            f"Elasticsearch não respondeu ({type(e).__name__}).\n"
            "       suba com: docker compose up -d elasticsearch\n"
            "       ele leva cerca de 30 s até aceitar conexão"
        )

    def _exists(self) -> bool:
        """O índice existe?

        **Exceção aqui é serviço fora do ar, não índice ausente**, e a distinção
        importa: engolir tudo e devolver False faria um Elasticsearch que caiu no
        meio da sessão virar `EmptyIndexException` e 409 "rode python ingest.py".
        O usuário reindexaria contra um serviço morto.

        É o risco "falha de infraestrutura confundida com falha do pipeline" que
        o HLD registra, e a primeira versão do adaptador do Projeto 2 o cometia.
        """
        try:
            return bool(self._client.indices.exists(index=self._index))
        except Exception as e:
            raise self._unavailable(e) from e

    def _properties(self) -> dict[str, Any] | None:
        """Propriedades do mapping do índice, ou None se ele não existe."""
        if not self._exists():
            return None
        try:
            mapping = self._client.indices.get_mapping(index=self._index)
            return dict(mapping[self._index]["mappings"].get("properties", {}))
        except Exception as e:
            raise self._unavailable(e) from e

    def count(self) -> int:
        if not self._exists():
            return 0
        try:
            # refresh antes de contar: o Elasticsearch indexa de forma assíncrona
            # por padrão, e sem isto a contagem logo após a ingestão sai menor do
            # que a realidade, o que faria `previous_chunks` mentir no relatório.
            self._client.indices.refresh(index=self._index)
            return int(self._client.count(index=self._index)["count"])
        except Exception as e:
            raise self._unavailable(e) from e

    def vector_size(self) -> int | None:
        properties = self._properties()
        if properties is None:
            return None
        embedding = properties.get(FIELD_EMBEDDING, {})
        dims = embedding.get("dims")
        return int(dims) if dims is not None else None

    def text_field_analyzed(self) -> bool | None:
        """O campo de texto é `text` analisado, e não `keyword`?

        Devolve None quando o índice não existe. Não levanta: quem decide o que
        fazer com a divergência é o `HealthChecker`, e quem decide o status HTTP
        é a matriz de erros. Um repositório que levantasse aqui impediria até o
        caminho puramente denso de rodar, e ele não depende deste campo.
        """
        properties = self._properties()
        if properties is None:
            return None
        return properties.get(FIELD_TEXT, {}).get("type") == "text"

    def recreate(self, dimensions: int) -> int:
        """Recria o índice do zero e devolve quantos chunks foram descartados.

        Criar explicitamente, em vez de deixar o motor inferir na primeira
        escrita, é o que fixa a dimensão, a métrica e **o analisador do campo de
        texto** em um lugar só, e permite conferi-los depois em `/health`.
        """
        previous = self.count()
        try:
            if self._exists():
                self._client.indices.delete(index=self._index)
            self._client.indices.create(index=self._index, **_mapping(dimensions))
        except Exception as e:
            raise self._unavailable(e) from e
        return previous

    def add(self, chunks: list[Chunk]) -> None:
        """Indexa os chunks, um documento por chunk.

        Vetor e texto analisado moram no MESMO documento (ADR-001). É isso que
        elimina a sincronização entre armazéns: não existe estado em que a busca
        densa enxerga um trecho e a léxica não.

        Uma chamada de embedding para o lote inteiro, não uma por chunk.
        """
        if not chunks:
            return
        try:
            vectors = self._embeddings.embed_documents([c.text for c in chunks])
            actions = [
                {
                    "_index": self._index,
                    "_source": {
                        FIELD_TEXT: chunk.text,
                        FIELD_EMBEDDING: vector,
                        FIELD_SOURCE: chunk.source,
                        FIELD_PAGE: chunk.page,
                    },
                }
                for chunk, vector in zip(chunks, vectors, strict=True)
            ]
            bulk(self._client, actions)
        except Exception as e:
            raise self._unavailable(e) from e

    def search(self, query: str, k: int) -> list[SearchHit]:
        """Busca os k mais próximos por kNN.

        **A conversão de escala é o ponto delicado, como era no Projeto 2.**

        O Elasticsearch com `similarity: cosine` devolve `(1 + cosseno) / 2`,
        em [0, 1], onde MAIOR é mais próximo. O contrato do domínio é distância,
        onde MENOR é mais próximo. Repassar o valor cru inverteria a leitura na
        interface e faria o trecho mais relevante parecer o mais distante.

        `distância = 1 - cosseno = 2 - 2 × score` põe o resultado na mesma escala
        mental do Projeto 1 e do Projeto 2: 0 = idêntico, 1 = ortogonal,
        2 = oposto. É a razão de o campo se chamar `distance` e não `score`.

        `num_candidates` é o esforço interno do kNN aproximado, e não tem relação
        com o `candidates` do funil: aquele é quantos trechos sobem para a fusão,
        este é quantos nós o motor visita antes de responder.
        """
        try:
            vector = self._embeddings.embed_query(query)
            response = self._client.search(
                index=self._index,
                knn={
                    "field": FIELD_EMBEDDING,
                    "query_vector": vector,
                    "k": k,
                    "num_candidates": max(k * 10, 100),
                },
                size=k,
                source_includes=[FIELD_TEXT, FIELD_SOURCE, FIELD_PAGE],
            )
        except Exception as e:
            raise self._unavailable(e) from e

        return [
            to_hit(
                document["_id"],
                document["_source"],
                distance=round(2.0 - 2.0 * float(document["_score"]), 6),
            )
            for document in response["hits"]["hits"]
        ]
