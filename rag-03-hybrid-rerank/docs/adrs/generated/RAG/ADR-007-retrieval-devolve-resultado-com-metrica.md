# ADR-007: `RetrievalService` devolve resultado com métrica, e a facade para de cronometrar o interior do estágio

- **Status:** aceito
- **Data:** 2026-07-28
- **Domínio:** RAG
- **Decisores:** arthu
- **Corrige:** `docs/domains/rag/hld.md` versão 1.0.0, que afirmava que a `QueryFacade` não
  mudaria

## Contexto

A versão 1.0.0 do HLD deste projeto afirmava, em três lugares, que a `QueryFacade` não
mudaria uma linha, e usava isso como evidência de que a estrutura em camadas herdada do
Projeto 1 tinha aguentado a troca do mecanismo de recuperação.

O reconhecimento do código do Projeto 2 mostrou que essa afirmação é incompatível com o
[[ADR-005-contrato-compartilhado-1-2-0]], que exige medição por estágio. Os fatos:

- `QueryFacade.ask()` cronometra ela mesma, com `time.perf_counter()`, e calcula
  `search_s` em volta da chamada a `retrieve()`
  (`rag-02-conversacional-citacoes/rag/facade/query_facade.py:102-103,137`).
- `RetrievalService.retrieve()` devolve `list[SearchHit]` puro
  (`.../rag/service/retrieval_service.py:56-63`). Não existe canal para tempo.
- `Answer` é `NamedTuple` de campos fixos, com os três tempos achatados e **sem campo
  `meta`** (`.../rag/domain/models.py:147-163`).

Com essas três coisas ao mesmo tempo, os tempos internos do funil (busca densa, busca
léxica, fusão, rerank) morrem dentro do serviço e não há onde publicá-los. A afirmação do
HLD foi escrita a partir do desenho, antes de o arquivo ser lido.

## Decisão

**A `QueryFacade` muda, e a afirmação do HLD é substituída por uma mais estreita e
verdadeira: a facade não muda em orquestração.**

*Precisão acrescentada em 28/07/2026, depois de a regeneração dos diagramas apontar que
o título desta decisão exagerava:* a facade não para de cronometrar. Ela para de
cronometrar **o que não consegue enxergar**.

Concretamente:

- `RetrievalService.retrieve()` passa a devolver um resultado composto, carregando os hits
  finais e os tempos de cada estágio interno do funil, em vez de apenas a lista.
- `Answer` ganha os campos de tempo correspondentes.
- `QueryFacade` **deixa de cronometrar o INTERIOR** do estágio de busca, e repassa o que o
  serviço mediu por dentro. Ela **continua medindo `search_s`**, que é o total da
  recuperação e mantém exatamente o significado que sempre teve. Cronometrar de fora uma
  operação inteira é legítimo; o que não dá é cronometrar de fora as quatro etapas que
  acontecem lá dentro. Continua chamando os mesmos estágios, na mesma ordem, sem saber que a
  recuperação virou funil.
- `JsonPresenter` e `ConsoleReporter` passam a emitir os tempos novos.

A propriedade que o HLD queria demonstrar sobrevive, e fica mais precisa: **a facade não
ganha nenhuma responsabilidade nova de orquestração.** Ela não sabe que existem dois
caminhos, não sabe que há fusão e não sabe que há reordenação. O que ela perde é uma
responsabilidade que não era dela: medir o tempo de um estágio cujo interior ela não
conhece.

## Alternativas consideradas

### Abrir mão da medição por estágio

Rejeitada pelo autor. `search_s` passaria a medir o funil inteiro e nada mudaria na facade,
no `Answer` nem nos apresentadores. O HLD ficaria correto como estava escrito.

Recusada porque mataria o exercício 3 do guia ("rerankear 50 candidatos em vez de 20 melhora
quanto, e custa quantos ms?") e esvaziaria metade da razão de existir do
[[ADR-005-contrato-compartilhado-1-2-0]]. A medição por estágio é o instrumento declarado
do projeto, não um confortinho de diagnóstico: sem ela, a decisão pendente de paralelizar as
buscas ([[ADR-006-buscas-em-sequencia]]) nunca teria como ser reaberta com evidência.

### Canal lateral: o serviço guarda os tempos da última chamada

Rejeitada. Quase nenhuma assinatura mudaria: a facade leria um atributo do serviço depois de
chamar `retrieve()`.

Recusada porque introduz **estado mutável em um serviço**, contrariando o padrão "serviço
sem estado" que o HLD declara e que o Projeto 2 defendeu no ADR-002 dele. Duas requisições
HTTP concorrentes leriam o tempo uma da outra, e o defeito seria intermitente e
indiagnosticável. Trocar uma mudança de assinatura visível por um acoplamento temporal
invisível é o pior negócio possível.

### Publicar os tempos em `Answer.meta`

Não considerada viável: `Answer` é `NamedTuple` de campos fixos e **não tem** campo `meta`.
O `meta` do contrato HTTP é montado pelo `JsonPresenter` a partir de
`unresolved_labels`. Usar esse caminho exigiria alterar `Answer` de qualquer forma, que é
justamente o que esta alternativa tentava evitar.

## Consequências

**Positivas**

- A medição por estágio, que é o instrumento principal do projeto, passa a ser possível.
- O tempo é medido por quem sabe o que aconteceu. Cronometrar de fora um estágio cujo
  interior mudou é medida que envelhece mal.
- O `RetrievalService` continua sem estado: o tempo sai pelo retorno, não por atributo.
- A afirmação do HLD sobre as camadas fica mais forte por ser mais estreita e verificável.

**Negativas**

- O raio da mudança cresce: além da facade, mudam `Answer`, `JsonPresenter` e
  `ConsoleReporter`. São quatro arquivos que a versão 1.0.0 do HLD dava como intocados.
- Um documento canônico precisou ser corrigido logo depois de escrito. O registro fica, e é
  informação: o desenho foi feito antes da leitura do código, e a leitura o corrigiu.

## Referências

- `docs/domains/rag/hld.md`, "Arquitetura geral" e "Componentes e responsabilidades"
- `.compozy/tasks/funil-recuperacao-hibrido/_prd.md`, "Core Features", item 5
- Código de referência: `rag-02-conversacional-citacoes/rag/facade/query_facade.py`,
  `rag/service/retrieval_service.py`, `rag/domain/models.py`
- [[ADR-005-contrato-compartilhado-1-2-0]]
- [[ADR-006-buscas-em-sequencia]]
