"""Configuração do pipeline.

Equivalente ao @ConfigurationProperties do Spring: um objeto imutável que
concentra os parâmetros externos. Um RagProperties que existe é válido, porque
a validação acontece na construção e não no uso.
"""

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

from .exceptions import InvalidConfigurationException

ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class RagProperties:
    """Parâmetros do pipeline. Imutável: ninguém reconfigura em execução."""

    openai_api_key: str
    pdf_dir: Path = ROOT / "pdfs"
    chroma_host: str = "localhost"
    chroma_port: int = 8000
    collection: str = "livros"
    embedding_model: str = "text-embedding-3-small"  # 1536 dimensões (ADR-002)
    chat_model: str = "gpt-4o-mini"
    temperature: float = 0.0
    max_retries: int = 3

    @property
    def chroma_url(self) -> str:
        return f"http://{self.chroma_host}:{self.chroma_port}"

    @property
    def heartbeat_url(self) -> str:
        """A API v1 do Chroma foi removida e responde 410 Gone (ADR-001)."""
        return f"{self.chroma_url}/api/v2/heartbeat"


def load(**overrides) -> RagProperties:
    """Lê o .env do repositório e constrói as propriedades.

    O caminho do .env é fixo no diretório do projeto. load_dotenv() sem
    argumento sobe a árvore de diretórios e pode carregar o .env de outro
    projeto sem avisar.

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
