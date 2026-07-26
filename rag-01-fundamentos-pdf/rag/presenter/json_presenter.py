"""Apresentação em JSON, conforme `docs/contracts/rag-api.yaml`.

Irmão do ConsoleReporter: mesma camada, mesmo papel, saída diferente. A
existência dos dois é a prova de que a facade valeu — o caso de uso não mudou
uma linha para ganhar HTTP.

Regra da camada: **nada aqui decide o que fazer, só como mostrar.**
"""

import os

from ..domain.models import Answer, IngestionReport, SearchHit
from ..service.prompt_builder import ESCAPE_PHRASE

TAMANHO_DO_TRECHO = 280


class JsonPresenter:
    """Converte objetos de domínio no formato do contrato compartilhado."""

    def hit(self, hit: SearchHit) -> dict:
        page = hit.document.metadata.get("page")
        return {
            "source": os.path.basename(hit.document.metadata.get("source", "?")),
            # PyPDFLoader numera a partir de zero; o contrato pede a partir de um.
            "page": page + 1 if isinstance(page, int) else None,
            "distance": round(hit.distance, 4),
            "excerpt": " ".join(hit.document.page_content.split())[:TAMANHO_DO_TRECHO],
        }

    def answer(self, answer: Answer) -> dict:
        """O campo `refused` é o que desacopla o frontend.

        Sem ele, o cliente precisaria comparar a resposta com a frase de escape
        de cada projeto, e passaria a depender do texto exato de cada um.
        """
        return {
            "text": answer.text,
            "refused": answer.text.strip() == ESCAPE_PHRASE,
            "hits": [self.hit(h) for h in answer.hits],
            "timings": {
                "search_s": round(answer.search_s, 3),
                "generation_s": round(answer.generation_s, 3),
            },
        }

    def ingestion(self, report: IngestionReport) -> dict:
        return {
            "pages": report.pages,
            "chunks": report.chunks,
            "discarded_pages": report.discarded_pages,
            "previous_chunks": report.previous_chunks,
            "chunk_size": report.chunk_size,
            "chunk_overlap": report.chunk_overlap,
            "seconds": round(report.seconds, 2),
        }

    def problem(self, title: str, detail: str, code: str) -> dict:
        # A mensagem das exceções já é multilinha e acionável; aqui ela vira
        # uma linha só, porque o destino é uma caixa de erro, não um terminal.
        return {
            "title": title,
            "detail": " ".join(detail.split()),
            "code": code,
        }
