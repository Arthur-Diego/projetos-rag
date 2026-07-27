"""Apresentação em JSON, conforme `../docs/contracts/rag-api.yaml` 1.1.0.

Irmão do ConsoleReporter: mesma camada, mesmo papel, saída diferente. A
existência dos dois é a prova de que a facade valeu.

Regra da camada: **nada aqui decide o que fazer, só como mostrar.** Em especial,
`refused` NÃO é calculado aqui, ao contrário do Projeto 1. Ele vem pronto do
domínio, porque a invariante "recusa não cita" precisa valer na facade, e uma
invariante que só existe na apresentação não vale em lugar nenhum.
"""

from ..domain.models import Answer, Citation, IngestionReport, SearchHit
from ..service.citation_resolver import EXCERPT_CHARS


class JsonPresenter:
    """Converte objetos de domínio no formato do contrato compartilhado."""

    def hit(self, hit: SearchHit) -> dict:
        return {
            "source": hit.source,
            "page": hit.page,
            "distance": round(hit.distance, 4),
            "excerpt": " ".join(hit.text.split())[:EXCERPT_CHARS],
        }

    def citation(self, citation: Citation) -> dict:
        return {
            "label": citation.label,
            "source": citation.source,
            "page": citation.page,
            "excerpt": citation.excerpt,
        }

    def answer(self, answer: Answer) -> dict:
        """Serializa a resposta.

        **Campos opcionais do 1.1.0 são OMITIDOS quando vazios, nunca emitidos
        como null.** É a garantia de compatibilidade registrada no ADR-005: um
        cliente que fale o contrato 1.0.0 não pode receber chave que ele não
        conhece com valor nulo e ter que distinguir "ausente" de "vazio".
        """
        body: dict = {
            "text": answer.text,
            "refused": answer.refused,
            "hits": [self.hit(h) for h in answer.hits],
            "timings": {
                "rewrite_s": round(answer.rewrite_s, 3),
                "search_s": round(answer.search_s, 3),
                "generation_s": round(answer.generation_s, 3),
            },
            "rewritten_question": {
                "used": answer.rewrite.used,
                "original": answer.rewrite.original,
                "rewritten": answer.rewrite.rewritten,
                "reason": answer.rewrite.reason,
            },
        }

        if answer.citations:
            body["citations"] = [self.citation(c) for c in answer.citations]

        if answer.unresolved_labels:
            # `meta` é o lugar certo para o que é específico deste projeto: o
            # contrato o declara como "extras do projeto". Um rótulo que o
            # modelo citou e que não existe entre os trechos é anomalia
            # diagnosticável, não parte do contrato compartilhado.
            body["meta"] = {"unresolved_labels": answer.unresolved_labels}

        return body

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
