"""Porta de diagnóstico por estágio da ingestão.

Existe por causa de uma tensão real entre duas regras da guideline: a 2.3 diz
que **só o presenter escreve**, e a 2.2 diz que a facade não conhece o mundo de
fora. Mas a ingestão deste projeto leva MINUTOS na primeira execução, e um
processo que não diz nada por cinco minutos é indistinguível de um processo
travado. O relatório final, que é como o rag-03 resolvia, chega tarde demais.

A saída é a de sempre em arquitetura hexagonal: a camada que precisa do serviço
declara a PORTA; quem escreve de verdade implementa. `IngestionLog` mora em
`service/` porque é ali e na facade que ela é consumida; o `ConsoleReporter`
(presenter) é o adaptador. Nada em `service/` nem em `facade/` importa
`presenter`, e o grafo de camadas continua descendente.

`NullIngestionLog` é o default de todo consumidor: um serviço que exigisse log
para funcionar seria intestável sem um dublê, e log é diagnóstico, não
comportamento.
"""

from typing import Protocol


class IngestionLog(Protocol):
    """Diagnóstico por estágio. Nunca altera o resultado da ingestão."""

    def stage(self, message: str) -> None:
        """Registra uma linha de diagnóstico de um estágio concluído."""
        ...


class NullIngestionLog:
    """Não escreve nada. Default de quem recebe um log opcional."""

    def stage(self, message: str) -> None:
        return None
