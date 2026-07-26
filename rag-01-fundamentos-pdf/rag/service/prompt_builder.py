"""Montagem do prompt.

É aqui que se compra o grounding. As instruções de fundamentação e de escape
são o que separa RAG de "LLM com texto colado no prompt".
"""

from ..domain.models import SearchHit

ESCAPE_PHRASE = "Não encontrei essa informação nos documentos."
"""Contrato literal.

Os critérios de aceite 3 e 4 do FDD verificam a recusa comparando string, não
interpretando. Mudar esta constante quebra a validação do projeto.
"""

# A frase aparece no template SEM aspas nem qualquer delimitador. Com aspas, o
# modelo as copia para a resposta e quebra a comparação literal. Isso foi
# encontrado na validação, não previsto: ver FDD, seção 5.
_TEMPLATE = """Responda a pergunta usando SOMENTE o contexto abaixo.
Se o contexto não contiver a resposta, responda com esta frase exata, sem aspas,
sem markdown e sem acrescentar nada antes ou depois:
{escape}
Nunca use conhecimento próprio. Nunca complete lacunas do contexto.

Contexto:
{context}

Pergunta: {question}"""


class PromptBuilder:
    """Monta o prompt final a partir da pergunta e dos trechos recuperados."""

    @staticmethod
    def format_context(hits: list[SearchHit]) -> str:
        """Numera os trechos para o modelo poder se referir a eles."""
        return "\n\n".join(
            f"[{i}] {hit.document.page_content}" for i, hit in enumerate(hits, 1)
        )

    def build(self, question: str, hits: list[SearchHit]) -> str:
        return _TEMPLATE.format(
            escape=ESCAPE_PHRASE,
            context=self.format_context(hits),
            question=question,
        )
