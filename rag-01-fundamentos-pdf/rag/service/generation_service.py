"""Chamada ao modelo de linguagem.

Isolado atrás de um Protocol para que trocar de provedor seja escrever um
adaptador, e para que os testes possam usar um gerador determinístico sem
tocar em API paga.
"""

from typing import Protocol

from langchain_openai import ChatOpenAI, OpenAIEmbeddings


class GenerationService(Protocol):
    """Contrato de qualquer gerador de resposta."""

    def generate(self, prompt: str) -> str:
        ...


class OpenAiGenerationService:
    """Adaptador do gpt-4o-mini.

    Temperatura 0 não é preferência: a mesma pergunta precisa dar a mesma
    resposta, senão não dá para comparar configurações de chunking (ADR-002).

    max_retries usa o backoff exponencial do próprio SDK da OpenAI, que retenta
    429 e 5xx mas NÃO retenta 401. Retentar não conserta chave errada, só
    atrasa o diagnóstico.
    """

    def __init__(self, model: str, temperature: float = 0.0, max_retries: int = 3) -> None:
        self._llm = ChatOpenAI(
            model=model,
            temperature=temperature,
            max_retries=max_retries,
        )

    def generate(self, prompt: str) -> str:
        content = self._llm.invoke(prompt).content
        # .content é str no caso normal, mas o tipo permite lista de blocos
        # (conteúdo multimodal). Coagimos para honrar o contrato do Protocol,
        # em vez de vazar um tipo que o resto do pipeline não espera.
        return content if isinstance(content, str) else str(content)


def create_embeddings(model: str, max_retries: int = 3) -> OpenAIEmbeddings:
    """Fábrica do modelo de embeddings.

    Vive aqui porque embedding e geração são o mesmo provedor e a mesma
    política de retentativa. Trocar de provedor mexe em um arquivo só.

    Atenção: mudar de modelo de embedding invalida a coleção inteira, porque a
    dimensão do vetor muda. Não existe migração, existe reindexação.
    """
    return OpenAIEmbeddings(model=model, max_retries=max_retries)
