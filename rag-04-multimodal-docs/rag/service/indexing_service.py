"""Gravação nos dois armazéns, em ordem FIXA (ADR-001, risco 4 do FDD).

Uma responsabilidade, e ela é uma invariante de uma linha:

    **o original vai para o docstore ANTES de a representação ir para o índice.**

Existe como serviço próprio, e não como duas chamadas dentro da facade, porque
a ordem é a mitigação inteira do risco 4 e precisa de um lugar onde seja
testável isoladamente (T3.7) e impossível de inverter por descuido.

Por que a ordem importa: um hit no índice é sempre resolvido no docstore. Se a
representação fosse gravada primeiro e o processo morresse entre as duas
escritas, o índice teria um `doc_id` sem original — um hit órfão, que na
consulta é um trecho que some em silêncio, e no agregado é "metade do índice
morta sem sintoma". Na ordem correta, a mesma falha deixa um original sem
representação: invisível para a busca, custo já pago, e a reexecução o completa
sem repagar nada (idempotência do ADR-003).

Sobra o que sobra do lado certo. É a diferença entre um armazém com dado a mais
e um índice que mente.
"""

from ..domain.models import DocumentUnit
from ..repository.docstore_repository import DocstoreRepository
from ..repository.vector_repository import VectorRepository
from .ingestion_log import IngestionLog, NullIngestionLog


class IndexingService:
    """Grava unidades enriquecidas nos dois armazéns, na ordem correta."""

    def __init__(
        self,
        docstore: DocstoreRepository,
        vectors: VectorRepository,
        log: IngestionLog | None = None,
    ) -> None:
        self._docstore = docstore
        self._vectors = vectors
        self._log = log or NullIngestionLog()

    def index(self, units: list[DocumentUnit]) -> None:
        """Docstore primeiro, índice depois. Nunca o inverso.

        Em lote, e não unidade a unidade: a invariante vale igual (todos os
        originais antes de qualquer representação) e uma única chamada de
        embedding para o lote inteiro é o que torna a ingestão viável.
        """
        if not units:
            self._log.stage("[indexação] nenhuma unidade nova para gravar")
            return

        self._docstore.put(units)
        self._log.stage(f"[indexação] {len(units)} original(is) no docstore")

        self._vectors.add(units)
        self._log.stage(f"[indexação] {len(units)} representação(ões) no Chroma")
