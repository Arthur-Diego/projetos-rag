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


# Nomes dos caminhos de recuperação. Enumerados, e não texto livre, porque a
# tabela de medição AGREGA por caminho e sobre string livre não se agrega nada.
PATH_DENSE: Final = "densa"
PATH_KEYWORD: Final = "bm25"


class Provenance(NamedTuple):
    """De onde o trecho veio e o que cada estágio do funil fez com ele.

    Não é enfeite de diagnóstico: é o DADO BRUTO da tabela de medição, que é o
    entregável do projeto (ADR-003). Sem isto não há como preencher as três
    colunas, e a pergunta "por que este trecho subiu?" não tem resposta.

    Ranks são 1-based, como as páginas: são para humanos lerem. Campo de caminho
    que não executou fica None, e o presenter o OMITE em vez de emitir zero,
    porque zero aqui significaria "ficou em primeiro lugar".
    """

    paths: tuple[str, ...]
    dense_rank: int | None = None
    keyword_rank: int | None = None
    rrf_score: float | None = None
    rerank_score: float | None = None


class SearchHit(NamedTuple):
    """Um chunk recuperado, com a evidência de por que está nesta posição.

    **Duas escalas OPOSTAS convivem aqui, e confundi-las é defeito silencioso.**

    `distance` é distância: MENOR é mais próximo. É a semântica original do
    Projeto 1, preservada, e vale apenas na configuração puramente densa. O
    `ConsoleReporter` imprime o mínimo como "melhor", e há teste afirmando
    `distance > 0.9` para o caso fora do corpus.

    `score` é pontuação: MAIOR é melhor. Carrega o valor do rerank quando ele
    rodou, e o da fusão quando não rodou.

    Escrever pontuação no campo de distância inverteria a leitura no console, no
    frontend e nos testes de uma vez só, sem erro nenhum. Por isso são campos
    separados, e o contrato 1.2.0 documenta cada um (ADR-005).

    A conversão de qualquer similaridade que o armazém devolva para distância
    acontece dentro do adaptador (ADR-001).
    """

    text: str
    source: str
    page: int
    #: Identidade do trecho indexado, preenchida pelo adaptador a partir do
    #: identificador do documento no armazém. É a chave de deduplicação da fusão
    #: (ADR-001). O guia da trilha usa `page_content[:200]` como chave, atalho
    #: que funde silenciosamente dois trechos distintos que começam igual.
    doc_id: str | None = None
    distance: float | None = None
    score: float | None = None
    provenance: Provenance | None = None


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
    # Decomposição de `search_s`, que MANTÉM o significado de total do estágio
    # de recuperação. Estágio que não executou fica None e é OMITIDO da
    # resposta, nunca emitido como zero: zero significaria "rodou e foi
    # instantâneo", que é afirmação diferente de "não rodou".
    dense_s: float | None = None
    keyword_s: float | None = None
    fusion_s: float | None = None
    rerank_s: float | None = None


class RetrievalResult(NamedTuple):
    """O que o funil produziu, e quanto custou cada estágio dele.

    Existe porque `retrieve()` devolvia `list[SearchHit]` e não havia canal para
    tempo (ADR-007). A `QueryFacade` cronometrava o estágio de fora, o que
    funcionava enquanto "buscar" era uma operação só. Com quatro etapas por
    dentro, medir de fora só produz um número agregado, e o agregado não
    responde onde o tempo foi gasto.

    O tempo sai pelo RETORNO, e não por atributo do serviço. A alternativa do
    canal lateral foi recusada no ADR-007 justamente por introduzir estado
    mutável: duas requisições concorrentes leriam o tempo uma da outra, e o
    defeito seria intermitente.

    Estágio não executado tem tempo None, nunca 0.0.
    """

    hits: list[SearchHit]
    dense_s: float | None = None
    keyword_s: float | None = None
    fusion_s: float | None = None
    rerank_s: float | None = None


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
