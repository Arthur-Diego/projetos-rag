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

from ..domain.models import Answer, IngestionReport
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

    def answer(self, answer: Answer) -> None:
        self.rewrite(answer)

        if answer.hits:
            best = min(h.distance for h in answer.hits)
            self.diagnostic(
                f"[busca: {len(answer.hits)} trecho(s), melhor distância {best:.4f}]"
            )

        self.diagnostic(
            f"[tempos: reescrita {answer.rewrite_s:.2f}s, "
            f"busca {answer.search_s:.2f}s, geração {answer.generation_s:.2f}s]"
        )

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
