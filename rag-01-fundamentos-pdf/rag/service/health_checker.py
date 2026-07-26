"""Verificação de pré-condições externas.

Existe para que a falha aconteça antes da primeira chamada paga. Descobrir que
o Chroma está parado depois de embedar 617 chunks custa dinheiro e paciência.
"""

import urllib.request

from ..config import RagProperties
from ..exceptions import ServiceUnavailableException


class HealthChecker:
    """Confere que as dependências externas respondem."""

    def __init__(self, properties: RagProperties) -> None:
        self._properties = properties

    def check(self) -> None:
        """Heartbeat explícito, não uma tentativa de conexão qualquer.

        Sem isso o erro aparece adiante como exceção de biblioteca, e serviço
        parado passa a parecer bug de código.

        Raises:
            ServiceUnavailableException: se o endpoint não responder.
        """
        url = self._properties.heartbeat_url
        try:
            urllib.request.urlopen(url, timeout=5)
        except Exception as e:
            raise ServiceUnavailableException(
                f"Chroma não respondeu em {url} ({type(e).__name__}).\n"
                "       suba o serviço com: docker compose up -d chroma"
            ) from e
