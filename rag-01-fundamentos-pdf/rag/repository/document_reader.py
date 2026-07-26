"""Leitura dos documentos de entrada.

Camada de repositório: fala com a fonte externa (sistema de arquivos) e devolve
objetos de domínio. Muda quando for preciso suportar outro formato de entrada,
e por nenhum outro motivo.
"""

from pathlib import Path
from typing import Protocol

from langchain_core.documents import Document

from ..exceptions import EmptyCorpusException, NoExtractableTextException


class DocumentReader(Protocol):
    """Contrato de qualquer fonte de documentos."""

    def files(self) -> list[Path]:
        """Os arquivos que serão lidos, antes de lê-los."""
        ...

    def read(self) -> tuple[list[Document], int]:
        """Documentos com texto e quantos foram descartados por estarem vazios."""
        ...


class PdfDocumentReader:
    """Lê PDFs de uma pasta, um Document por página.

    O glob é NÃO recursivo, e isso é invariante de projeto, não conveniência:
    pdfs/fora-do-corpus/ precisa ficar fora do índice porque é o corpus de
    controle do teste negativo de grounding (ADR-004). Trocar por rglob destrói
    esse teste em silêncio, sem erro nem aviso.
    """

    def __init__(self, directory: Path) -> None:
        self._directory = directory

    def files(self) -> list[Path]:
        return sorted(self._directory.glob("*.pdf"))  # NÃO recursivo

    def read(self) -> tuple[list[Document], int]:
        # Import local: o pacote langchain_community emite DeprecationWarning
        # na importação, e não queremos o aviso em quem só usa o Protocol.
        from langchain_community.document_loaders import PyPDFLoader

        if not self._directory.is_dir():
            raise EmptyCorpusException(f"pasta {self._directory}/ não existe.")

        files = self.files()
        if not files:
            raise EmptyCorpusException(
                f"nenhum .pdf em {self._directory}/ "
                "(o glob não é recursivo, por desenho)."
            )

        pages: list[Document] = []
        discarded = 0
        for path in files:
            for page in PyPDFLoader(str(path)).load():
                if page.page_content.strip():
                    pages.append(page)
                else:
                    discarded += 1

        if not pages:
            raise NoExtractableTextException(
                "nenhuma página produziu texto.\n"
                "       hipótese provável: PDF escaneado (imagem sem camada de texto).\n"
                "       isso é o assunto do Projeto 4, não deste."
            )
        return pages, discarded
