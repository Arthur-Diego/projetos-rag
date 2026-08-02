"""O caminho denso do funil: busca por significado.

**Este serviço DELEGA ao repositório e não acrescenta política.** A decisão de
criá-lo assim foi consciente e está registrada no ADR-009; ela troca uma regra da
guideline por legibilidade da pasta, e quem ler depois precisa saber que foi
escolha e não descuido.

O que ele existe para dar: `rag/service/retrieval/` passa a conter as QUATRO
etapas do funil como pares (denso, léxico, fusão, reordenação), em vez de duas
delas aqui e duas em `repository/`. Abrir a pasta passa a contar a história
inteira.

**Por que embeddings falham em termo literal**, que é o motivo de existir o
caminho irmão: um vetor representa significado, e um código não tem significado a
representar. `E-4021` e `E-4022` produzem vetores quase idênticos. Este caminho
acerta o sinônimo e erra o token exato; o `KeywordSearchService` faz o inverso.
"""

from ...domain.models import SearchHit
from ...repository.vector_repository import VectorRepository


class DenseSearchService:
    """Busca por proximidade vetorial, e dona da contagem do índice.

    **Delega DOIS métodos, enquanto o serviço léxico delega um**, e a assimetria é
    real em vez de simetria forçada: o repositório denso é o dono do índice e do
    mapping (ADR-001), então é dele que sai a contagem que o `require_index`
    consulta. O caminho léxico só consulta o índice que o outro criou.
    """

    def __init__(self, repository: VectorRepository) -> None:
        self._repository = repository

    def search(self, query: str, k: int) -> list[SearchHit]:
        """Os `k` trechos mais próximos da pergunta no espaço vetorial.

        Embute duas idas à rede: uma para a API de embeddings, que converte a
        pergunta em vetor, e outra para o motor de busca. A primeira responde
        pela quase totalidade do tempo, e é o argumento do ADR-006 para não
        paralelizar os dois caminhos antes de medir.
        """
        return self._repository.search(query, k)

    def indexed_count(self) -> int:
        """Quantos trechos existem. Zero também significa "não existe"."""
        return self._repository.count()
