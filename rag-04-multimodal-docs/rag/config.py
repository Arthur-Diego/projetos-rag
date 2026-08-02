"""Configuração do pipeline.

Equivalente ao @ConfigurationProperties do Spring: um objeto imutável que
concentra os parâmetros externos. Um `RagProperties` que existe é válido, porque
a validação acontece na construção e não no uso.

O que NÃO mora aqui: `k` e `descrever_imagens`. Eles chegam por requisição
(`options` do contrato) e são declarados em `/capabilities`. Misturá-los com as
propriedades do processo faria parecer que mudam com reinício, quando mudam a
cada chamada. Os DEFAULTS deles moram aqui, e não espalhados pelas rotas e
entrypoints, para que `/capabilities` e as CLIs prometam o mesmo.

O que muda em relação ao Projeto 3: há DOIS armazéns (ADR-001) e um estágio de
partição local e caro que tem cache próprio (ADR-005), então os três diretórios
de `data/` são propriedade de configuração, não caminho literal espalhado pelos
serviços.
"""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, Literal

from dotenv import load_dotenv

from .exceptions import InvalidConfigurationException

ROOT = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# Defaults dos parâmetros de requisição (publicados em /capabilities)
# ---------------------------------------------------------------------------

#: Trechos recuperados por consulta. Moderado por desenho: com `kind=tabela` o
#: que entra no prompt é o HTML ÍNTEGRO da tabela, não o resumo, e top-k alto
#: estoura contexto e custo (risco 5 do FDD).
DEFAULT_K: Final = 4
MIN_K: Final = 1
MAX_K: Final = 20

#: Descrever imagens custa uma chamada de visão por figura. Ligado por padrão:
#: desligar deixa as unidades de imagem pendentes para uma ingestão futura, e
#: isso é contingência de custo, não o caminho normal.
DEFAULT_DESCREVER_IMAGENS: Final = True

# ---------------------------------------------------------------------------
# Parâmetros do estágio de partição e enriquecimento
# ---------------------------------------------------------------------------

#: Alvo de caracteres do agrupamento de texto narrativo por `chunk_by_title`.
#: Tabelas e imagens FICAM DE FORA do agrupamento: cada uma é unidade própria,
#: porque agrupá-las com o texto vizinho desfaria a separação que o `hi_res`
#: acabou de fazer.
DEFAULT_MAX_CHARACTERS: Final = 1000

#: Teto de chamadas simultâneas ao enriquecer em lote (resumo e descrição).
#: 5 é o limite adotado na trilha para não esbarrar em rate limit da OpenAI.
MAX_CONCURRENCY: Final = 5

#: Estratégias de partição aceitas.
#:
#: `hi_res` é a do projeto: roda modelo de layout e Table Transformer, custa
#: minutos de CPU por PDF e é o ÚNICO caminho que produz tabela em HTML.
#: `fast` é contingência declarada do risco 2 do FDD: usa só a camada de texto
#: do PDF, sobe em segundos, não precisa de poppler nem de tesseract e NÃO
#: detecta tabela nenhuma. Serve para destravar o resto do pipeline enquanto o
#: setup nativo não sobe — nunca para medir.
PartitionStrategy = Literal["hi_res", "fast"]
DEFAULT_PARTITION_STRATEGY: Final[PartitionStrategy] = "hi_res"
PARTITION_STRATEGIES: Final[frozenset[str]] = frozenset({"hi_res", "fast"})


@dataclass(frozen=True)
class RagProperties:
    """Parâmetros do pipeline. Imutável: ninguém reconfigura em execução."""

    openai_api_key: str
    pdf_dir: Path = ROOT / "pdfs"

    # -- Chroma (representações) --------------------------------------------
    chroma_host: str = "localhost"
    #: 8002, e não 8000 nem 8001: aquelas pertencem aos Chroma dos projetos 1 e
    #: 2, que convivem nesta máquina (ADR-001).
    chroma_port: int = 8002
    #: O contrato compartilhado publica `collection` em GET /health desde a
    #: 1.0.0; o nome do campo é herança, o valor é deste projeto.
    collection: str = "relatorios"

    # -- Docstore (originais) -----------------------------------------------
    #: Fonte de verdade dos conteúdos (ADR-001). Perder o Chroma custa minutos
    #: de re-embedding; perder isto custa a ingestão inteira.
    docstore_dir: Path = ROOT / "data" / "docstore"

    # -- Estágio local de partição ------------------------------------------
    partition_strategy: PartitionStrategy = DEFAULT_PARTITION_STRATEGY
    #: Cache do resultado bruto do `hi_res`, chaveado por hash do PDF (ADR-005).
    #: É a fronteira entre o estágio local gratuito e o estágio pago.
    partition_cache_dir: Path = ROOT / "data" / "partition"
    #: Imagens extraídas pelo `hi_res`. Os nomes derivam do `doc_id`, nunca de
    #: conteúdo do PDF: path traversal neutralizado por construção (ADR-003).
    figures_dir: Path = ROOT / "data" / "figures"

    # -- Modelos pagos -------------------------------------------------------
    embedding_model: str = "text-embedding-3-small"  # 1536 dimensões
    embedding_dimensions: int = 1536
    chat_model: str = "gpt-4o-mini"
    #: O MESMO modelo do texto, em modo visão (base64 em mensagem `image_url`).
    #: Campo separado porque o ponto de troca é real: o ADR-006 prevê um modelo
    #: local como segunda implementação do `ImageDescriptor`.
    vision_model: str = "gpt-4o-mini"
    temperature: float = 0.0
    max_retries: int = 3
    request_timeout_s: float = 60.0

    def __post_init__(self) -> None:
        if self.partition_strategy not in PARTITION_STRATEGIES:
            raise InvalidConfigurationException(
                f"PARTITION_STRATEGY deve ser uma de {sorted(PARTITION_STRATEGIES)}; "
                f"recebido {self.partition_strategy!r}."
            )
        if not 1 <= self.chroma_port <= 65535:
            raise InvalidConfigurationException(
                f"CHROMA_PORT fora da faixa de portas válidas: {self.chroma_port}."
            )

    @property
    def chroma_url(self) -> str:
        return f"http://{self.chroma_host}:{self.chroma_port}"

    @property
    def health_url(self) -> str:
        """Endpoint de saúde do Chroma.

        É `/api/v2/heartbeat`: na imagem 1.5.9 a API v1 responde 410 Gone, e um
        verificador apontado para lá reportaria o container saudável como morto.
        Valor conferido contra a imagem na trilha (ver `docker-compose.yml`).
        """
        return f"{self.chroma_url}/api/v2/heartbeat"


def load(**overrides: Any) -> RagProperties:
    """Lê o .env do projeto e constrói as propriedades.

    O caminho do .env é fixo no diretório do projeto. `load_dotenv()` sem
    argumento sobe a árvore de diretórios e, num workspace com dez projetos lado
    a lado, carregaria o .env do vizinho sem avisar.

    Chamador explícito vence o ambiente, que é o que os testes usam.

    Raises:
        InvalidConfigurationException: se `OPENAI_API_KEY` estiver ausente, se
            `CHROMA_PORT` não for numérica ou se `PARTITION_STRATEGY` trouxer
            valor fora do conjunto aceito.
    """
    load_dotenv(ROOT / ".env")

    key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not key:
        raise InvalidConfigurationException(
            "OPENAI_API_KEY não definida.\n"
            "       copie .env.example para .env e preencha a chave."
        )

    # Host, porta e estratégia vêm do ambiente porque são os três ajustes mais
    # prováveis: a máquina hospeda os armazéns dos projetos anteriores, e a
    # queda para `fast` é a contingência declarada do risco 2 do FDD.
    env_overrides: dict[str, Any] = {}
    if "chroma_host" not in overrides:
        host = os.environ.get("CHROMA_HOST", "").strip()
        if host:
            env_overrides["chroma_host"] = host
    if "chroma_port" not in overrides:
        port = os.environ.get("CHROMA_PORT", "").strip()
        if port:
            if not port.isdigit():
                raise InvalidConfigurationException(
                    f"CHROMA_PORT deve ser um número inteiro; recebido {port!r}."
                )
            env_overrides["chroma_port"] = int(port)
    if "partition_strategy" not in overrides:
        strategy = os.environ.get("PARTITION_STRATEGY", "").strip()
        if strategy:
            env_overrides["partition_strategy"] = strategy

    return RagProperties(openai_api_key=key, **{**env_overrides, **overrides})
