"""Política de recuperação.

Separado do repositório de propósito: o repositório sabe guardar e consultar,
este serviço sabe QUANTO trazer e sob que critério. Mudar k, ordenação ou
filtro mexe aqui, não no adaptador do banco.

Não há limiar de similaridade, por decisão registrada no HLD. O armazém devolve
os k mais próximos SEMPRE, mesmo quando todos são ruins. Sentir isso sem
proteção é o que dá sentido ao grading do Projeto 5.
"""

from ..domain.models import SearchHit
from ..exceptions import EmptyIndexException, InvalidConfigurationException
from ..repository.vector_repository import VectorRepository


class RetrievalService:
    """Traz os k chunks mais próximos da pergunta."""

    def __init__(self, repository: VectorRepository, k: int = 4) -> None:
        if k < 1:
            raise InvalidConfigurationException(f"--k deve ser >= 1 (recebido: {k}).")
        self._repository = repository
        self.k = k

    def indexed_count(self) -> int:
        return self._repository.count()

    def require_index(self, collection: str) -> int:
        """Falha cedo se não há o que buscar.

        Raises:
            EmptyIndexException: se a coleção não existe ou está sem chunks.
        """
        total = self.indexed_count()
        if not total:
            raise EmptyIndexException(
                f"coleção '{collection}' está vazia ou não existe.\n"
                "       rode primeiro: python ingest.py"
            )
        return total

    def retrieve(self, question: str) -> list[SearchHit]:
        return self._repository.search(question, k=self.k)
