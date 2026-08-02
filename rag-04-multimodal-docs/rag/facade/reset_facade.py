"""Caso de uso do reset: zerar os DOIS armazéns numa operação.

**Uma facade para duas chamadas, e ela se paga na primeira vez que alguém
esquecer a segunda.** O risco 4 do FDD é dessincronia entre Chroma e docstore, e
zerar um armazém sozinho é a maneira mais direta de produzi-la de propósito: o
índice ficaria cheio de `doc_id`s cujos originais não existem mais, e cada
consulta descartaria hits em silêncio. Aqui as duas operações têm um dono só, e
o `US-013` pede exatamente isso ("um comando único que limpe os dois armazéns").

**O cache de partição em `data/partition/` NÃO é tocado** (ADR-005, AC-2 da
US-013): ele é resultado de um estágio local e gratuito que custa minutos de
CPU. Zerar armazém não pode significar repagar o `hi_res`.

Idempotente: rodar duas vezes seguidas é normal e não falha (EC-1 da US-013).
"""

from ..domain.models import ResetReport
from ..repository.docstore_repository import DocstoreRepository
from ..repository.vector_repository import VectorRepository
from ..service.ingestion_log import IngestionLog, NullIngestionLog


class ResetFacade:
    """Zera índice e docstore, nessa ordem, e relata o que apagou."""

    def __init__(
        self,
        docstore: DocstoreRepository,
        vectors: VectorRepository,
        log: IngestionLog | None = None,
    ) -> None:
        self._docstore = docstore
        self._vectors = vectors
        self._log = log or NullIngestionLog()

    def reset(self) -> ResetReport:
        """Apaga o índice primeiro, o docstore depois.

        **A ordem é o inverso exato da gravação, e é deliberada.** A ingestão
        grava o original antes da representação, para que todo hit encontre o
        seu original (invariante da seção 6 do FDD). Apagar na ordem inversa
        preserva a mesma invariante enquanto o reset roda: entre as duas
        chamadas existe um instante em que há originais sem índice — o que
        significa "nada é buscável" —, e nunca um em que há índice sem originais,
        que seria hit órfão de verdade.

        Se o processo morrer no meio (EC-2 da US-013), o `GET /health` denuncia,
        e rodar o reset de novo conserta.
        """
        indexed_removed = self._vectors.reset()
        self._log.stage(
            f"[reset] índice zerado: {indexed_removed} representação(ões) apagada(s)"
        )

        originals_removed = self._docstore.reset()
        self._log.stage(
            f"[reset] docstore zerado: {originals_removed} original(is) apagado(s)"
        )

        self._log.stage(
            "[reset] cache de partição PRESERVADO: a próxima ingestão não repaga "
            "o hi_res (ADR-005)"
        )
        return ResetReport(
            indexed_removed=indexed_removed,
            originals_removed=originals_removed,
        )
