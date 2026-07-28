"""Resolução dos rótulos [n] do texto gerado.

Componente novo deste projeto, e a razão de ele existir isolado é o ADR-004.

O caminho barato seria implícito: o cliente lê `[3]` e pega o terceiro item de
`hits`. Ele falha do pior jeito possível, porque qualquer dedup, reordenação ou
filtro de `hits` entre a geração e a exibição faz `[3]` apontar para outro
trecho SEM ERRO, SEM LOG, SEM SINTOMA. A resposta continua bem formada, a
citação continua presente, e ela passou a mentir.

Aqui a resolução acontece uma vez, contra a MESMA lista que o `PromptBuilder`
numerou, e o resultado é materializado em `Citation` antes de qualquer camada
de apresentação existir. É a invariante 5 do FDD: `hits` é construído uma vez e
não é reordenado entre a numeração e a resolução.
"""

import re

from ..domain.models import Citation, SearchHit

#: Tamanho do trecho guardado na citação. Suficiente para reconhecer a passagem
#: ao abrir a página, curto o bastante para caber numa interface.
EXCERPT_CHARS = 280

_LABEL = re.compile(r"\[(\d+)\]")


class CitationResolver:
    """Extrai os rótulos citados e os liga aos trechos que os sustentam."""

    def resolve(
        self, text: str, hits: list[SearchHit]
    ) -> tuple[list[Citation], list[int]]:
        """Devolve as citações resolvidas e os rótulos que não resolveram.

        Rótulo fora de 1..len(hits) NÃO vira citação e NÃO é engolido: ele sai
        na segunda lista, que a facade expõe em `meta.unresolved_labels` e
        registra em log. O modelo citar [7] quando só houve quatro trechos é o
        caso fácil de detectar, e detectá-lo é barato: o caro seria descobrir
        depois que a citação estava errada e não havia registro.

        Deduplica preservando a ordem de primeira aparição: uma resposta que
        cita [1] três vezes tem uma citação, não três.
        """
        resolved: list[Citation] = []
        unresolved: list[int] = []
        seen: set[int] = set()

        for match in _LABEL.finditer(text):
            label = int(match.group(1))
            if label in seen:
                continue
            seen.add(label)

            if 1 <= label <= len(hits):
                hit = hits[label - 1]
                resolved.append(
                    Citation(
                        label=label,
                        source=hit.source,
                        page=hit.page,
                        excerpt=" ".join(hit.text.split())[:EXCERPT_CHARS],
                    )
                )
            else:
                unresolved.append(label)

        return resolved, unresolved
