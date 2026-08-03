"""Estágio local da ingestão: partição com cache (ADR-005).

Uma responsabilidade: devolver os elementos brutos de um PDF, pagando os
minutos de `hi_res` apenas quando não há como não pagar.

**É aqui que passa a fronteira entre o estágio local e o estágio pago.** Acima
desta linha, tudo custa CPU e nada custa dinheiro. O cache torna barato iterar
no que vem depois — prompt de resumo, roteamento, indexação —, que é justamente
a metade pedagogicamente interessante do pipeline. Sem ele, cada ajuste de
prompt esperaria minutos para reproduzir um resultado que já existia byte a byte.

O serviço não conhece `unstructured` nem disco: ele coordena um `Partitioner` e
um `PartitionCache`, os dois injetados. É o que permite ao teste T3.5 provar que
um cache válido NÃO invoca o particionador.
"""

from pathlib import Path

from unstructured.documents.elements import Element

from ..repository.pdf_partitioner import PartitionCache, Partitioner, content_hash
from .ingestion_log import IngestionLog, NullIngestionLog


class PartitionService:
    """Particiona um PDF, consultando o cache antes."""

    def __init__(
        self,
        partitioner: Partitioner,
        cache: PartitionCache,
        log: IngestionLog | None = None,
    ) -> None:
        self._partitioner = partitioner
        self._cache = cache
        self._log = log or NullIngestionLog()

    def partition(self, path: Path) -> list[Element]:
        """Os elementos brutos do PDF, do cache ou do `hi_res`.

        A ordem — hash, consulta, partição, gravação — é o fluxo do passo 2 ao 4
        do diagrama de ingestão, e o hash vem primeiro porque é a única parte
        barata: ler o arquivo inteiro para hashear custa menos de um segundo,
        contra os minutos que ele pode evitar.

        O acerto de cache é ANUNCIADO, não silencioso: é critério de aceite
        (AC-2 da US-002) e, mais que isso, é o que distingue "a partição foi
        rápida porque o cache funcionou" de "a partição foi rápida porque
        `strategy=fast` está ligado e nenhuma tabela será detectada".
        """
        key = content_hash(path)

        cached = self._cache.load(key)
        discard = self._cache.last_discard
        if discard is not None:
            # O descarte precisa aparecer: cache corrompido em silêncio vira
            # "por que essa ingestão demorou minutos de novo?" sem resposta.
            self._log.stage(
                f"[partição] cache DESCARTADO ({discard}); refazendo a partição"
            )

        if cached is not None:
            self._log.stage(
                f"[partição] acerto de cache para {path.name}: "
                f"{len(cached)} elemento(s) lidos em segundos"
            )
            return cached

        # A mensagem não afirma "hi_res": este serviço não conhece a estratégia,
        # e prometer minutos numa execução `fast` que leva segundos ensinaria o
        # operador a ignorar o aviso justamente quando ele for verdadeiro.
        self._log.stage(
            f"[partição] sem cache para {path.name}: particionando do zero "
            "(com hi_res isto leva MINUTOS de CPU)"
        )
        elements = self._partitioner.partition(path)
        self._cache.save(key, elements)
        self._log.stage(
            f"[partição] {path.name}: {len(elements)} elemento(s), cache gravado"
        )
        return elements
