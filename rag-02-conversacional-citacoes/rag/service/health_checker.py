"""Verificação de pré-condições, antes da primeira chamada paga.

O risco que este componente mitiga está no HLD: falha de infraestrutura
confundida com falha do pipeline. Qdrant fora do ar e índice vazio produzem
sintomas parecidos, e num projeto de estudo isso custa uma tarde de depuração
no lugar errado.

Duas verificações, deliberadamente separadas:

- `check()` só pergunta se o serviço responde. Barata, não depende de a coleção
  existir. É o que distingue "fora do ar" de "vazio".
- `check_dimensions()` compara o modelo de embedding configurado com a coleção
  que já está lá. Roda contra o repositório, e por isso vem depois.
"""

import urllib.error
import urllib.request

from ..config import RagProperties
from ..exceptions import InvalidConfigurationException, ServiceUnavailableException
from ..repository.vector_repository import VectorRepository

TIMEOUT_S = 5.0


class HealthChecker:
    """Confere que dá para trabalhar antes de começar a trabalhar."""

    def __init__(self, properties: RagProperties) -> None:
        self._properties = properties

    def check(self) -> None:
        """O Qdrant responde?

        Usa urllib da biblioteca padrão de propósito: verificar se o serviço
        está de pé não deve depender do cliente do próprio serviço, que pode
        falhar por outro motivo e confundir o diagnóstico.

        Raises:
            ServiceUnavailableException: com o comando a rodar na mensagem.
        """
        try:
            with urllib.request.urlopen(
                self._properties.health_url, timeout=TIMEOUT_S
            ) as response:
                if response.status >= 400:
                    raise ServiceUnavailableException(self._unavailable_message())
        except ServiceUnavailableException:
            raise
        except Exception:
            raise ServiceUnavailableException(self._unavailable_message()) from None

    def check_dimensions(self, repository: VectorRepository) -> None:
        """A coleção existente foi criada com o mesmo modelo de embedding?

        Coleção de 1536 dimensões não aceita vetor de outra dimensão, e o erro
        que o cliente devolve nesse caso é obscuro. Detectar aqui troca esse
        erro por uma instrução.

        Coleção inexistente não é erro: é o estado antes da primeira ingestão.

        Raises:
            InvalidConfigurationException: se a dimensão não bate.
        """
        actual = repository.vector_size()
        expected = self._properties.embedding_dimensions
        if actual is not None and actual != expected:
            raise InvalidConfigurationException(
                f"a coleção '{self._properties.collection}' tem vetores de {actual} "
                f"dimensões, mas o modelo '{self._properties.embedding_model}' produz "
                f"{expected}.\n"
                "       não existe migração, existe reindexação:\n"
                "       docker compose down -v && docker compose up -d qdrant && "
                "python ingest.py"
            )

    def _unavailable_message(self) -> str:
        return (
            f"Qdrant não respondeu em {self._properties.qdrant_url}.\n"
            "       suba com: docker compose up -d qdrant"
        )
