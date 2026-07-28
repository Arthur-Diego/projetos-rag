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


class InvalidIndexMappingException(RagException):
    """O índice existe e tem dados, mas o campo de texto não serve para BM25.

    **Esta exceção existe contra o risco mais grave do projeto.** Se o campo de
    texto for mapeado como valor único em vez de texto analisado, a busca por
    palavra exata passa a casar apenas o campo inteiro e nunca os termos. Metade
    do funil para de funcionar SEM ERRO NENHUM, e a conclusão registrada seria
    "a busca híbrida não ajudou" quando a verdade é que ela nunca rodou.

    Separada de InvalidConfigurationException por dois motivos. O culpado é
    outro: aqui o índice é que está no estado errado, e a correção é reindexar,
    não reconfigurar. E o status também: esta vira 409, junto de
    EmptyIndexException, porque as duas dizem "o índice precisa ser
    reconstruído"; InvalidConfigurationException vira 500.

    **Só é levantada quando o caminho léxico é pedido** (`hibrida` ligado). Com
    ele desligado a consulta passa, porque a busca densa não depende deste campo
    e não há nada de errado com ela, e a configuração puramente densa é a linha
    de base da tabela de medição.
    """
