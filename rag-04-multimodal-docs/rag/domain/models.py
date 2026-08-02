"""Objetos de domínio.

Não se chamam Entity: entidade implica identidade e ciclo de vida persistido.
Estes são objetos de valor, definidos apenas pelo conteúdo.

Esta camada é folha: **não importa nada do projeto e nada do LangChain nem do
`unstructured`.** A tradução de `Element` do `unstructured` para `DocumentUnit`
acontece no `ElementRoutingService`, uma vez só; o que sobe daí é domínio puro.
(A task_01 previa essa tradução dentro do `PartitionService`; ela ficou num
serviço próprio porque particionar custa minutos e rotear custa microssegundos,
e juntá-los faria o teste do roteamento depender de particionar um PDF real.)
O mesmo vale para o `Document` do LangChain nos repositórios.

O vocabulário central do projeto é a separação do padrão multi-vector:
`DocumentUnit` carrega o ORIGINAL (o que responde bem, entregue ao LLM) e a
REPRESENTAÇÃO (o que embeda bem, indexada no Chroma). As duas metades andam
ligadas pelo `doc_id` (ADR-001).
"""

from typing import Literal, NamedTuple

#: As três categorias do pipeline. São os valores publicados em `SearchHit.kind`
#: pelo contrato 1.3.0, então estão em português: é o vocabulário do contrato,
#: não identificador interno.
Kind = Literal["texto", "tabela", "imagem"]


class DocumentUnit(NamedTuple):
    """Uma unidade indexável do PDF, com original e representação separados.

    `content` é o ORIGINAL íntegro que chega ao LLM na consulta: o texto cru
    para `kind=texto`, o HTML completo da tabela para `kind=tabela`, a descrição
    para `kind=imagem`.

    `representation` é o que vai ao índice. Para `kind=texto` é o próprio
    `content`, porque texto narrativo já embeda bem — o multi-vector aqui é
    SELETIVO (ADR-002), e resumir texto seria pagar por uma perda de informação.
    Para tabela é o resumo em linguagem natural; para imagem, a descrição.

    `figure_path` só existe para `kind=imagem`: o arquivo extraído em
    `data/figures/`. A v1 não serve a imagem ao frontend (fora de escopo,
    declarado no HLD); ela participa como descrição textual.
    """

    doc_id: str
    kind: Kind
    content: str
    representation: str
    source: str
    page: int
    figure_path: str | None = None


class ElementCounts(NamedTuple):
    """Contagem de unidades por categoria, publicada em `IngestionReport`.

    `tabelas: 0` é sinal do risco 1 do FDD (`hi_res` não detectou tabela
    nenhuma), e por isso é reportado explicitamente em vez de omitido.
    """

    textos: int = 0
    tabelas: int = 0
    imagens: int = 0


class IngestionReport(NamedTuple):
    """O que a ingestão devolve. Espelha o `IngestionReport` do contrato 1.3.0."""

    pages: int
    chunks: int
    seconds: float
    elements: ElementCounts


class SearchHit(NamedTuple):
    """Um trecho recuperado, já resolvido para o original no docstore.

    Espelha o `SearchHit` do contrato 1.3.0. Duas invariantes do FDD vivem aqui:
    `content_html` só é preenchido quando `kind == "tabela"`, e HTML nunca entra
    em `excerpt`. Campo ausente é omitido do JSON pelo presenter, nunca `null`.

    `excerpt` carrega o trecho para `kind=texto`, o resumo para `kind=tabela` e
    a descrição para `kind=imagem` — ou seja, sempre a REPRESENTAÇÃO. O original
    de uma tabela viaja em `content_html`.
    """

    source: str
    page: int
    kind: Kind
    excerpt: str
    score: float | None = None
    content_html: str | None = None


class IndexMatch(NamedTuple):
    """O que a busca densa devolve: um `doc_id` e o quão perto ele ficou.

    **Não é um `SearchHit`, e a distinção é o projeto inteiro.** Um match é o
    que o ÍNDICE sabe — o identificador da representação que casou com a
    pergunta. O `SearchHit` só existe depois que o original correspondente foi
    resolvido no docstore (ADR-001). Fundir os dois faria o resumo da tabela
    virar a resposta, que é exatamente o defeito que este projeto existe para
    não cometer.

    `distance` é DISTÂNCIA do cosseno: MENOR é mais próximo. O contrato publica
    `score`, que é pontuação e cresce ao contrário; a conversão acontece uma vez
    só, no `RetrievalService`, para que as duas escalas nunca convivam soltas.
    """

    doc_id: str
    distance: float


class RetrievalResult(NamedTuple):
    """O que a recuperação devolve: os hits e onde o tempo foi gasto.

    Métrica pelo RETORNO, e não por atributo do serviço (precedente do ADR-007
    do rag-03): tempo guardado em atributo é estado mutável, e duas requisições
    concorrentes leriam o tempo uma da outra.

    `discarded` conta os hits ÓRFÃOS — `doc_id` no índice sem original no
    docstore. Ele viaja no resultado porque a consulta segue normalmente (nunca
    500 por hit órfão), e sem essa contagem o sintoma da dessincronia seria uma
    resposta com menos fontes do que o `k` pedido, sem explicação nenhuma.
    """

    hits: tuple[SearchHit, ...]
    dense_s: float
    docstore_s: float
    discarded: int = 0


class Answer(NamedTuple):
    """Resposta gerada, com os trechos que a sustentam.

    `refused` é campo essencial do contrato: o backend compara a resposta com a
    própria frase de escape e informa. Sem ele o frontend teria que comparar
    strings e ficaria acoplado ao texto exato de cada projeto.
    """

    text: str
    refused: bool
    hits: tuple[SearchHit, ...]
    timings: dict[str, float]


class ResetReport(NamedTuple):
    """O que o reset apagou de cada armazém.

    Existe para que o comando diga o que fez em vez de terminar em silêncio: um
    reset que não encontrou nada e um reset que apagou a ingestão inteira são
    indistinguíveis sem estes dois números.

    O cache de partição não aparece aqui porque ele NÃO é tocado (ADR-005):
    zerar armazém não pode custar os minutos de `hi_res` de novo.
    """

    indexed_removed: int
    originals_removed: int
