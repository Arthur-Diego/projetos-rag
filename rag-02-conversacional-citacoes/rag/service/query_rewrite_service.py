"""Reescrita da pergunta contra o histórico (history-aware retrieval).

O componente central deste projeto. Sem ele, a segunda pergunta de um diálogo
é embedada fora de contexto: "e se eu vender dez?" vira um vetor sobre vender
coisas, o retriever traz lixo, e o modelo responde em cima do lixo sem que nada
na saída denuncie a falha.

Duas decisões estão codificadas aqui, e as duas têm modo de falha conhecido:

1. **Quando reescrever.** Reescrever custa uma chamada de LLM por turno. A
   heurística léxica evita parte disso sem gastar nada, e erra de um jeito
   documentado (ver `_needs_rewrite`).
2. **Como reescrever.** O prompt resolve referências e NÃO completa lacunas. Um
   prompt que "ajuda" o usuário a formular melhor a pergunta pode transformar
   uma pergunta fora do corpus numa que parece pertencer a ele, e aí o sistema
   responde em vez de recusar. É o risco central do FDD.
"""

import re
import unicodedata
from typing import Final

from ..domain.models import (
    REASON_ANAPHORIC_MARKER,
    REASON_FIRST_TURN,
    REASON_HISTORY_PRESENT,
    REASON_REWRITE_FAILED,
    REASON_SELF_CONTAINED,
    REASON_SHORT_QUESTION,
    Conversation,
    RewriteDecision,
)
from .generation_service import GenerationService

#: Abaixo disto, a pergunta é curta demais para ser autossuficiente num diálogo.
#: Hipótese inicial do FDD, sujeita à medição do critério 5 do PRD.
SHORT_QUESTION_WORDS: Final = 8

#: Pronomes e advérbios que, sozinhos, denunciam referência a algo anterior.
_ANAPHORIC_TOKENS: Final = frozenset({
    "ele", "ela", "eles", "elas",
    "isso", "isto", "esse", "essa", "esses", "essas",
    "aquele", "aquela", "aqueles", "aquelas",
    "dele", "dela", "disso", "nesse", "nessa", "nisso",
    "ai", "la",
})

#: Locuções que só disparam como sequência. Casadas com fronteira de palavra
#: sobre o texto normalizado.
_ANAPHORIC_PHRASES: Final = (
    "o mesmo", "a mesma", "nesse caso", "nessa situacao",
    "e se", "e quando", "e no", "e na", "e nesse",
)

#: Pergunta que começa com conjunção está, quase sempre, emendando a anterior.
_LEADING_CONJUNCTIONS: Final = frozenset({"e", "mas", "ou", "entao", "porem"})

_REWRITE_TEMPLATE = """Dado o histórico da conversa e a última pergunta do usuário,
reescreva a pergunta de forma que ela faça sentido SOZINHA, sem o histórico.

Resolva pronomes e referências implícitas usando o histórico.
NÃO responda a pergunta.
NÃO acrescente assunto, entidade ou termo que não esteja na pergunta original
nem no histórico: você resolve referências, não completa lacunas.
Se a pergunta já for autossuficiente, devolva-a exatamente como está.
Responda apenas com a pergunta reescrita, sem aspas e sem comentário.

Histórico:
{history}

Pergunta: {question}"""


def _normalize(text: str) -> str:
    """Minúsculas e sem acento, para a heurística não depender de digitação."""
    decomposed = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in decomposed if not unicodedata.combining(c))


class QueryRewriteService:
    """Decide se reescreve, e reescreve.

    Devolve sempre uma `RewriteDecision`, inclusive quando não reescreve: o
    critério 2 do PRD exige que a decisão seja visível em toda resposta, e um
    retorno opcional convidaria a omiti-la quando "não houve nada de
    interessante".
    """

    def __init__(
        self,
        generation: GenerationService,
        conditional: bool = False,
        short_question_words: int = SHORT_QUESTION_WORDS,
    ) -> None:
        self._generation = generation
        self._conditional = conditional
        self._short_question_words = short_question_words

    def _needs_rewrite(self, question: str) -> str | None:
        """Heurística léxica. Devolve o motivo do disparo, ou None.

        **Modo de falha conhecido, e ele é entregável.** Uma pergunta longa, sem
        pronome e sem conjunção inicial, e ainda assim dependente do turno
        anterior, passa batido. Exemplo real do FDD:

            "quantos dias posso converter em abono pecuniário considerando o
             período aquisitivo mencionado"

        `mencionado` refere-se ao turno anterior e nenhum gatilho pega. O
        critério 5 do PRD exige registrar um caso assim, e é por isso que
        `conditional` nasce desligado: o caminho correto e mais caro é o padrão.
        """
        normalized = _normalize(question)
        tokens = re.findall(r"\w+", normalized)

        if len(tokens) < self._short_question_words:
            return REASON_SHORT_QUESTION

        # Token inteiro, nunca substring: `essencial` não pode disparar `esse`.
        if _ANAPHORIC_TOKENS.intersection(tokens):
            return REASON_ANAPHORIC_MARKER

        if any(
            re.search(rf"\b{re.escape(phrase)}\b", normalized)
            for phrase in _ANAPHORIC_PHRASES
        ):
            return REASON_ANAPHORIC_MARKER

        if tokens and tokens[0] in _LEADING_CONJUNCTIONS:
            return REASON_ANAPHORIC_MARKER

        return None

    def _rewrite(self, question: str, conversation: Conversation) -> str:
        history = "\n".join(
            f"- Pergunta: {turn.question}\n  Resposta: {turn.answer}"
            for turn in conversation.turns
        )
        prompt = _REWRITE_TEMPLATE.format(history=history, question=question)
        rewritten = self._generation.generate(prompt).strip()

        # O modelo às vezes devolve entre aspas apesar da instrução. Tirar aqui
        # evita que a aspa entre no vetor de busca e desloque o embedding.
        if len(rewritten) >= 2 and rewritten[0] in "\"'" and rewritten[-1] == rewritten[0]:
            rewritten = rewritten[1:-1].strip()

        if not rewritten:
            raise ValueError("reescrita devolveu texto vazio")
        return rewritten

    def decide(self, question: str, conversation: Conversation) -> RewriteDecision:
        """Devolve a query a buscar e por que ela é o que é.

        Nunca levanta: falha de reescrita é degradação, não erro. Cair para a
        pergunta original devolve o comportamento do Projeto 1, e o `reason`
        deixa isso visível em vez de silencioso.
        """
        if not conversation:
            # Primeiro turno: não há o que resolver, e não se gasta chamada.
            return RewriteDecision(
                used=question,
                original=question,
                rewritten=False,
                reason=REASON_FIRST_TURN,
            )

        if self._conditional:
            trigger = self._needs_rewrite(question)
            if trigger is None:
                return RewriteDecision(
                    used=question,
                    original=question,
                    rewritten=False,
                    reason=REASON_SELF_CONTAINED,
                )
            reason = trigger
        else:
            reason = REASON_HISTORY_PRESENT

        try:
            used = self._rewrite(question, conversation)
        except Exception:
            # Timeout, erro da OpenAI ou devolução vazia. NÃO derruba a
            # requisição: o único fallback de todo o fluxo, e ele é visível.
            return RewriteDecision(
                used=question,
                original=question,
                rewritten=False,
                reason=REASON_REWRITE_FAILED,
            )

        return RewriteDecision(
            used=used,
            original=question,
            rewritten=True,
            reason=reason,
        )
