"""Política de recuperação, agora um funil de quatro etapas.

Separado do repositório de propósito: os repositórios sabem guardar e consultar,
este serviço sabe QUANTO trazer, por quais caminhos e sob que critério.

**Este componente é o único lugar do projeto que mudou de natureza.** No
Projeto 2 ele repassava uma chamada ao repositório. Aqui ele orquestra:

    denso ─┐
           ├─→ fusão RRF ─→ rerank ─→ top k
    BM25 ──┘

Ele orquestra e **não calcula**. A matemática da fusão mora no `FusionService`,
que é função pura sem dependência nenhuma (ADR-003), e a pontuação mora no
`RerankService`. Se a fórmula do RRF aparecer neste arquivo, a responsabilidade
escorregou.

**Ele fala com serviços, nunca com repositórios** (ADR-009). Os dois caminhos de
busca são encapsulados por `DenseSearchService` e `KeywordSearchService`, de modo
que as quatro etapas do funil apareçam como pares dentro deste pacote. Os dois
delegam ao repositório correspondente sem acrescentar política, e o ADR-009
registra que isso foi escolha por legibilidade, não descuido.

**Por que ele devolve `RetrievalResult` e não `list[SearchHit]`** (ADR-007): com
quatro etapas por dentro, cronometrar de fora só produz um número agregado, e o
agregado não responde onde o tempo foi gasto. O tempo sai pelo retorno, nunca
por atributo do serviço: a alternativa do canal lateral introduziria estado
mutável, e duas requisições concorrentes leriam o tempo uma da outra.

Não há limiar de distância, por decisão herdada do Projeto 2. O armazém devolve
os mais próximos SEMPRE, mesmo quando todos são ruins. Quem pode recusar é o
prompt, e só depois da geração.
"""

from time import perf_counter

from ...config import (
    DEFAULT_CANDIDATES,
    DEFAULT_HYBRID,
    DEFAULT_K,
    DEFAULT_RERANK,
    DEFAULT_RRF_K,
    MAX_CANDIDATES,
    MAX_K,
    MAX_RRF_K,
)
from ...domain.models import PATH_DENSE, PATH_KEYWORD, RetrievalResult, SearchHit
from ...exceptions import EmptyIndexException, InvalidParameterException
from .dense_search_service import DenseSearchService
from .fusion_service import FusionService
from .keyword_search_service import KeywordSearchService
from .rerank_service import RerankService


class RetrievalService:
    """Executa o funil de recuperação e devolve os finais com a métrica."""

    def __init__(
        self,
        dense: DenseSearchService,
        keywords: KeywordSearchService,
        fusion: FusionService,
        reranker: RerankService,
        k: int = DEFAULT_K,
        candidates: int = DEFAULT_CANDIDATES,
        rrf_k: int = DEFAULT_RRF_K,
        hybrid: bool = DEFAULT_HYBRID,
        rerank: bool = DEFAULT_RERANK,
    ) -> None:
        """Valida as faixas na CONSTRUÇÃO, não no uso.

        Um serviço que existe é válido. Declarar um limite em `/capabilities` e
        não impô-lo transforma o descritor em sugestão, que é o comentário que o
        Projeto 2 deixou no construtor da facade.

        **`MAX_K` não é reaproveitado para `candidates`.** São grandezas de
        ordens diferentes: `k` é quantos trechos vão para a janela de contexto do
        modelo, e acima de 20 o contexto dilui e a citação fica confusa;
        `candidates` é quantos sobem para a fusão, e 20 é o ponto de PARTIDA. Um
        teto só para os dois obrigaria a escolher entre limitar o funil e
        permitir uma janela de contexto absurda.
        """
        if k < 1:
            raise InvalidParameterException(f"k deve ser >= 1 (recebido: {k}).")
        if k > MAX_K:
            raise InvalidParameterException(
                f"k deve ser <= {MAX_K} (recebido: {k}). "
                "Acima disso o contexto dilui e a citação fica confusa."
            )
        if candidates < 1:
            raise InvalidParameterException(
                f"candidates deve ser >= 1 (recebido: {candidates})."
            )
        if candidates > MAX_CANDIDATES:
            raise InvalidParameterException(
                f"candidates deve ser <= {MAX_CANDIDATES} (recebido: {candidates}). "
                "O custo do reordenador cresce com o número de pares, e em CPU "
                "isso são segundos por turno."
            )
        if k > candidates:
            # Contradição de configuração, e não simples valor fora de faixa:
            # pedir mais finais do que candidatos é pedir que o funil invente
            # trecho. Silenciar isso cortando para `candidates` esconderia um
            # erro de quem chamou.
            raise InvalidParameterException(
                f"k ({k}) não pode ser maior que candidates ({candidates}): "
                "o funil não tem de onde tirar os finais que faltam."
            )
        if rrf_k < 1:
            raise InvalidParameterException(
                f"rrf_k deve ser >= 1 (recebido: {rrf_k})."
            )
        if rrf_k > MAX_RRF_K:
            raise InvalidParameterException(
                f"rrf_k deve ser <= {MAX_RRF_K} (recebido: {rrf_k}). "
                "Valor alto achata as diferenças entre posições."
            )

        self._dense = dense
        self._keywords = keywords
        self._fusion = fusion
        self._reranker = reranker
        self.k = k
        self.candidates = candidates
        self.rrf_k = rrf_k
        self.hybrid = hybrid
        self.rerank = rerank

    def indexed_count(self) -> int:
        return self._dense.indexed_count()

    def require_index(self, collection: str) -> int:
        """Falha cedo se não há o que buscar.

        Chamado ANTES de qualquer chamada paga: um índice vazio não deve custar
        uma reescrita nem uma geração.

        Raises:
            EmptyIndexException: se o índice não existe ou está sem chunks.
        """
        total = self.indexed_count()
        if not total:
            raise EmptyIndexException(
                f"índice '{collection}' está vazio ou não existe.\n"
                "       rode primeiro: python ingest.py"
            )
        return total

    def retrieve(self, query: str) -> RetrievalResult:
        """Executa o funil sobre a query JÁ RESOLVIDA.

        Nunca sobre a pergunta original. Quem decide qual das duas é esta é a
        facade, a partir da `RewriteDecision`. Este serviço recebe texto e
        busca: se ele conhecesse a conversa, a política de reescrita teria dois
        donos.

        **O caminho denso SEMPRE executa.** Não existe `hybrid=False, denso
        desligado`: o diagnóstico "só BM25" é obtido pelo harness de medição
        consultando o repositório léxico direto, e não por combinação de
        parâmetros públicos.

        **Estágio que não roda tem tempo None, nunca 0.0.** Zero significaria
        "rodou e foi instantâneo", que é afirmação diferente de "não rodou", e a
        tabela de medição depende dessa distinção.

        As duas buscas rodam em SEQUÊNCIA (ADR-006). O gargalo do turno é a
        embedagem da pergunta, que é chamada externa paga, e o reordenador; duas
        requisições locais ao mesmo container não justificam concorrência antes
        de haver medição. `dense_s` e `keyword_s` separados são o que permite
        reabrir essa decisão com número em vez de intuição.
        """
        marker = perf_counter()
        dense = self._dense.search(query, k=self.candidates)
        dense_s = perf_counter() - marker

        rankings = [(PATH_DENSE, dense)]
        keyword_s: float | None = None
        if self.hybrid:
            marker = perf_counter()
            rankings.append((PATH_KEYWORD, self._keywords.search(query, k=self.candidates)))
            keyword_s = perf_counter() - marker

        marker = perf_counter()
        fused = self._fusion.fuse(rankings, rrf_k=self.rrf_k)
        fusion_s = perf_counter() - marker

        rerank_s: float | None = None
        if self.rerank:
            marker = perf_counter()
            hits = self._reranker.rerank(query, fused, top_n=self.k)
            rerank_s = perf_counter() - marker
        else:
            hits = fused[: self.k]

        return RetrievalResult(
            hits=hits,
            dense_s=dense_s,
            keyword_s=keyword_s,
            fusion_s=fusion_s,
            rerank_s=rerank_s,
        )

    def keyword_only(self, query: str, k: int | None = None) -> list[SearchHit]:
        """Busca APENAS pelo caminho léxico. Diagnóstico, não uso normal.

        Existe para o critério de aceite 8, o teste de fumaça do BM25: buscar um
        termo raro conhecido do corpus só por este caminho e exigir resultado.
        Se vier vazio, o campo de texto do índice foi mapeado como valor único em
        vez de texto analisado, e metade do funil está morta sem que nada avise.

        É **o critério que impede a conclusão do projeto de ser falsa**. Sem ele,
        um mapping errado produziria a tabela mostrando "a busca híbrida não
        ajudou" quando a verdade seria que ela nunca rodou.

        Não é exposto como parâmetro de requisição, por decisão registrada no
        FDD: é comando de diagnóstico, não configuração de usuário.
        """
        return self._keywords.search(query, k=k or self.candidates)
