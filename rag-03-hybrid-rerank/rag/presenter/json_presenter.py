"""Apresentação em JSON, conforme `../docs/contracts/rag-api.yaml` 1.2.0.

Irmão do ConsoleReporter: mesma camada, mesmo papel, saída diferente. A
existência dos dois é a prova de que a facade valeu.

Regra da camada: **nada aqui decide o que fazer, só como mostrar.** Em especial,
`refused` NÃO é calculado aqui, ao contrário do Projeto 1. Ele vem pronto do
domínio, porque a invariante "recusa não cita" precisa valer na facade, e uma
invariante que só existe na apresentação não vale em lugar nenhum.
"""

from ..domain.models import (
    Answer,
    Citation,
    IngestionReport,
    Provenance,
    SearchHit,
)
from ..service.citation_resolver import EXCERPT_CHARS


class JsonPresenter:
    """Converte objetos de domínio no formato do contrato compartilhado."""

    def hit(self, hit: SearchHit) -> dict:
        """Serializa um trecho recuperado.

        **`distance` e `score` são campos separados porque têm sentidos
        OPOSTOS**: menor é melhor em um, maior é melhor no outro. Escrever
        pontuação de fusão ou de reordenação no campo de distância inverteria a
        leitura no console, no frontend e nos testes de uma vez só, sem erro
        nenhum. É o risco de colisão de escala registrado na seção 10 do FDD.

        `distance` é emitido SEMPRE que o trecho passou pelo caminho denso, em
        qualquer configuração, com a semântica original preservada. Só fica
        ausente no trecho que veio exclusivamente do BM25, onde ele nunca teve
        valor: BM25 não mede distância nenhuma.
        """
        body: dict = {
            "source": hit.source,
            "page": hit.page,
            "excerpt": " ".join(hit.text.split())[:EXCERPT_CHARS],
        }

        if hit.distance is not None:
            body["distance"] = round(hit.distance, 4)

        if hit.score is not None:
            body["score"] = round(hit.score, 6)

        if hit.provenance is not None:
            body["provenance"] = self.provenance(hit.provenance)

        return body

    def provenance(self, provenance: Provenance) -> dict:
        """Serializa a procedência, OMITINDO o caminho que não executou.

        Ausente e zero são afirmações diferentes, e a distinção é toda a
        informação aqui: `keyword_rank` zerado significaria "o BM25 achou e pôs
        em primeiro", enquanto ausente significa "o BM25 não rodou, ou não achou
        este trecho". Emitir zero por conveniência transformaria a coluna mais
        importante da tabela de medição numa mentira.
        """
        body: dict = {"paths": list(provenance.paths)}
        for key, value in (
            ("dense_rank", provenance.dense_rank),
            ("keyword_rank", provenance.keyword_rank),
            ("rrf_score", provenance.rrf_score),
            ("rerank_score", provenance.rerank_score),
        ):
            if value is not None:
                body[key] = round(value, 6) if isinstance(value, float) else value
        return body

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
            # `search_s` MANTÉM o significado que sempre teve: o total do estágio
            # de recuperação. Os campos novos o DECOMPÕEM, e por isso quem somar
            # os cinco conta a recuperação duas vezes. Estágio que não executou é
            # OMITIDO, nunca emitido como zero: zero significaria "rodou e foi
            # instantâneo", que é afirmação diferente de "não rodou".
            "timings": {
                "rewrite_s": round(answer.rewrite_s, 3),
                "search_s": round(answer.search_s, 3),
                "generation_s": round(answer.generation_s, 3),
                **{
                    name: round(value, 3)
                    for name, value in (
                        ("dense_s", answer.dense_s),
                        ("keyword_s", answer.keyword_s),
                        ("fusion_s", answer.fusion_s),
                        ("rerank_s", answer.rerank_s),
                    )
                    if value is not None
                },
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
