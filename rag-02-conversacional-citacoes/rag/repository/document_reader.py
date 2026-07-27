"""Leitura dos documentos de entrada.

Camada de repositório: tudo que fala com o mundo externo. Aqui o mundo externo
é o sistema de arquivos e o formato PDF.

O que sobe daqui é domínio puro (`Page`), com a página já 1-based. O pypdf
numera a partir de zero; converter aqui, uma vez, é o que evita a conversão
aparecer espalhada em três consumidores mais adiante.
"""

from pathlib import Path
from typing import Protocol

from pypdf import PdfReader

from ..domain.models import Page
from ..exceptions import EmptyCorpusException


class DocumentReader(Protocol):
    """Contrato de qualquer leitor de corpus."""

    def files(self) -> list[Path]:
        """Lista o que SERÁ lido, sem ler.

        Existe separado de `read()` porque o chamador precisa ver o que vai ser
        indexado ANTES do trabalho começar. É a mitigação registrada no FDD para
        o risco do glob recursivo: um corpus de controle indexado por engano
        aparece na listagem, em vez de ser descoberto quando o teste negativo
        parar de falhar.
        """
        ...

    def read(self) -> list[Page]:
        ...

    def total_pages(self) -> int:
        """Quantas páginas existem, com ou sem texto extraível.

        Faz parte do contrato porque a `IngestionFacade` a chama para calcular
        `discarded_pages`. Estava só na implementação concreta, e o mypy pegou:
        é exatamente o tipo de buraco que um `Protocol` esconde em runtime.
        """
        ...


class PdfDocumentReader:
    """Adaptador do pypdf sobre um diretório de PDFs."""

    def __init__(self, directory: Path) -> None:
        self._directory = directory

    def files(self) -> list[Path]:
        """Glob NÃO recursivo, e isso é uma decisão, não um descuido.

        `pdfs/*.pdf` alcança o corpus indexado. `pdfs/fora-do-corpus/*.pdf` fica
        deliberadamente fora: é o corpus de controle do teste negativo de
        grounding (critério 4 do PRD).

        Trocar por `**/*.pdf` indexa o corpus de controle e faz o critério 4
        passar a testar nada, SEM NENHUM SINTOMA. É a invariante 6 do FDD, e ela
        é verificável por grep justamente porque a falha é silenciosa.
        """
        return sorted(self._directory.glob("*.pdf"))

    def read(self) -> list[Page]:
        """Lê todas as páginas com texto extraível.

        Página sem texto é descartada em silêncio aqui e contada pelo chamador:
        PDF com uma capa em imagem é normal e não deve derrubar a ingestão. O
        corpus INTEIRO sem texto é outra coisa, e quem decide isso é a facade,
        que é quem conhece o total.

        Raises:
            EmptyCorpusException: se não há nenhum PDF no diretório.
        """
        paths = self.files()
        if not paths:
            raise EmptyCorpusException(
                f"nenhum PDF em {self._directory}.\n"
                "       coloque o corpus normativo lá e rode de novo."
            )

        pages: list[Page] = []
        for path in paths:
            reader = PdfReader(str(path))
            for index, page in enumerate(reader.pages, start=1):
                text = (page.extract_text() or "").strip()
                if text:
                    pages.append(Page(text=text, source=path.name, number=index))
        return pages

    def total_pages(self) -> int:
        """Quantas páginas existem, com ou sem texto.

        Necessário para `discarded_pages` do relatório: sem o total bruto, não
        há como dizer quantas páginas não renderam texto, e essa contagem é o
        primeiro sinal de PDF escaneado.
        """
        return sum(len(PdfReader(str(p)).pages) for p in self.files())
