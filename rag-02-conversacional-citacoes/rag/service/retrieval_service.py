"""Política de recuperação.

Separado do repositório de propósito: o repositório sabe guardar e consultar,
este serviço sabe QUANTO trazer e sob que critério. Mudar k, ordenação ou
filtro mexe aqui, não no adaptador do banco.

Este componente ficou de fora da tabela de componentes do HLD por omissão, e a
omissão tinha consequência: sem ele, o `EmptyIndexException` que vira 409 não
tem dono, e a validação de `k` acabaria espalhada entre a rota e a facade.

Não há limiar de distância, por decisão registrada no HLD e reafirmada no FDD.
O armazém devolve os k mais próximos SEMPRE, mesmo quando todos são ruins. Quem
pode recusar é o prompt, e só depois da geração.
"""

from ..config import MAX_K
from ..domain.models import SearchHit
from ..exceptions import EmptyIndexException, InvalidParameterException
from ..repository.vector_repository import VectorRepository


class RetrievalService:
    """Traz os k chunks mais próximos da query de busca."""

    def __init__(self, repository: VectorRepository, k: int = 4) -> None:
        if k < 1:
            raise InvalidParameterException(f"k deve ser >= 1 (recebido: {k}).")
        if k > MAX_K:
            raise InvalidParameterException(
                f"k deve ser <= {MAX_K} (recebido: {k}). "
                "Acima disso o contexto dilui e a citação fica confusa."
            )
        self._repository = repository
        self.k = k

    def indexed_count(self) -> int:
        return self._repository.count()

    def require_index(self, collection: str) -> int:
        """Falha cedo se não há o que buscar.

        Chamado ANTES de qualquer chamada paga: um índice vazio não deve custar
        uma reescrita nem uma geração.

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

    def retrieve(self, query: str) -> list[SearchHit]:
        """Busca pela query JÁ RESOLVIDA, nunca pela pergunta original.

        Quem decide qual das duas é esta é a facade, a partir da
        `RewriteDecision`. Este serviço recebe texto e busca: se ele conhecesse
        a conversa, a política de reescrita teria dois donos.
        """
        return self._repository.search(query, k=self.k)
