"""Busca léxica (BM25) no armazém.

O segundo caminho do funil, e o que resolve o problema que motiva o projeto.

**Ele lê o MESMO índice e o MESMO documento que a busca densa** (ADR-001). Não
há segundo armazém, não há sincronização, e não existe o estado em que um
caminho enxerga um trecho e o outro não. O dono do índice e do mapping é o
`vector_repository.py`; este arquivo apenas consulta, e importa de lá os nomes
dos campos para que divergir seja impossível.

**Por que este caminho existe.** Embeddings representam significado, e termos
literais não têm significado a representar: um código de erro, um artigo de
norma, um nome próprio raro produzem vetores quase indistinguíveis entre si. Em
*EntityQuestions* (Sciavolino et al., EMNLP 2021), a acurácia de recuperação em
top-20 para perguntas simples sobre entidades é de 72,0% para BM25 contra 49,7%
para recuperação densa, e a diferença cresce conforme a entidade fica mais rara.
BM25 acerta o token exato e erra o sinônimo; a busca densa faz o inverso. É a
complementaridade que o projeto existe para medir.

**Regra dura do ADR-001:** nada do vocabulário do Elasticsearch atravessa este
arquivo. Agora são dois adaptadores sobre o mesmo motor, o que dobra a
superfície por onde ele pode escapar.
"""

from typing import Protocol

from elasticsearch import Elasticsearch

from ..domain.models import SearchHit
from ..exceptions import ServiceUnavailableException
from .vector_repository import FIELD_PAGE, FIELD_SOURCE, FIELD_TEXT, to_hit


class KeywordRepository(Protocol):
    """Contrato do caminho léxico. Um método só.

    Bem menor que o `VectorRepository`, e é isso mesmo: este adaptador não cria
    índice, não conta, não recria e não confere mapping. Ele consulta. Quem é
    dono do ciclo de vida do índice é o repositório vetorial, porque índice e
    mapping são um só (ADR-001) e dois donos seriam duas verdades.
    """

    def search(self, query: str, k: int) -> list[SearchHit]:
        ...


class ElasticKeywordRepository:
    """Adaptador de BM25 sobre o índice compartilhado.

    Não gasta chamada paga: BM25 opera sobre os termos do texto, sem embedar
    nada. É por isso que, no funil, este caminho é o barato, e o custo do
    estágio de recuperação fica quase todo na embedagem da pergunta pelo caminho
    denso, e não aqui. É também o argumento do ADR-006 para não paralelizar as
    duas buscas antes de medir.
    """

    def __init__(self, client: Elasticsearch, index: str) -> None:
        # Mesmo cliente do repositório vetorial, injetado de fora. Dois clientes
        # contra o mesmo container seriam dois pools de conexão para nada.
        self._client = client
        self._index = index

    def _unavailable(self, e: Exception) -> ServiceUnavailableException:
        return ServiceUnavailableException(
            f"Elasticsearch não respondeu ({type(e).__name__}).\n"
            "       suba com: docker compose up -d elasticsearch\n"
            "       ele leva cerca de 30 s até aceitar conexão"
        )

    def search(self, query: str, k: int) -> list[SearchHit]:
        """Busca os k melhores por BM25.

        **O hit devolvido NÃO tem `distance`, e isso é deliberado.** BM25 não
        mede distância nenhuma: devolve uma pontuação sem teto superior, que
        depende da frequência dos termos no corpus, e onde MAIOR é melhor.
        Escrever esse número no campo `distance`, cujo contrato é "menor é mais
        próximo", inverteria a leitura no console e no frontend sem erro nenhum.

        A pontuação bruta também não sobe como `score`. Ela não é comparável com
        a do caminho denso, e é exatamente por essa incomparabilidade que a fusão
        usa posição e não valor (ADR-002). Quem preenche `score` é a fusão, e
        depois o rerank. O que este método entrega é uma lista ORDENADA, e a
        ordem é toda a informação que o RRF precisa.

        Se este método devolver lista vazia para um termo que existe no corpus,
        o mapping do índice está errado: o campo de texto virou `keyword` em vez
        de `text` analisado, e o BM25 está casando o valor inteiro do campo em
        vez dos termos. É o risco número um do projeto, e é o que o critério de
        aceite 8 verifica.
        """
        try:
            response = self._client.search(
                index=self._index,
                query={"match": {FIELD_TEXT: query}},
                size=k,
                source_includes=[FIELD_TEXT, FIELD_SOURCE, FIELD_PAGE],
            )
        except Exception as e:
            raise self._unavailable(e) from e

        return [
            to_hit(document["_id"], document["_source"])
            for document in response["hits"]["hits"]
        ]
