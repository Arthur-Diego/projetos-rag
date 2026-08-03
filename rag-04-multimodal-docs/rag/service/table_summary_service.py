"""Resumo de tabela: a representação que EMBEDA bem (ADR-002).

O problema que este serviço resolve, e que é o objeto do projeto: o HTML de uma
tabela responde muito bem e embeda muito mal. `<td>129,6</td>` não casa com
"qual foi a receita no 3T24?" por nenhuma medida de similaridade — os termos da
pergunta não estão lá. O resumo em linguagem natural casa; o HTML responde. Por
isso um vai para o índice e o outro para o docstore.

**Não há `Protocol` aqui, e a ausência é decisão registrada (ADR-006).** Resumir
tabela é texto para texto usando o mesmo cliente de LLM da geração: não existe
segunda implementação plausível que não seja "outro provedor de LLM", e isso é
uma decisão de outro tamanho. O ponto de troca real — e o ponto de substituição
nos testes — é o modelo injetado, que já chega atrás da interface `Runnable` do
LangChain. Interface sem segunda implementação plausível é camada vazia.
"""

from langchain_core.language_models import BaseChatModel, LanguageModelInput
from langchain_core.messages import BaseMessage, HumanMessage

from ..config import MAX_CONCURRENCY
from ..exceptions import ServiceUnavailableException

#: O prompt do guia, e as quatro exigências dele não são decorativas: cada uma
#: é um jeito de a pergunta do usuário casar com o resumo.
#:
#: - ENTIDADES e NOMES DE COLUNA trazem para o resumo as palavras que a pergunta
#:   vai usar ("receita de vendas", "EBITDA"), que no HTML estão em `<th>` e
#:   diluídas entre marcação.
#: - MÉTRICAS e PERÍODO ancoram a tabela no tempo ("3T24"), que é metade de
#:   qualquer pergunta sobre relatório trimestral.
#:
#: A ordem "descreva, não transcreva" é deliberada: um resumo que repete os
#: números vira uma segunda cópia ruim da tabela e reintroduz o problema de
#: embedar dígitos.
SUMMARY_PROMPT = """Você recebe uma tabela extraída de um relatório financeiro, em HTML.

Escreva um resumo em português, de um parágrafo, que sirva para ENCONTRAR esta
tabela numa busca. Inclua obrigatoriamente:

- as entidades de que a tabela trata (empresa, segmento, produto);
- as métricas apresentadas e os nomes das colunas, com as palavras exatas usadas;
- o período coberto (trimestre, ano, intervalo).

Descreva o que a tabela contém; não transcreva os números célula a célula.
Responda apenas com o resumo, sem preâmbulo.

Tabela:
{table}
"""


class TableSummaryService:
    """Resume tabelas em lote, com concorrência limitada."""

    def __init__(
        self,
        model: BaseChatModel,
        max_concurrency: int = MAX_CONCURRENCY,
    ) -> None:
        self._model = model
        self._max_concurrency = max_concurrency
        self._tokens = 0

    @property
    def tokens(self) -> int:
        """Tokens gastos até agora. Alimenta o log de custo do estágio pago."""
        return self._tokens

    def summarize(self, tables: list[str]) -> list[str]:
        """Um resumo por tabela, na mesma ordem da entrada.

        `batch` com `max_concurrency`: cinco chamadas simultâneas é o teto
        adotado na trilha para não esbarrar em rate limit da OpenAI. Sequencial
        seria seguro e lento demais num relatório com uma dúzia de tabelas;
        sem teto, o rate limit transformaria a ingestão inteira em 503.

        Raises:
            ServiceUnavailableException: se a API não respondeu. As unidades já
                gravadas ficam, e a reexecução retoma pelo `doc_id`.
        """
        if not tables:
            return []

        prompts: list[LanguageModelInput] = [
            [HumanMessage(content=SUMMARY_PROMPT.format(table=table))]
            for table in tables
        ]
        try:
            responses = self._model.batch(
                prompts, config={"max_concurrency": self._max_concurrency}
            )
        except Exception as e:
            raise ServiceUnavailableException(
                f"a API de resumo não respondeu ({type(e).__name__}).\n"
                "       as unidades já gravadas FICAM; rode de novo para retomar."
            ) from e

        return [self._text_of(response) for response in responses]

    def _text_of(self, message: BaseMessage) -> str:
        usage = getattr(message, "usage_metadata", None)
        if usage:
            self._tokens += int(usage.get("total_tokens", 0))
        content = message.content
        return content.strip() if isinstance(content, str) else str(content).strip()
