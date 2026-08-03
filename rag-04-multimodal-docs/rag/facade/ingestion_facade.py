"""Caso de uso da ingestão multimodal.

Orquestra e não calcula: seleção -> partição -> roteamento -> idempotência ->
enriquecimento -> indexação dupla. Cada etapa é um serviço; o que mora aqui é a
ORDEM delas, que é onde as invariantes do FDD vivem.

Regra 2.2 da guideline: nada de terminal aqui dentro. O diagnóstico por estágio
sai pela porta `IngestionLog`, cujo adaptador é o presenter — a facade não sabe
se alguém está lendo.
"""

import time

from ..domain.models import DocumentUnit, IngestionReport
from ..repository.corpus_reader import CorpusReader
from ..repository.docstore_repository import DocstoreRepository
from ..repository.vector_repository import VectorRepository
from ..service.enrichment_service import EnrichmentService
from ..service.indexing_service import IndexingService
from ..service.ingestion_log import IngestionLog, NullIngestionLog
from ..service.partition_service import PartitionService
from ..service.routing_service import ElementRoutingService, count_elements


class IngestionFacade:
    """Ingestão de ponta a ponta, idempotente por `doc_id`."""

    def __init__(
        self,
        reader: CorpusReader,
        partition: PartitionService,
        routing: ElementRoutingService,
        docstore: DocstoreRepository,
        vectors: VectorRepository,
        enrichment: EnrichmentService,
        indexing: IndexingService,
        log: IngestionLog | None = None,
    ) -> None:
        self._reader = reader
        self._partition = partition
        self._routing = routing
        self._docstore = docstore
        self._vectors = vectors
        self._enrichment = enrichment
        self._indexing = indexing
        self._log = log or NullIngestionLog()

    def files(self) -> list[str]:
        """O que SERÁ ingerido, antes de ingerir.

        Exposto separado de `ingest()` porque o operador precisa ver a lista
        antes de um trabalho que custa minutos e depois dinheiro. É a mitigação
        registrada para o risco do glob: um PDF do corpus de controle aparece
        aqui em vez de ser descoberto quando a recusa parar de acontecer.
        """
        return [path.name for path in self._reader.files()]

    def ingest(self, descrever_imagens: bool) -> IngestionReport:
        """Ingere o corpus e devolve o relatório do contrato 1.3.0.

        **A ingestão RECONCILIA, não recria** — é a divergência declarada em
        relação aos projetos 1 a 3 e a nota aditiva do `/ingest` na 1.3.0. Lá o
        índice era apagado e reconstruído porque reconstruir custava segundos.
        Aqui custa minutos de `hi_res` e uma chamada paga por tabela e por
        imagem, então apagar para reescrever o mesmo conteúdo seria queimar
        dinheiro por hábito.

        **A ordem das quatro guardas é o desenho:**

        1. Corpus vazio falha antes de qualquer trabalho.
        2. A partição roda antes de tudo que custa dinheiro (é local e grátis).
        3. O índice é verificado ANTES do estágio pago: um Chroma fora do ar
           descoberto depois dos resumos teria custado o corpus inteiro para
           depois falhar na gravação. É a EC-4 da US-001 e a invariante "nenhuma
           chamada paga antes de índice acessível".
        4. Só então o `doc_id` decide quem paga.

        Raises:
            EmptyCorpusException: não há PDF em `pdfs/`. Nada foi tocado.
            PartitionFailedException: dependência nativa ausente, quase sempre.
            ServiceUnavailableException: Chroma ou OpenAI fora do ar.
        """
        started = time.perf_counter()

        paths = self._reader.require_files()
        self._log.stage(
            f"[seleção] {len(paths)} arquivo(s): {', '.join(p.name for p in paths)}"
        )

        units: list[DocumentUnit] = []
        pages = 0
        for path in paths:
            elements = self._partition.partition(path)
            routed = self._routing.route(elements, source=path.name)
            units.extend(routed)
            pages += self._pages_of(routed)

        # Contagem do que a EXTRAÇÃO encontrou, e não do que foi indexado agora:
        # numa reingestão nada é indexado e o relatório continua descrevendo o
        # corpus. `imagens` conta as figuras extraídas mesmo com
        # `descrever_imagens=false`, que é o que a EC do FDD promete.
        elements_count = count_elements(units)

        # Guarda 3: barato, e antes do caro.
        indexed = self._vectors.count()
        self._log.stage(f"[índice] acessível, {indexed} representação(ões) hoje")

        known = self._docstore.known([unit.doc_id for unit in units])
        novos = [unit for unit in units if unit.doc_id not in known]
        self._log.stage(
            f"[idempotência] novos={len(novos)}, reaproveitados={len(known)} "
            f"(de {len(units)} unidade(s) no corpus)"
        )
        if known:
            self._log.stage(
                "[idempotência] doc_id(s) pulados por já existirem no docstore: "
                + ", ".join(sorted(known)[:5])
                + (" e outros" if len(known) > 5 else "")
            )
            # Idempotência olha os DOIS armazéns: original no docstore com
            # representação ausente no índice é retomada de falha parcial
            # (EC-1 da US-003) — o que sobrou do lado certo, na ordem do
            # `IndexingService`. Re-indexar a partir do original persistido
            # repaga só o embedding, nunca o enriquecimento (ADR-003).
            known_ids = sorted(known)
            in_index = self._vectors.known(known_ids)
            pending = [doc_id for doc_id in known_ids if doc_id not in in_index]
            if pending:
                recovered = self._docstore.get(pending)
                self._log.stage(
                    f"[retomada] {len(recovered)} unidade(s) com original no "
                    "docstore e sem representação no índice; re-indexando sem "
                    "repagar enriquecimento"
                )
                self._indexing.index(list(recovered.values()))

        enriched = self._enrichment.enrich(novos, descrever_imagens)
        self._indexing.index(enriched)

        seconds = time.perf_counter() - started
        self._log.stage(
            f"[ingestão] concluída em {seconds:.1f}s — "
            f"{elements_count.textos} texto(s), {elements_count.tabelas} tabela(s), "
            f"{elements_count.imagens} imagem(ns)"
        )
        return IngestionReport(
            pages=pages,
            chunks=len(units),
            seconds=seconds,
            elements=elements_count,
        )

    @staticmethod
    def _pages_of(units: list[DocumentUnit]) -> int:
        """Quantas páginas do documento renderam unidade.

        Página conhecida e distinta, e não a maior numeração vista: uma página
        sem elemento nenhum (folha de rosto em imagem, com `descrever_imagens`
        desligado) não deve ser contada como processada. Unidades com página 0
        (a biblioteca não soube dizer) não entram na contagem.
        """
        return len({unit.page for unit in units if unit.page > 0})
