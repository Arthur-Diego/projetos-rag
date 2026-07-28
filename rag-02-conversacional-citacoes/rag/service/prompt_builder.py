"""Montagem do prompt de resposta.

É aqui que se compra o grounding. As instruções de fundamentação, de escape e
de citação são o que separa RAG de "LLM com texto colado no prompt".

Duas responsabilidades, e a segunda é nova em relação ao Projeto 1:

1. Instruir o modelo a responder SOMENTE do contexto, ou recusar com uma frase
   literal.
2. **Numerar os trechos** e exigir a referência pelo número. A numeração feita
   aqui é a mesma que o `CitationResolver` usa para resolver depois, e essa
   identidade é a invariante 5 do FDD.
"""

from ..domain.models import Conversation, RewriteDecision, SearchHit

ESCAPE_PHRASE = "Não encontrei essa informação nos documentos."
"""Contrato literal.

Os critérios de aceite comparam string, não interpretam. Mudar esta constante
quebra a validação do projeto.

É a MESMA string do `rag-01-fundamentos-pdf`, de propósito: permite comparar a
taxa de recusa entre os dois projetos, que é uma das coisas que o Projeto 2
existe para medir.
"""

# A frase aparece no template SEM aspas nem qualquer delimitador. Com aspas, o
# modelo as copia para a resposta e quebra a comparação literal. Isso foi
# encontrado na validação do Projeto 1, não previsto.
_ANSWER_TEMPLATE = """Responda a pergunta usando SOMENTE o contexto abaixo.

Cite as fontes no formato [n], usando o número que aparece antes de cada trecho,
ao final de cada afirmação que você fizer. Cite apenas números que existem no
contexto. Nunca invente um número.

Se o contexto não contiver a resposta, responda com esta frase exata, sem aspas,
sem markdown, sem citação e sem acrescentar nada antes ou depois:
{escape}

Nunca use conhecimento próprio. Nunca complete lacunas do contexto.
{history}
Contexto:
{context}

Pergunta: {question}"""

_LITERAL_SUFFIX = """
(esta pergunta foi resolvida contra o histórico; o usuário digitou literalmente:
"{original}". Se a pergunta resolvida tiver mudado o assunto do que o usuário
perguntou, responda ao que ele perguntou.)"""

_HISTORY_BLOCK = """
Conversa até aqui, apenas para você entender o fio. Ela NÃO é fonte: nada dela
pode ser usado como fundamento de uma afirmação nova.
{turns}
"""


class PromptBuilder:
    """Monta o prompt final a partir da pergunta, dos trechos e da conversa."""

    @staticmethod
    def format_context(hits: list[SearchHit]) -> str:
        """Numera os trechos e cola a procedência a cada um.

        O identificador chega ao modelo JUNTO do texto, e não numa lista à
        parte. Numerar e pedir a referência pelo número reduz muito a invenção
        de citação, porque o modelo copia um rótulo curto em vez de gerar um
        nome de arquivo.

        A numeração é 1-based e é a fonte da verdade para o `CitationResolver`.
        """
        return "\n\n".join(
            f"[{i}] (fonte: {hit.source}, página {hit.page})\n{hit.text}"
            for i, hit in enumerate(hits, 1)
        )

    @staticmethod
    def format_history(conversation: Conversation) -> str:
        """Renderiza a conversa já truncada pela janela.

        Recebe a conversa como ela vai ser usada, não a íntegra: quem trunca é
        a facade, e ela trunca antes de chamar. Renderizar aqui a conversa
        inteira faria a janela existir no papel e não no prompt.
        """
        if not conversation:
            return ""
        turns = "\n".join(
            f"- Pergunta: {turn.question}\n  Resposta: {turn.answer}"
            for turn in conversation.turns
        )
        return _HISTORY_BLOCK.format(turns=turns)

    @staticmethod
    def format_question(decision: RewriteDecision) -> str:
        """A pergunta que o modelo vê: a resolvida, com a literal ao lado.

        **Este método é a correção de um defeito encontrado na validação.** A
        versão anterior mandava ao modelo a pergunta ORIGINAL enquanto a busca
        usava a reescrita. Com contexto perfeito sobre a capa de invisibilidade
        e a pergunta "E o que ela faz?", o modelo recusava: nada no prompt
        dizia a que "ela" se referia, e a instrução de não completar lacunas
        fazia o resto. A reescrita existe justamente para resolver isso, e
        usá-la só na busca desfazia metade do trabalho.

        Por que a original continua visível, em vez de mandar só a resolvida:
        é a mitigação do risco número 1 do FDD. Se a reescrita derrapar e
        trocar o assunto, o modelo tem como perceber, porque vê as duas. Mandar
        só a resolvida deixaria uma reescrita ruim invisível para quem responde.
        """
        if not decision.rewritten:
            return decision.used
        return decision.used + _LITERAL_SUFFIX.format(original=decision.original)

    def build(
        self,
        decision: RewriteDecision,
        hits: list[SearchHit],
        conversation: Conversation = Conversation(),
    ) -> str:
        return _ANSWER_TEMPLATE.format(
            escape=ESCAPE_PHRASE,
            history=self.format_history(conversation),
            context=self.format_context(hits),
            question=self.format_question(decision),
        )
