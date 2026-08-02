"""Hierarquia de exceções do domínio.

Nenhuma camada deste pacote chama `sys.exit()`. Elas levantam; quem decide
encerrar o processo é o entrypoint, que é o único que sabe que existe um
processo. Uma camada que mata o interpretador não é reutilizável nem testável.

Convenção de nomes: código em inglês, mensagens ao usuário em português.

A matriz de tradução para status HTTP está na seção 6 do FDD
(`.compozy/tasks/pipeline-multimodal/_techspec.md`) e é implementada em
`rag/api/error_handlers.py` (task_04).
"""


class RagException(Exception):
    """Base de tudo que este pacote levanta deliberadamente."""


class InvalidConfigurationException(RagException):
    """Falta configuração, ou ela é internamente inconsistente.

    Vira 500: o culpado é quem configurou o processo, não quem chamou.
    """


class InvalidParameterException(RagException):
    """Um parâmetro da requisição está fora do domínio válido.

    Vira 422. Separada de `InvalidConfigurationException` porque o culpado é
    outro, e a distinção só existe se os tipos forem dois.
    """


class ServiceUnavailableException(RagException):
    """Uma dependência externa não respondeu (Chroma ou OpenAI).

    Vira 503. Inclui a falha no meio do enriquecimento: a ingestão para, as
    unidades já gravadas ficam, e a reexecução retoma pelo `doc_id` (ADR-003).
    """


class EmptyCorpusException(RagException):
    """Não há PDF de entrada para processar em `pdfs/`."""


class EmptyIndexException(RagException):
    """Consulta pedida contra uma coleção inexistente ou sem representações.

    Vira 409, e é verificada ANTES de qualquer chamada paga (precedente do
    rag-03): perguntar contra índice vazio não deve custar dinheiro.
    """


class PartitionFailedException(RagException):
    """A partição do PDF não produziu elementos, ou o `hi_res` falhou.

    Quase sempre significa dependência nativa ausente (poppler, tesseract) ou
    modelo de layout indisponível — o risco 2 do FDD. A contingência é
    `PARTITION_STRATEGY=fast` no `.env`, que destrava o pipeline sem tabelas.
    """
