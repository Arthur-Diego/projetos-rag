"""O caminho léxico do funil: busca por palavra exata (BM25).

**Este serviço DELEGA ao repositório e não acrescenta política.** Mesma decisão
consciente do irmão denso, registrada no ADR-009.

**Por que este caminho existe.** BM25 acerta o token exato e erra o sinônimo; a
busca densa faz o inverso. Em *EntityQuestions* (Sciavolino et al., EMNLP 2021), a
acurácia de recuperação em top-20 para perguntas sobre entidades é de 72,0% para
BM25 contra 49,7% para recuperação densa, e a diferença cresce conforme a entidade
fica mais rara. É a complementaridade que o projeto existe para medir.

Não gasta chamada paga: BM25 opera sobre os termos do texto, sem embedar nada.
"""

from ...domain.models import SearchHit
from ...repository.keyword_repository import KeywordRepository


class KeywordSearchService:
    """Busca por termos sobre o mesmo índice que o caminho denso alimenta.

    Um método só, contra os dois do `DenseSearchService`. O repositório denso é o
    dono do índice e do mapping (ADR-001); este apenas consulta o que o outro
    criou, e não tem contagem própria a expor.
    """

    def __init__(self, repository: KeywordRepository) -> None:
        self._repository = repository

    def search(self, query: str, k: int) -> list[SearchHit]:
        """Os `k` melhores por BM25.

        **O trecho devolvido não tem `distance`, e é deliberado.** BM25 não mede
        distância nenhuma: devolve pontuação sem teto, dependente da frequência
        dos termos no corpus, e onde MAIOR é melhor. Escrever esse número no campo
        cujo contrato é "menor é mais próximo" inverteria a leitura no console e
        no frontend sem erro nenhum.

        Se este método devolver lista vazia para um termo que existe no corpus, o
        mapping do índice está errado: o campo de texto virou valor único em vez
        de texto analisado. É o risco número um do projeto, e o que o critério de
        aceite 8 verifica.
        """
        return self._repository.search(query, k)
