"""Verificação de pré-condições e de SINCRONIA entre os dois armazéns.

Duas checagens, deliberadamente separadas, porque respondem perguntas
diferentes:

- `check()` só pergunta se o Chroma responde. Barata, não depende de o índice
  existir, e é o que distingue "container fora do ar" (503) de "índice vazio"
  (409). Roda antes de qualquer chamada paga.
- `synchrony()` compara as contagens dos dois armazéns. É o verificador do risco
  4 do FDD, e o mais perigoso dos dois: dessincronia NÃO produz erro nenhum —
  produz hits órfãos descartados em silêncio, isto é, metade do índice morta sem
  sintoma. Um `doc_id` sem original é uma fonte que nunca chega ao LLM.

`check()` usa `urllib` da biblioteca padrão de propósito (molde do rag-03):
verificar se o serviço está de pé não deve depender do cliente do próprio
serviço, que pode falhar por outro motivo e confundir o diagnóstico.
"""

import urllib.request

from ..config import RagProperties
from ..exceptions import ServiceUnavailableException

TIMEOUT_S = 5.0

#: Estados publicados em `GET /health` pelo contrato compartilhado.
STATUS_OK = "ok"
STATUS_DEGRADED = "degraded"


class HealthChecker:
    """Confere que dá para trabalhar, e se os dois armazéns concordam."""

    def __init__(self, properties: RagProperties) -> None:
        self._properties = properties

    def check(self) -> None:
        """O Chroma responde?

        Aponta para `/api/v2/heartbeat` e não para a raiz: na imagem 1.5.9 a API
        v1 responde 410 Gone, e um verificador apontado para lá reportaria o
        container saudável como morto. O endereço vive em `RagProperties`, num
        lugar só.

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

    def synchrony(self, indexed: int, originals: int) -> str | None:
        """A evidência da dessincronia, ou `None` se os armazéns concordam.

        Devolve texto e não booleano porque `degraded` sem evidência é inútil
        para quem opera: o critério 9 do FDD pede a evidência na resposta, e a
        receita (reset e reingestão) muda conforme qual lado está sobrando.

        **Contagens iguais e ZERADAS são consistentes**, não degradadas: é o
        estado normal antes da primeira ingestão, e não há dessincronia nenhuma
        nele. Quem denuncia índice vazio é o `POST /ask`, com 409 — a seção 5 do
        FDD reserva `degraded` para incompatibilidade entre os armazéns ou
        docstore inacessível.
        """
        if indexed == originals:
            return None

        collection = self._properties.collection
        if originals < indexed:
            return (
                f"o índice '{collection}' tem {indexed} representação(ões) e o "
                f"docstore tem {originals} original(is): {indexed - originals} "
                "doc_id(s) órfão(s). Hits desses trechos são descartados na "
                "consulta e nunca chegam ao modelo. Conserte com: "
                ".venv/bin/python reset.py && .venv/bin/python ingest.py"
            )
        return (
            f"o docstore tem {originals} original(is) e o índice '{collection}' "
            f"tem {indexed} representação(ões): {originals - indexed} "
            "original(is) não é buscável, porque não foi indexado. A ingestão "
            "provavelmente parou no meio; rode de novo: "
            ".venv/bin/python ingest.py"
        )

    def _unavailable_message(self) -> str:
        return (
            f"Chroma não respondeu em {self._properties.chroma_url}.\n"
            "       suba com: docker compose up -d chroma\n"
            "       confira com: curl localhost:8002/api/v2/heartbeat"
        )
