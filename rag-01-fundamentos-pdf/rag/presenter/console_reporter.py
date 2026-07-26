"""Saída e observabilidade.

Camada de apresentação. Uma política, um lugar: **stdout carrega o resultado,
stderr carrega o diagnóstico**. É o que permite `python ask.py "..." > saida.txt`
gravar só a resposta. Nenhuma outra camada escreve.

Recebe objetos de domínio (Answer, IngestionReport) e decide como exibi-los.
As facades produzem o dado; este módulo é o único que sabe que existe um
terminal.
"""

import os
import sys
from pathlib import Path

from ..domain.models import Answer, IngestionReport, SearchHit


class ConsoleReporter:
    """Escreve para o usuário. Único ponto do pacote que conhece stdout/stderr."""

    # ── primitivas ────────────────────────────────────────────────────────
    def diagnostic(self, message: str) -> None:
        print(message, file=sys.stderr)

    def result(self, text: str) -> None:
        print(text)

    def failure(self, message: str) -> None:
        print(f"erro: {message}", file=sys.stderr)

    # ── ingestão ──────────────────────────────────────────────────────────
    def service_ok(self, url: str) -> None:
        self.diagnostic(f"chroma: ok ({url})")

    def reading(self, path: Path) -> None:
        self.diagnostic(f"lendo {path}")

    def ingestion(self, report: IngestionReport, collection: str) -> None:
        """Relata a ingestão a partir do dado devolvido pela facade."""
        if report.previous_chunks:
            self.diagnostic(
                f"coleção '{collection}' tinha {report.previous_chunks} chunks, "
                "recriada do zero"
            )
        if report.discarded_pages:
            self.diagnostic(f"  {report.discarded_pages} página(s) sem texto, descartadas")

        self.result(
            f"{report.pages} páginas -> {report.chunks} chunks "
            f"(tamanho {report.chunk_size}, sobreposição {report.chunk_overlap})"
        )
        self.result(f"indexado em {report.seconds:.1f}s")

    # ── consulta ──────────────────────────────────────────────────────────
    def index_opened(self, collection: str, total: int, k: int) -> None:
        self.diagnostic(f"chroma: ok | coleção '{collection}': {total} chunks | k={k}")

    def answer(self, answer: Answer) -> None:
        """Resposta em stdout; procedência e latências em stderr."""
        self.diagnostic(
            f"busca {answer.search_s:.2f}s | geração {answer.generation_s:.2f}s "
            f"| {len(answer.hits)} chunks"
        )
        self.result(answer.text)
        if answer.hits:
            self._hits(answer.hits)

    def _hits(self, hits: list[SearchHit]) -> None:
        """Procedência de cada trecho: origem, página e distância."""
        self.diagnostic("")
        for i, hit in enumerate(hits, 1):
            source = os.path.basename(hit.document.metadata.get("source", "?"))
            page = hit.document.metadata.get("page")
            # PyPDFLoader numera a partir de zero; humanos, a partir de um.
            label = page + 1 if isinstance(page, int) else "?"
            self.diagnostic(f"  [{i}] {source} p.{label}  dist {hit.distance:.3f}")
        self.diagnostic("  (distância: menor = mais próximo)")
