"""Verificação de pré-condições, antes da primeira chamada paga.

O risco que este componente mitiga está no HLD: falha de infraestrutura
confundida com falha do pipeline. Motor fora do ar e índice vazio produzem
sintomas parecidos, e num projeto de estudo isso custa uma tarde de depuração
no lugar errado.

TRÊS verificações, deliberadamente separadas, e a terceira é nova neste projeto:

- `check()` só pergunta se o serviço responde e se o cluster não está vermelho.
  Barata, não depende de o índice existir. É o que distingue "fora do ar" de
  "vazio".
- `check_mapping()` confere que o campo de texto serve para busca por termos. É
  o verificador contra o risco número um do projeto, o BM25 que degrada em
  silêncio.
- `check_dimensions()` compara o modelo de embedding configurado com o índice
  que já está lá.

As duas últimas rodam contra o repositório, e por isso vêm depois.
"""

import json
import urllib.error
import urllib.request

from ..config import RagProperties
from ..exceptions import (
    InvalidConfigurationException,
    InvalidIndexMappingException,
    ServiceUnavailableException,
)
from ..repository.vector_repository import VectorRepository

TIMEOUT_S = 5.0


class HealthChecker:
    """Confere que dá para trabalhar antes de começar a trabalhar."""

    def __init__(self, properties: RagProperties) -> None:
        self._properties = properties

    def check(self) -> None:
        """O Elasticsearch responde, e o cluster está utilizável?

        Usa urllib da biblioteca padrão de propósito: verificar se o serviço
        está de pé não deve depender do cliente do próprio serviço, que pode
        falhar por outro motivo e confundir o diagnóstico.

        **Consulta `/_cluster/health`, e não a raiz.** A raiz do Elasticsearch
        responde 200 mesmo com o cluster em estado VERMELHO, então um teste
        apontado para lá aprovaria infraestrutura quebrada como saudável. Aqui
        isso seria pior que no Projeto 2: um cluster degradado pode servir busca
        densa e falhar BM25, produzindo silenciosamente a conclusão de que a
        busca híbrida não ajuda.

        Estado AMARELO é aceito, e precisa ser. Um cluster de nó único nunca
        fica verde, porque as réplicas não têm onde ser alocadas. Exigir verde
        reprovaria todo ambiente local.

        Raises:
            ServiceUnavailableException: com o comando a rodar na mensagem.
        """
        try:
            with urllib.request.urlopen(
                self._properties.health_url, timeout=TIMEOUT_S
            ) as response:
                if response.status >= 400:
                    raise ServiceUnavailableException(self._unavailable_message())
                status = json.loads(response.read()).get("status")
        except ServiceUnavailableException:
            raise
        except Exception:
            raise ServiceUnavailableException(self._unavailable_message()) from None

        if status == "red":
            raise ServiceUnavailableException(
                f"o Elasticsearch respondeu em {self._properties.elastic_url}, mas o "
                "cluster está VERMELHO: há shard primário indisponível.\n"
                "       ele aceita conexão e responde 200 na raiz mesmo assim, então "
                "não confie na raiz como teste de saúde.\n"
                "       veja o motivo com: curl "
                f"{self._properties.elastic_url}/_cluster/allocation/explain"
            )

    def check_mapping(self, repository: VectorRepository) -> None:
        """O campo de texto do índice serve para busca por termos?

        **Este é o verificador contra o risco número um do projeto.** Se o campo
        de texto tiver sido mapeado como valor único em vez de texto analisado, o
        BM25 passa a casar o campo inteiro e nunca os termos. Metade do funil
        para de funcionar sem erro nenhum, e a conclusão registrada seria "a
        busca híbrida não ajudou" quando a verdade é que ela nunca rodou.

        Índice inexistente não é erro: é o estado antes da primeira ingestão, e o
        tratamento é o mesmo tri-estado de `check_dimensions`.

        **Quem chama decide quando chamar.** Este método não sabe se o caminho
        léxico foi pedido, e a matriz de erros do FDD é explícita: com `hibrida`
        desligado a consulta passa, porque a busca densa não depende deste campo
        e não há nada de errado com ela. Chamar isto incondicionalmente
        bloquearia a configuração puramente densa, que é a linha de base da
        tabela de medição.

        Raises:
            InvalidIndexMappingException: se o campo existe e não é analisado.
        """
        analyzed = repository.text_field_analyzed()
        if analyzed is False:
            raise InvalidIndexMappingException(
                f"o índice '{self._properties.collection}' tem o campo de texto "
                "mapeado sem análise de termos, então a busca BM25 não encontra "
                "nada e o funil híbrido roda pela metade, em silêncio.\n"
                "       não existe migração de mapping, existe reindexação:\n"
                "       docker compose down -v && docker compose up -d elasticsearch "
                "&& python ingest.py"
            )

    def check_dimensions(self, repository: VectorRepository) -> None:
        """A coleção existente foi criada com o mesmo modelo de embedding?

        Índice de 1536 dimensões não aceita vetor de outra dimensão, e o erro
        que o cliente devolve nesse caso é obscuro. Detectar aqui troca esse
        erro por uma instrução.

        Índice inexistente não é erro: é o estado antes da primeira ingestão.

        Raises:
            InvalidConfigurationException: se a dimensão não bate.
        """
        actual = repository.vector_size()
        expected = self._properties.embedding_dimensions
        if actual is not None and actual != expected:
            raise InvalidConfigurationException(
                f"o índice '{self._properties.collection}' tem vetores de {actual} "
                f"dimensões, mas o modelo '{self._properties.embedding_model}' produz "
                f"{expected}.\n"
                "       não existe migração, existe reindexação:\n"
                "       docker compose down -v && docker compose up -d elasticsearch && "
                "python ingest.py"
            )

    def _unavailable_message(self) -> str:
        return (
            f"Elasticsearch não respondeu em {self._properties.elastic_url}.\n"
            "       suba com: docker compose up -d elasticsearch\n"
            "       ele leva cerca de 30 s até aceitar conexão"
        )
