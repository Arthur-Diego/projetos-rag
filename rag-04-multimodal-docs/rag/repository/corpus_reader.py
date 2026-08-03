"""Seleção dos PDFs de entrada.

Camada de repositório: o mundo externo aqui é o sistema de arquivos. Não lê o
conteúdo — quem particiona é o `PartitionService`, e a partição é cara. Este
módulo responde a uma pergunta barata: *quais arquivos entram?*
"""

from pathlib import Path
from typing import Protocol

from ..exceptions import EmptyCorpusException


class CorpusReader(Protocol):
    """Contrato de qualquer seleção de corpus."""

    def files(self) -> list[Path]:
        """Lista o que SERÁ ingerido, sem ingerir.

        Separado do resto do pipeline porque o operador precisa ver a lista
        ANTES do trabalho começar — e aqui o trabalho custa minutos de CPU e
        depois dinheiro. Um PDF do corpus de controle aparece nesta listagem em
        vez de ser descoberto quando o teste negativo de recusa parar de falhar.
        """
        ...

    def require_files(self) -> list[Path]:
        """Os arquivos, ou erro claro antes de qualquer custo.

        Separado de `files()` porque os dois chamadores querem coisas
        diferentes: quem só LISTA aceita a lista vazia, e quem vai INGERIR
        precisa que a ausência de corpus falhe antes dos minutos de CPU. Uma
        função só obrigaria um dos dois a tratar o caso do outro.

        Raises:
            EmptyCorpusException: se não há PDF no diretório.
        """
        ...


class PdfCorpusReader:
    """Diretório de PDFs, glob não recursivo."""

    def __init__(self, directory: Path) -> None:
        self._directory = directory

    def files(self) -> list[Path]:
        """Glob NÃO recursivo, e isso é uma decisão, não um descuido.

        `pdfs/*.pdf` alcança o corpus ingerido. `pdfs/fora-do-corpus/*.pdf` fica
        deliberadamente fora: é o corpus de controle do critério de recusa
        (US-008), a pergunta cuja resposta só existe num relatório nunca
        indexado.

        Trocar por `**/*.pdf` indexa o controle negativo e faz o critério passar
        a testar nada, SEM NENHUM SINTOMA — a recusa simplesmente para de
        acontecer e a leitura vira "o grounding piorou". É a EC-2 da US-001, e
        o teste T3.6 existe porque a falha é silenciosa.
        """
        return sorted(self._directory.glob("*.pdf"))

    def require_files(self) -> list[Path]:
        """Os arquivos, ou erro claro antes de qualquer custo.

        Raises:
            EmptyCorpusException: se não há PDF no diretório.
        """
        paths = self.files()
        if not paths:
            raise EmptyCorpusException(
                f"nenhum PDF em {self._directory}.\n"
                "       coloque o corpus lá e rode de novo."
            )
        return paths
