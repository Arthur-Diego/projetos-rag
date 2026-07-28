"""Apresentação no terminal.

**Único componente do pacote que escreve.** Uma política, um lugar:
stdout carrega o resultado, stderr carrega o diagnóstico. É o que permite
`python ask.py "..." > resposta.txt` gravar só a resposta.

O que este projeto imprime a mais que o Projeto 1, e por quê:

- **A query reescrita, sempre.** Critério 2 do PRD. Ver a pergunta ambígua
  virar uma pergunta autossuficiente é metade do que este projeto ensina, e o
  que não aparece na tela não é aprendido.
- **As citações resolvidas.** Critério 3. Fonte e página ao lado do rótulo é o
  que torna a conferência manual barata, e o que é caro de conferir não é
  conferido.
"""

import sys

from ..domain.models import Answer, IngestionReport, SearchHit
from ..service.query_rewrite_service import SHORT_QUESTION_WORDS

_REASON_LABEL = {
    "primeiro_turno": "primeiro turno, sem histórico",
    "historico_presente": "há histórico, reescrita incondicional",
    "pergunta_curta": f"pergunta com menos de {SHORT_QUESTION_WORDS} palavras",
    "marcador_anaforico": "pergunta com referência implícita",
    "pergunta_autossuficiente": "pergunta já autossuficiente, reescrita pulada",
    "reescrita_falhou": "A REESCRITA FALHOU, usando a pergunta original",
}


class ConsoleReporter:
    """Escreve resultado em stdout e diagnóstico em stderr."""

    def diagnostic(self, message: str) -> None:
        print(message, file=sys.stderr)

    def failure(self, message: str) -> None:
        """Erro previsto. Vai para stderr; quem encerra o processo é o entrypoint."""
        self.diagnostic(f"erro: {message}")

    def index_opened(self, collection: str, total: int, k: int, window: int) -> None:
        self.diagnostic(
            f"coleção '{collection}': {total} chunks, k={k}, janela={window} turno(s)"
        )

    def files(self, names: list[str]) -> None:
        """Lista o que vai ser indexado, ANTES de indexar.

        Se um PDF do corpus de controle aparecer aqui, pare: o glob deixou de
        ser `pdfs/*.pdf` e o teste negativo do critério 4 morreu em silêncio.
        """
        self.diagnostic(f"indexando {len(names)} arquivo(s):")
        for name in names:
            self.diagnostic(f"  - {name}")

    def rewrite(self, answer: Answer) -> None:
        """A decisão de reescrita, sempre, mesmo quando não houve reescrita."""
        decision = answer.rewrite
        label = _REASON_LABEL.get(decision.reason, decision.reason)
        self.diagnostic(f"\n[reescrita: {label}]")
        if decision.rewritten:
            self.diagnostic(f"  original: {decision.original}")
            self.diagnostic(f"  buscado : {decision.used}")
        else:
            self.diagnostic(f"  buscado : {decision.used}")

    @staticmethod
    def _provenance(hit: SearchHit) -> str:
        """Uma linha explicando por que este trecho está nesta posição.

        É a resposta observável para a pergunta que o projeto inteiro faz. Sem
        ela, a ordem final do funil é mágica: não dá para distinguir "os dois
        caminhos acharam" de "um achou em primeiro e o outro em décimo nono", e
        é justamente essa diferença que explica uma promoção pela fusão.

        **`distância` e `score` nunca aparecem no mesmo rótulo**, porque têm
        sentidos opostos: menor é melhor na primeira, maior é melhor no segundo.
        Foi assim que o Projeto 2 imprimia "melhor distância" usando o mínimo, e
        escrever pontuação ali inverteria a leitura sem erro nenhum.
        """
        partes = [f"{hit.source} p.{hit.page}"]

        provenance = hit.provenance
        if provenance is not None:
            caminhos = []
            if provenance.dense_rank is not None:
                caminhos.append(f"densa #{provenance.dense_rank}")
            if provenance.keyword_rank is not None:
                caminhos.append(f"bm25 #{provenance.keyword_rank}")
            if caminhos:
                partes.append(" + ".join(caminhos))
            if provenance.rrf_score is not None:
                partes.append(f"rrf {provenance.rrf_score:.5f}")
            if provenance.rerank_score is not None:
                partes.append(f"rerank {provenance.rerank_score:.3f}")

        if hit.distance is not None:
            partes.append(f"distância {hit.distance:.4f}")

        return " | ".join(partes)

    def answer(self, answer: Answer) -> None:
        self.rewrite(answer)

        if answer.hits:
            self.diagnostic(f"[busca: {len(answer.hits)} trecho(s)]")
            for position, hit in enumerate(answer.hits, start=1):
                self.diagnostic(f"  {position}. {self._provenance(hit)}")

        # Só os estágios que RODARAM aparecem. Imprimir "rerank 0.00s" quando o
        # estágio estava desligado faria parecer que ele rodou e foi de graça,
        # que é a leitura errada exata.
        stages = [
            ("reescrita", answer.rewrite_s),
            ("densa", answer.dense_s),
            ("bm25", answer.keyword_s),
            ("fusão", answer.fusion_s),
            ("rerank", answer.rerank_s),
            ("busca total", answer.search_s),
            ("geração", answer.generation_s),
        ]
        medidos = ", ".join(
            f"{nome} {valor:.2f}s" for nome, valor in stages if valor is not None
        )
        self.diagnostic(f"[tempos: {medidos}]")

        if answer.refused:
            self.diagnostic("[RECUSOU: nada no contexto sustentava a resposta]")

        if answer.unresolved_labels:
            # Não é erro, mas precisa aparecer: o modelo citou um número que não
            # existe entre os trechos enviados.
            rotulos = ", ".join(f"[{n}]" for n in answer.unresolved_labels)
            self.diagnostic(f"[ATENÇÃO: rótulo(s) citado(s) sem trecho: {rotulos}]")

        # O resultado, e só ele, vai para stdout.
        print(f"\n{answer.text}\n")

        if answer.citations:
            self.diagnostic("Fontes citadas:")
            for citation in answer.citations:
                self.diagnostic(
                    f"  [{citation.label}] {citation.source}, página {citation.page}"
                )
                self.diagnostic(f"      {citation.excerpt}")

    def ingestion(self, report: IngestionReport) -> None:
        if report.previous_chunks:
            self.diagnostic(
                f"coleção anterior tinha {report.previous_chunks} chunks, "
                "recriada do zero"
            )
        self.diagnostic(
            f"{report.pages} página(s) com texto viraram {report.chunks} chunk(s) "
            f"(size={report.chunk_size}, overlap={report.chunk_overlap}) "
            f"em {report.seconds:.1f}s"
        )
        if report.discarded_pages:
            self.diagnostic(
                f"{report.discarded_pages} página(s) sem texto extraível, descartada(s). "
                "muitas assim significa PDF escaneado."
            )
