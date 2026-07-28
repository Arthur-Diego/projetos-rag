"""Configuração do pipeline.

Equivalente ao @ConfigurationProperties do Spring: um objeto imutável que
concentra os parâmetros externos. Um RagProperties que existe é válido, porque
a validação acontece na construção e não no uso.

O que NÃO mora aqui: `k`, `candidates`, `rrf_k`, `hibrida`, `rerank`,
`history_window` e `conditional_rewrite`. Eles chegam por requisição (`options`
do contrato) e são declarados em `/capabilities`. Misturá-los com as
propriedades do processo faria parecer que mudam com reinício, quando mudam a
cada chamada.

O que muda em relação ao Projeto 2: o armazém é o Elasticsearch, atendendo os
dois caminhos de busca sobre o mesmo índice (ADR-001), e existe um modelo de
reordenação local (ADR-004).
"""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from dotenv import load_dotenv

from .exceptions import InvalidConfigurationException

ROOT = Path(__file__).resolve().parent.parent

# Defaults dos parâmetros de requisição. Ficam aqui, e não espalhados pelas
# rotas e entrypoints, para que `/capabilities` e as CLIs prometam o mesmo.
DEFAULT_K: Final = 4
DEFAULT_HISTORY_WINDOW: Final = 6
DEFAULT_CONDITIONAL_REWRITE: Final = False
DEFAULT_CHUNK_SIZE: Final = 1000
DEFAULT_CHUNK_OVERLAP: Final = 150

MAX_K: Final = 20
MAX_HISTORY_WINDOW: Final = 50
MIN_CHUNK_SIZE: Final = 100
MAX_CHUNK_SIZE: Final = 8000
MAX_CHUNK_OVERLAP: Final = 2000

# ---------------------------------------------------------------------------
# Parâmetros do funil (Projeto 3)
# ---------------------------------------------------------------------------

#: Liga o caminho BM25 ao lado do denso. O caminho denso SEMPRE executa; não
#: existe `densa=False`. "Só BM25" é diagnóstico interno (critério de aceite 8),
#: não comando de usuário.
DEFAULT_HYBRID: Final = True

#: Liga a reordenação por cross-encoder. Ligado por padrão em TODOS os caminhos
#: (ADR-001 da feature): o que se usa precisa ser o que se mede, e esconder o
#: custo do estágio derrotaria o exercício de medir o trade-off.
DEFAULT_RERANK: Final = True

#: Candidatos buscados POR CAMINHO, antes da fusão.
DEFAULT_CANDIDATES: Final = 20

#: Teto de candidatos. É 50 e não 100 por latência: o custo do cross-encoder é
#: aproximadamente linear no número de pares, e o BEIR mede 6,1 s para 100 pares
#: em CPU. 100 candidatos sairiam da faixa em que o uso interativo é praticável.
#: Revisável com a primeira medição real nesta máquina.
MAX_CANDIDATES: Final = 50

#: Amortecimento da fusão RRF: score = Σ 1/(rrf_k + posição + 1).
#: 60 é o valor do paper de Cormack et al. (SIGIR 2009) e o default do
#: Elasticsearch, do LangChain e do Azure AI Search. Nenhum deles publica curva
#: de sensibilidade, então varrer este valor é exercício de entendimento e não
#: busca de ótimo.
DEFAULT_RRF_K: Final = 60

#: Teto do amortecimento. Valor alto achata as diferenças entre posições até a
#: fusão virar quase união simples; 1000 é folgado o bastante para o exercício.
MAX_RRF_K: Final = 1000


@dataclass(frozen=True)
class RagProperties:
    """Parâmetros do pipeline. Imutável: ninguém reconfigura em execução."""

    openai_api_key: str
    pdf_dir: Path = ROOT / "pdfs"
    elastic_host: str = "localhost"
    elastic_port: int = 9200
    # Mantém o nome `collection`, e não `index`, apesar de o Elasticsearch
    # chamar de índice: o contrato compartilhado publica `collection` em
    # GET /health desde a versão 1.0.0, e renomear seria mudança quebrante. O
    # ADR-005 fixa que 1.2.0 é aditivo puro. Nas mensagens ao usuário o termo é
    # "índice", que é o vocabulário do projeto.
    collection: str = "normas"
    embedding_model: str = "text-embedding-3-small"  # 1536 dimensões
    embedding_dimensions: int = 1536
    chat_model: str = "gpt-4o-mini"
    temperature: float = 0.0
    max_retries: int = 3
    request_timeout_s: float = 60.0
    #: Cross-encoder local, em CPU (ADR-004). Roda sem gastar API e sem que
    #: nenhum trecho do corpus saia da máquina.
    #:
    #: **MULTILÍNGUE, e não o `ms-marco-MiniLM-L-6-v2` do guia da trilha.** O
    #: guia é escrito para corpus em inglês; este projeto indexa português. A
    #: diferença foi MEDIDA sobre o mesmo corpus, mesmas perguntas e mesmos
    #: parâmetros (ver docs/operations/README.md): o modelo inglês derrubou o
    #: acerto de 8/10 para 5/10, e na linha de identificadores de 5/5 para 3/5.
    #: Ele não era apenas mais fraco em português; ele expulsava do top-4
    #: trechos corretos que a fusão tinha acertado.
    #:
    #: O preço é latência: L12 contra L6 quase dobra o tempo do estágio.
    reranker_model: str = "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1"

    @property
    def elastic_url(self) -> str:
        return f"http://{self.elastic_host}:{self.elastic_port}"

    @property
    def health_url(self) -> str:
        """Endpoint de saúde do Elasticsearch.

        É `/_cluster/health`, e NÃO a raiz. O Elasticsearch responde 200 na raiz
        mesmo com o cluster em estado vermelho, então um teste de saúde apontado
        para lá aprovaria um cluster degradado. Aprovar infraestrutura quebrada
        como saudável é exatamente a confusão que este verificador existe para
        evitar, e ela seria pior aqui que no Projeto 2: um cluster degradado
        pode servir busca densa e falhar BM25, produzindo a conclusão errada.
        """
        return f"{self.elastic_url}/_cluster/health"


def load(**overrides) -> RagProperties:
    """Lê o .env do projeto e constrói as propriedades.

    O caminho do .env é fixo no diretório do projeto. `load_dotenv()` sem
    argumento sobe a árvore de diretórios e, num workspace com dez projetos
    lado a lado, carregaria o .env do vizinho sem avisar.

    Raises:
        InvalidConfigurationException: se OPENAI_API_KEY estiver ausente, ou se
            ELASTIC_PORT estiver definida com valor não numérico.
    """
    load_dotenv(ROOT / ".env")

    key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not key:
        raise InvalidConfigurationException(
            "OPENAI_API_KEY não definida.\n"
            "       copie .env.example para .env e preencha a chave."
        )

    # Host e porta vêm do ambiente porque o compose deste projeto convive com o
    # Qdrant do Projeto 2 e dois Chroma, e remapear porta é o ajuste mais
    # provável de ser necessário. Chamador explícito continua vencendo o
    # ambiente, que é o que os testes usam.
    env_overrides: dict[str, object] = {}
    if "elastic_host" not in overrides:
        host = os.environ.get("ELASTIC_HOST", "").strip()
        if host:
            env_overrides["elastic_host"] = host
    if "elastic_port" not in overrides:
        port = os.environ.get("ELASTIC_PORT", "").strip()
        if port:
            if not port.isdigit():
                raise InvalidConfigurationException(
                    f"ELASTIC_PORT deve ser um número inteiro; recebido {port!r}."
                )
            env_overrides["elastic_port"] = int(port)

    return RagProperties(openai_api_key=key, **{**env_overrides, **overrides})
