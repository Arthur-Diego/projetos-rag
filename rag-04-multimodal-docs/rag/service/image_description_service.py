"""Descrição de imagem: a única representação de conteúdo visual (ADR-006).

Um gráfico de barras não tem texto que embede; nos projetos 1 a 3 ele
simplesmente não existia para o índice. Aqui ele vira descrição em linguagem
natural, e a descrição é ao mesmo tempo o que BUSCA (representação) e o que
RESPONDE (original) — é a única categoria em que as duas metades do multi-vector
coincidem, porque não há original textual por baixo.

**Este serviço está atrás de um `Protocol`, e a tabela vizinha não** — a
assimetria é o ADR-006 e tem motivo: descrever imagem é o único estágio cujo
custo por elemento é uma chamada de VISÃO paga, e o Apêndice C do guia aponta a
alternativa local (Ollama e afins) para zerar esse custo. A segunda
implementação é plausível e prevista; a do resumidor de tabela não é.

O precedente é o ADR-004 do rag-03: o reranker nasceu atrás de `Protocol`
prevendo a Cohere, e a previsão foi exercida antes do fim do projeto.

Como todo `Protocol` do projeto, este não é verificado em runtime — é por isso
que o mypy é obrigatório na suíte.
"""

import base64
import mimetypes
from pathlib import Path
from typing import Protocol

from langchain_core.language_models import BaseChatModel, LanguageModelInput
from langchain_core.messages import BaseMessage, HumanMessage

from ..config import MAX_CONCURRENCY
from ..exceptions import ServiceUnavailableException

#: Prompt QUALITATIVO, e a ressalva de precisão é parte do contrato com o
#: usuário (adr-003 da sessão de PRD): um modelo de visão lê tendência e forma
#: bem, e lê valor exato de um eixo mal. Pedir o número exato produziria um
#: número plausível e errado, que é o pior resultado possível num relatório
#: financeiro — pior que a recusa, porque não se distingue de um acerto.
DESCRIPTION_PROMPT = """Você recebe uma figura extraída de um relatório financeiro.

Descreva em português, em um parágrafo, o que a figura mostra: tipo de gráfico ou
imagem, o que está sendo comparado, as séries e categorias presentes, o período e
a TENDÊNCIA visível (subiu, caiu, estável).

Não afirme valores exatos lidos de eixo ou de rótulo. Quando um valor for
relevante, escreva-o como aproximação explícita ("cerca de"). Se a figura for
decorativa (logotipo, foto), diga isso francamente.

Responda apenas com a descrição, sem preâmbulo.
"""


class ImageDescriptionService(Protocol):
    """Contrato do descritor de imagens.

    Recebe caminhos de figuras, devolve descrições na mesma ordem. A
    implementação da v1 é a da OpenAI; um modelo de visão local é a segunda
    implementação prevista e não implementada (ADR-006).
    """

    def describe(self, figures: list[Path]) -> list[str]:
        ...

    @property
    def tokens(self) -> int:
        """Tokens gastos até agora, para o log de custo do estágio pago."""
        ...


class OpenAiImageDescriptionService:
    """Adaptador do `gpt-4o-mini` em modo visão."""

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
        return self._tokens

    def describe(self, figures: list[Path]) -> list[str]:
        """Uma descrição por figura, na mesma ordem da entrada.

        Raises:
            ServiceUnavailableException: se a API de visão não respondeu.
        """
        if not figures:
            return []

        prompts: list[LanguageModelInput] = [
            [self._message(figure)] for figure in figures
        ]
        try:
            responses = self._model.batch(
                prompts, config={"max_concurrency": self._max_concurrency}
            )
        except Exception as e:
            raise ServiceUnavailableException(
                f"a API de visão não respondeu ({type(e).__name__}).\n"
                "       as unidades já gravadas FICAM; rode de novo para retomar.\n"
                "       para ingerir sem custo de visão: "
                'options.descrever_imagens=false'
            ) from e

        return [self._text_of(response) for response in responses]

    def _message(self, figure: Path) -> HumanMessage:
        """A figura como `image_url` em base64, no formato que a API espera.

        Base64 embutido, e não URL: as figuras vivem em `data/figures/`, fora de
        qualquer servidor. Servir arquivo de mídia está declarado fora de escopo
        na v1 (ADR-004), então não existe URL para dar.
        """
        mime = mimetypes.guess_type(figure.name)[0] or "image/jpeg"
        payload = base64.b64encode(figure.read_bytes()).decode("ascii")
        return HumanMessage(
            content=[
                {"type": "text", "text": DESCRIPTION_PROMPT},
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:{mime};base64,{payload}"},
                },
            ]
        )

    def _text_of(self, message: BaseMessage) -> str:
        usage = getattr(message, "usage_metadata", None)
        if usage:
            self._tokens += int(usage.get("total_tokens", 0))
        content = message.content
        return content.strip() if isinstance(content, str) else str(content).strip()
