"""Chamada ao modelo de linguagem que RESPONDE.

Atrás de um `Protocol` para que os testes usem um gerador determinístico sem
tocar em API paga — a matriz de recusa do FDD depende inteiramente disso — e
para que trocar de provedor seja escrever um adaptador.

**Por que aqui há `Protocol` e no `TableSummaryService` não** (ADR-006): lá o
único ponto de troca plausível é o MODELO, que já chega atrás de uma interface
do LangChain. Aqui o dublê precisa ser DETERMINÍSTICO e contável — os testes
perguntam "quantas vezes o gerador foi chamado?" para provar que o 409 de índice
vazio acontece ANTES de qualquer chamada paga.

Os retries com backoff exponencial ficam nas chamadas da OpenAI e só nelas
(seção 6 do FDD); eles vêm configurados de `openai_models.create_chat_model`,
num lugar só, junto do timeout.
"""

from typing import Protocol

from langchain_core.language_models import BaseChatModel

from ..exceptions import ServiceUnavailableException


class GenerationService(Protocol):
    """Contrato de qualquer gerador de texto."""

    def generate(self, prompt: str) -> str:
        """Devolve a resposta do modelo para o prompt já montado."""
        ...


class OpenAiGenerationService:
    """Adaptador do `gpt-4o-mini` para o estágio de resposta.

    Recebe o modelo pronto em vez de construí-lo: os parâmetros de resiliência
    (timeout, retries) e a temperatura zero moram em `openai_models`, e
    duplicá-los aqui garantiria que um dos dois pontos ficasse para trás no dia
    em que o timeout mudasse.
    """

    def __init__(self, model: BaseChatModel) -> None:
        self._model = model

    def generate(self, prompt: str) -> str:
        """Gera a resposta, traduzindo falha externa na fronteira.

        A tradução não é zelo: sem ela um timeout da OpenAI sobe até o FastAPI e
        vira 500 em TEXTO PURO, fora do formato `Problem` do contrato. O cliente
        receberia "Internal Server Error" sem saber que a falha foi externa nem
        o que fazer. A matriz da seção 6 do FDD diz 503.
        """
        try:
            content = self._model.invoke(prompt).content
        except Exception as e:
            raise ServiceUnavailableException(
                f"a OpenAI não respondeu ({type(e).__name__}).\n"
                "       confira a chave, o crédito da conta e a conexão."
            ) from e

        # `.content` é str no caso normal, mas o tipo permite lista de blocos
        # (conteúdo multimodal). Coagimos aqui para honrar o `Protocol` em vez
        # de vazar um tipo que o resto do pipeline não espera.
        return content if isinstance(content, str) else str(content)
