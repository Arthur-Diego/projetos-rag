"""Estágio PAGO da ingestão: preenche a representação do que embeda mal.

Uma responsabilidade: dadas unidades NOVAS, devolver as mesmas unidades com a
representação pronta para indexar. Não decide quem é novo (é o docstore que
sabe, pelo `doc_id`) e não grava nada (é o `IndexingService` que grava).

**O multi-vector aqui é SELETIVO (ADR-002), e a seletividade é o desenho.** O
diagrama do guia resume TODO elemento antes de indexar. Este projeto diverge:
texto narrativo entra direto. Resumir é remédio para representação que embeda
mal, não pipeline padrão — resumir texto narrativo pagaria uma chamada por
chunk para OBTER MENOS INFORMAÇÃO do que já se tinha de graça.
"""

from pathlib import Path

from ..domain.models import DocumentUnit
from .image_description_service import ImageDescriptionService
from .ingestion_log import IngestionLog, NullIngestionLog
from .table_summary_service import TableSummaryService


class EnrichmentService:
    """Preenche `representation` de tabelas e imagens; não toca em texto."""

    def __init__(
        self,
        summaries: TableSummaryService,
        descriptions: ImageDescriptionService,
        log: IngestionLog | None = None,
    ) -> None:
        self._summaries = summaries
        self._descriptions = descriptions
        self._log = log or NullIngestionLog()

    def enrich(
        self, units: list[DocumentUnit], descrever_imagens: bool
    ) -> list[DocumentUnit]:
        """Enriquece as unidades e devolve o que está PRONTO PARA INDEXAR.

        A saída pode ser menor que a entrada, e o caso é declarado: com
        `descrever_imagens=false` as unidades de imagem saem da lista. Elas já
        foram extraídas e contadas no relatório, mas não são descritas nem
        indexadas nesta execução — ficam pendentes para uma ingestão futura com
        a flag ligada. Indexá-las com representação vazia seria pior: um vetor
        de string vazia ocupa vaga entre os k mais próximos sem significar nada.

        Unidade cuja representação volta vazia da API também é descartada, pelo
        mesmo motivo, com o descarte anunciado no log.
        """
        tables = [unit for unit in units if unit.kind == "tabela"]
        images = [unit for unit in units if unit.kind == "imagem"]
        texts = [unit for unit in units if unit.kind == "texto"]

        if texts:
            self._log.stage(
                f"[enriquecimento] {len(texts)} texto(s) indexados DIRETO, "
                "sem resumo (ADR-002): zero chamada paga neste ramo"
            )

        enriched: list[DocumentUnit] = list(texts)
        enriched.extend(self._enrich_tables(tables))
        enriched.extend(self._enrich_images(images, descrever_imagens))

        self._log.stage(
            f"[enriquecimento] tokens gastos: {self.tokens} "
            f"(resumo {self._summaries.tokens}, visão {self._descriptions.tokens})"
        )
        return enriched

    @property
    def tokens(self) -> int:
        return self._summaries.tokens + self._descriptions.tokens

    def _enrich_tables(self, tables: list[DocumentUnit]) -> list[DocumentUnit]:
        if not tables:
            return []
        self._log.stage(f"[enriquecimento] resumindo {len(tables)} tabela(s)")
        summaries = self._summaries.summarize([unit.content for unit in tables])

        enriched = []
        for unit, summary in zip(tables, summaries, strict=True):
            if not summary.strip():
                self._log.stage(
                    f"[enriquecimento] resumo vazio para a tabela da página "
                    f"{unit.page} de {unit.source}; unidade NÃO indexada"
                )
                continue
            # `content` intocado: o original que responde é o HTML, e trocá-lo
            # pelo resumo aqui seria cometer, num único `_replace`, o defeito que
            # o projeto inteiro existe para não cometer.
            enriched.append(unit._replace(representation=summary))
        return enriched

    def _enrich_images(
        self, images: list[DocumentUnit], descrever_imagens: bool
    ) -> list[DocumentUnit]:
        if not images:
            return []
        if not descrever_imagens:
            self._log.stage(
                f"[enriquecimento] descrever_imagens=false: {len(images)} "
                "imagem(ns) extraídas e contadas, mas NÃO descritas nem "
                "indexadas; ficam pendentes para uma ingestão futura"
            )
            return []

        self._log.stage(f"[enriquecimento] descrevendo {len(images)} imagem(ns)")
        figures = [Path(unit.figure_path or "") for unit in images]
        descriptions = self._descriptions.describe(figures)

        enriched = []
        for unit, description in zip(images, descriptions, strict=True):
            if not description.strip():
                self._log.stage(
                    f"[enriquecimento] descrição vazia para a figura da página "
                    f"{unit.page} de {unit.source}; unidade NÃO indexada"
                )
                continue
            # Imagem é a única categoria em que original e representação
            # coincidem: não há texto por baixo da figura para servir de
            # original, e a descrição é tudo que o LLM vai receber.
            enriched.append(
                unit._replace(content=description, representation=description)
            )
        return enriched
