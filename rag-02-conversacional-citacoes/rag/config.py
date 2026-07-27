"""Configuração do pipeline.

Equivalente ao @ConfigurationProperties do Spring: um objeto imutável que
concentra os parâmetros externos. Um RagProperties que existe é válido, porque
a validação acontece na construção e não no uso.

O que NÃO mora aqui: `k`, `history_window` e `conditional_rewrite`. Eles chegam
por requisição (`options` do contrato) e são declarados em `/capabilities`.
Misturá-los com as propriedades do processo faria parecer que mudam com
reinício, quando mudam a cada chamada.
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


@dataclass(frozen=True)
class RagProperties:
    """Parâmetros do pipeline. Imutável: ninguém reconfigura em execução."""

    openai_api_key: str
    pdf_dir: Path = ROOT / "pdfs"
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    collection: str = "normas"
    embedding_model: str = "text-embedding-3-small"  # 1536 dimensões
    embedding_dimensions: int = 1536
    chat_model: str = "gpt-4o-mini"
    temperature: float = 0.0
    max_retries: int = 3
    request_timeout_s: float = 60.0

    @property
    def qdrant_url(self) -> str:
        return f"http://{self.qdrant_host}:{self.qdrant_port}"

    @property
    def health_url(self) -> str:
        """Endpoint de saúde do Qdrant.

        O Qdrant expõe /healthz, /livez e /readyz na porta REST. /healthz é o
        mais barato e não depende de a coleção existir, que é o que se quer:
        distinguir "serviço fora do ar" de "índice vazio" é uma distinção que o
        HLD registra como risco, e ela morre se o teste de saúde exigir dados.
        """
        return f"{self.qdrant_url}/healthz"


def load(**overrides) -> RagProperties:
    """Lê o .env do projeto e constrói as propriedades.

    O caminho do .env é fixo no diretório do projeto. `load_dotenv()` sem
    argumento sobe a árvore de diretórios e, num workspace com dez projetos
    lado a lado, carregaria o .env do vizinho sem avisar.

    Raises:
        InvalidConfigurationException: se OPENAI_API_KEY estiver ausente.
    """
    load_dotenv(ROOT / ".env")

    key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not key:
        raise InvalidConfigurationException(
            "OPENAI_API_KEY não definida.\n"
            "       copie .env.example para .env e preencha a chave."
        )

    return RagProperties(openai_api_key=key, **overrides)
