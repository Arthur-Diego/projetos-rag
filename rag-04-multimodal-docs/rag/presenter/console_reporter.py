"""Apresentação no terminal.

**Único componente do pacote que escreve.** Uma política, um lugar: stdout
carrega o resultado, stderr carrega o diagnóstico. É o que permite
`python ingest.py 2> ingestao.log` separar as duas coisas.

Também é o adaptador da porta `IngestionLog` (`service/ingestion_log.py`): o
diagnóstico por estágio de uma ingestão que leva minutos chega aqui em tempo
real, em vez de esperar o relatório final. A facade não sabe que este arquivo
existe.

"""

import sys

from ..domain.models import Answer, IngestionReport, ResetReport, SearchHit


class ConsoleReporter:
    """Escreve resultado em stdout e diagnóstico em stderr."""

    def diagnostic(self, message: str) -> None:
        print(message, file=sys.stderr)

    def failure(self, message: str) -> None:
        """Erro previsto. Vai para stderr; quem encerra o processo é o entrypoint."""
        self.diagnostic(f"erro: {message}")

    def stage(self, message: str) -> None:
        """Implementa `IngestionLog`. Diagnóstico, então stderr."""
        self.diagnostic(message)

    def files(self, names: list[str]) -> None:
        """Lista o que vai ser ingerido, ANTES de ingerir.

        Se um PDF do corpus de controle aparecer aqui, pare: o glob deixou de
        ser `pdfs/*.pdf` e o critério de recusa morreu em silêncio.
        """
        self.diagnostic(f"ingerindo {len(names)} arquivo(s):")
        for name in names:
            self.diagnostic(f"  - {name}")

    def ingestion(self, report: IngestionReport) -> None:
        """O relatório final. Vai para stdout: é o RESULTADO da operação."""
        elements = report.elements
        print(
            f"{report.pages} página(s) renderam {report.chunks} unidade(s) "
            f"em {report.seconds:.1f}s"
        )
        # As três contagens SEMPRE, inclusive as zeradas. `tabelas: 0` é o sinal
        # do risco 1 do FDD, e omiti-lo por ser zero esconderia exatamente a
        # falha que este relatório existe para denunciar.
        print(
            f"elementos: {elements.textos} texto(s), {elements.tabelas} tabela(s), "
            f"{elements.imagens} imagem(ns)"
        )
        if elements.tabelas == 0:
            self.diagnostic(
                "ATENÇÃO: nenhuma tabela foi detectada. Confira a estratégia de "
                "partição (hi_res?) e rode docs/operations/inspeciona-tabelas.py."
            )

    def index_opened(self, collection: str, total: int, k: int) -> None:
        self.diagnostic(f"coleção '{collection}': {total} representação(ões), k={k}")

    @staticmethod
    def _hit_line(position: int, hit: SearchHit) -> str:
        """Uma linha por fonte, com o selo de tipo à frente.

        O `kind` aparece porque é a resposta observável da pergunta que o projeto
        inteiro faz: a tabela chegou ao prompt? Sem ele, uma resposta correta
        vinda só de texto narrativo seria indistinguível de uma que usou a
        tabela, e o critério de sucesso do guia viraria opinião.
        """
        parts = [f"[{hit.kind}] {hit.source} p.{hit.page}"]
        if hit.score is not None:
            parts.append(f"similaridade {hit.score:.4f}")
        if hit.kind == "tabela":
            # O tamanho do HTML é a evidência barata de que o ORIGINAL foi
            # resolvido no docstore: o resumo tem centenas de caracteres, a
            # tabela tem milhares.
            html = hit.content_html or ""
            parts.append(f"HTML de {len(html)} caractere(s)")
        return f"  {position}. " + " | ".join(parts)

    def answer(self, answer: Answer) -> None:
        """A resposta em stdout; a evidência que a sustenta em stderr."""
        if answer.hits:
            self.diagnostic(f"[busca: {len(answer.hits)} trecho(s)]")
            for position, hit in enumerate(answer.hits, start=1):
                self.diagnostic(self._hit_line(position, hit))
            if not any(hit.kind == "tabela" for hit in answer.hits):
                self.diagnostic(
                    "  (nenhum hit de tabela nesta consulta — se a pergunta era "
                    "de célula, o resumo não casou com ela)"
                )

        times = ", ".join(
            f"{name} {value:.2f}s" for name, value in answer.timings.items()
        )
        self.diagnostic(f"[tempos: {times}]")

        if answer.refused:
            self.diagnostic("[RECUSOU: nada no contexto sustentava a resposta]")

        # O resultado, e só ele, vai para stdout.
        print(f"\n{answer.text}\n")

    def reset(self, report: ResetReport) -> None:
        """O que o reset apagou. Vai para stdout: é o RESULTADO da operação."""
        print(
            f"índice: {report.indexed_removed} representação(ões) apagada(s); "
            f"docstore: {report.originals_removed} original(is) apagado(s)"
        )
        self.diagnostic(
            "cache de partição preservado — a próxima ingestão não repaga o hi_res."
        )
