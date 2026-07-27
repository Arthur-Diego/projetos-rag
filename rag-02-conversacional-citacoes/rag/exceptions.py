"""Hierarquia de exceções do domínio.

Nenhuma camada deste pacote chama sys.exit(). Elas levantam; quem decide
encerrar o processo é o entrypoint, que é o único que sabe que existe um
processo. Uma camada que mata o interpretador não é reutilizável nem testável.

Convenção de nomes: código em inglês, mensagens ao usuário em português.
"""


class RagException(Exception):
    """Base de tudo que este pacote levanta deliberadamente.

    Capture esta para tratar qualquer falha prevista; capture uma subclasse
    para tratar um caso específico.
    """


class InvalidConfigurationException(RagException):
    """Falta configuração, ou ela é internamente inconsistente."""


class InvalidParameterException(RagException):
    """Um parâmetro da requisição está fora do domínio válido.

    Separada de InvalidConfigurationException porque o culpado é outro: aqui
    quem errou foi quem chamou, não quem configurou. A camada HTTP traduz esta
    em 422 e aquela em 500, e a distinção só existe se os tipos forem dois.
    """


class ServiceUnavailableException(RagException):
    """Uma dependência externa não respondeu."""


class EmptyCorpusException(RagException):
    """Não há documento de entrada para processar."""


class NoExtractableTextException(RagException):
    """Os documentos existem mas não produziram texto.

    Quase sempre significa PDF escaneado: imagem sem camada de texto.
    """


class EmptyIndexException(RagException):
    """Consulta pedida contra uma coleção inexistente ou sem chunks."""
