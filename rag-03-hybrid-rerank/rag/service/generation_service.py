"""Chamada ao modelo de linguagem.

Isolado atrás de um Protocol para que trocar de provedor seja escrever um
adaptador, e para que os testes usem um gerador determinístico sem tocar em
API paga. A matriz de recusa do critério 4 do PRD depende inteiramente disso.

**Dois chamadores distintos usam este serviço**: o `QueryRewriteService`, para
reescrever a pergunta, e a `QueryFacade`, para gerar a resposta. É o mesmo
contrato e o mesmo adaptador; o que muda é só o prompt. Registrar isso importa
porque é a origem do custo dobrado por turno (risco no HLD e no FDD).
"""

from typing import Protocol

from langchain_openai import ChatOpenAI, OpenAIEmbeddings

from ..exceptions import ServiceUnavailableException


class GenerationService(Protocol):
    """Contrato de qualquer gerador de texto."""

    def generate(self, prompt: str) -> str:
        ...


class OpenAiGenerationService:
    """Adaptador do gpt-4o-mini.

    Temperatura 0 não é preferência: a mesma pergunta precisa dar a mesma
    resposta, senão não dá para comparar configurações entre execuções, e os
    critérios 5 e 6 do PRD são exatamente comparações entre execuções.

    max_retries usa o backoff exponencial do SDK da OpenAI, que retenta 429 e
    5xx mas NÃO retenta 401. Retentar não conserta chave errada, só atrasa o
    diagnóstico.
    """

    def __init__(
        self,
        model: str,
        temperature: float = 0.0,
        max_retries: int = 3,
        timeout_s: float = 60.0,
    ) -> None:
        self._llm = ChatOpenAI(
            model=model,
            temperature=temperature,
            max_retries=max_retries,
            timeout=timeout_s,
        )

    def generate(self, prompt: str) -> str:
        try:
            content = self._llm.invoke(prompt).content
        except Exception as e:
            # Traduzir na fronteira, e não deixar propagar.
            #
            # Sem isto, um timeout da OpenAI sobe até o FastAPI e vira 500 em
            # TEXTO PURO, fora do formato `Problem` que o contrato declara. O
            # cliente recebe "Internal Server Error" e não tem como saber que a
            # falha foi externa nem o que fazer.
            #
            # Nota para quem for depurar a reescrita: o QueryRewriteService
            # captura esta exceção e cai para a pergunta original, de propósito
            # (reason=reescrita_falhou). Só a falha do estágio de RESPOSTA chega
            # ao cliente como 503.
            raise ServiceUnavailableException(
                f"a OpenAI não respondeu ({type(e).__name__}).\n"
                "       confira a chave, o crédito da conta e a conexão."
            ) from e

        # .content é str no caso normal, mas o tipo permite lista de blocos
        # (conteúdo multimodal). Coagimos para honrar o contrato do Protocol,
        # em vez de vazar um tipo que o resto do pipeline não espera.
        return content if isinstance(content, str) else str(content)


def create_embeddings(
    model: str, max_retries: int = 3, timeout_s: float = 60.0
) -> OpenAIEmbeddings:
    """Fábrica do modelo de embeddings.

    Vive aqui porque embedding e geração são o mesmo provedor e a mesma
    política de retentativa. Trocar de provedor mexe em um arquivo só.

    Atenção: mudar de modelo de embedding invalida a coleção inteira, porque a
    dimensão do vetor muda. Não existe migração, existe reindexação. O
    HealthChecker detecta isso antes da primeira chamada paga.
    """
    return OpenAIEmbeddings(model=model, max_retries=max_retries, timeout=timeout_s)
