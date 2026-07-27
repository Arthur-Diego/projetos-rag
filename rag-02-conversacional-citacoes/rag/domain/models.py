"""Objetos de domínio.

Não se chamam Entity: entidade implica identidade e ciclo de vida persistido.
Estes são objetos de valor, definidos apenas pelo conteúdo.

Esta camada é folha: **não importa nada do projeto e nada do LangChain.** O
Projeto 1 carregava um `Document` do LangChain dentro do domínio; aqui não, e a
diferença é deliberada. Com `Citation` precisando de `source` e `page`, a
normalização passaria a existir em três consumidores; descê-la para o adaptador
exige que o que sobe já seja domínio puro.
"""

from typing import Final, NamedTuple


class Turn(NamedTuple):
    """Um par pergunta e resposta já ocorrido.

    `answer` guarda o texto como o backend devolveu, com os `[n]` inclusive: o
    estágio de reescrita lê a conversa, e os rótulos ajudam a resolver
    referências ("o artigo que você citou").
    """

    question: str
    answer: str


class Conversation(NamedTuple):
    """A transcrição, do turno mais antigo para o mais recente.

    Imutável, e é isso que a torna segura num fluxo com dois estágios de LLM:
    aplicar a janela não pode corromper a conversa original porque produz outra.

    Não existe `ConversationMemory` (ADR-003). O backend não guarda conversa
    (ADR-002); ela chega como argumento e vai embora com a resposta. Um serviço
    de memória aqui não teria o que guardar, e a única lógica associada é a
    janela, que é função pura sobre este valor.
    """

    turns: tuple[Turn, ...] = ()

    def last(self, n: int) -> "Conversation":
        """Janela de histórico. Devolve uma conversa nova; não muta esta.

        `n == 0` devolve conversa vazia, e isso é intencional: é como se
        desliga o histórico sem inventar outro parâmetro.
        """
        if n <= 0:
            return Conversation(())
        return Conversation(self.turns[-n:])

    def __bool__(self) -> bool:
        return bool(self.turns)


class Page(NamedTuple):
    """Uma página lida de um documento, antes de ser dividida.

    `number` é 1-based, para humanos. A conversão do 0-based do pypdf acontece
    no adaptador de leitura, uma vez só.
    """

    text: str
    source: str
    number: int


class Chunk(NamedTuple):
    """Um pedaço indexável, com a procedência preservada.

    A procedência viaja com o texto desde a leitura até a citação. Se ela se
    perder em qualquer etapa, `Citation` não tem como ser verificável, que é o
    ponto do projeto.
    """

    text: str
    source: str
    page: int


class SearchHit(NamedTuple):
    """Um chunk recuperado e sua DISTÂNCIA até a pergunta.

    Menor é mais próximo, não maior. Chamar de score inverteria a leitura na
    interface, e o contrato compartilhado é explícito quanto a isso.

    A conversão de qualquer similaridade que o armazém devolva para distância
    acontece dentro do adaptador (ADR-001).
    """

    text: str
    source: str
    page: int
    distance: float


class Citation(NamedTuple):
    """A ligação entre um rótulo [n] do texto gerado e o trecho que o sustenta.

    Existe para que a resolução NÃO dependa da posição em `hits` (ADR-004):
    dedup ou reordenação de `hits` faria `[3]` apontar para o trecho errado sem
    erro nenhum, produzindo uma citação que parece verificada e não está.

    `excerpt` carrega o texto junto de propósito: torna a citação
    autossuficiente mesmo se a lista de trechos sumir do caminho.
    """

    label: int
    source: str
    page: int
    excerpt: str


# Valores fechados de RewriteDecision.reason.
#
# Enumerados, e não texto livre, porque o critério 5 do PRD exige AGREGAR quantas
# chamadas de LLM a reescrita condicional evitou. Sobre string livre não se
# agrega nada.
REASON_FIRST_TURN: Final = "primeiro_turno"
REASON_HISTORY_PRESENT: Final = "historico_presente"
REASON_SHORT_QUESTION: Final = "pergunta_curta"
REASON_ANAPHORIC_MARKER: Final = "marcador_anaforico"
REASON_SELF_CONTAINED: Final = "pergunta_autossuficiente"
REASON_REWRITE_FAILED: Final = "reescrita_falhou"

#: Motivos em que NÃO houve chamada de LLM concluída com sucesso.
#: `timings.rewrite_s` vale 0.0 exatamente nos dois primeiros (invariante 3 do
#: FDD); `reescrita_falhou` tentou e gastou tempo, então não entra aqui.
REASONS_WITHOUT_CALL: Final = frozenset({REASON_FIRST_TURN, REASON_SELF_CONTAINED})


class RewriteDecision(NamedTuple):
    """O que foi buscado, o que o usuário digitou, e por que diferem.

    Não é conveniência de log. O critério 2 do PRD exige que a reescrita seja
    VISÍVEL: ver a pergunta ambígua virar uma pergunta autossuficiente é metade
    do que este projeto ensina. Por isso este objeto está no domínio e viaja em
    toda resposta, inclusive quando não houve reescrita.
    """

    used: str
    original: str
    rewritten: bool
    reason: str


class Answer(NamedTuple):
    """Resultado de uma consulta, com a evidência que a torna verificável.

    `refused` é campo de domínio, e não cálculo do presenter como era no
    Projeto 1. Sem isso, a invariante "recusa não cita" não é verificável na
    facade, que é onde ela precisa valer.
    """

    text: str
    hits: list[SearchHit]
    citations: list[Citation]
    unresolved_labels: list[int]
    refused: bool
    rewrite: RewriteDecision
    rewrite_s: float
    search_s: float
    generation_s: float


class IngestionReport(NamedTuple):
    """Resultado de uma indexação.

    `previous_chunks` maior que zero significa que havia coleção anterior e ela
    foi apagada. Recriar é decisão de desenho: acrescentar geraria duplicatas.
    """

    pages: int
    chunks: int
    discarded_pages: int
    previous_chunks: int
    chunk_size: int
    chunk_overlap: int
    seconds: float
