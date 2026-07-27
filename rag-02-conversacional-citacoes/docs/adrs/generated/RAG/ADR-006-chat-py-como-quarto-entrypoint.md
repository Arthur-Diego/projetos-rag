# ADR-006: `chat.py` como quarto entrypoint, preservando `ask.py` de turno único

- **Status:** aceito
- **Data:** 2026-07-27
- **Domínio:** RAG
- **Decisores:** arthu

## Contexto

A estrutura canônica da guideline de arquitetura tem três entrypoints: `ingest.py`,
`ask.py` e `serve.py`. O Projeto 2 precisa de conversa multi-turno no terminal, e um
comando que responde uma pergunta e sai não conversa.

As opções eram acrescentar um entrypoint, transformar o `ask.py` em REPL, ou aposentá-lo.

## Decisão

Quatro entrypoints. `chat.py` é novo; `ask.py` continua sendo o comando de turno único
que termina.

| Entrypoint | Papel |
| --- | --- |
| `ingest.py` | Indexa `pdfs/*.pdf`. Roda uma vez. |
| `ask.py` | Uma pergunta, uma resposta, e sai. Sem histórico. |
| `chat.py` | REPL. Mantém a transcrição no processo e imprime a query reescrita a cada turno. |
| `serve.py` | Publica o app FastAPI. Magro. |

Manter o `ask.py` não é conservadorismo, é requisito. Dois critérios de aceite do PRD
dependem dele:

- **Critério 4** é uma matriz: turnos 1, 2 e 3, dentro e fora do corpus, com e sem
  reescrita. Scriptar isso contra um comando que termina é uma linha de shell por caso;
  contra um REPL, é automação de terminal interativo.
- **Critério 5** compara custo com e sem histórico. Comparar exige que o caso sem
  histórico exista como caminho de primeira classe, e não como o REPL com uma lista vazia.

Há também o motivo de comparação lado a lado: `ask.py` faz no Projeto 2 o que faz no
Projeto 1, e a diferença entre os dois é a coisa que o projeto ensina. Se o nome mudasse
de significado entre projetos vizinhos, a comparação ficaria mais difícil exatamente onde
ela é mais valiosa.

Os quatro compartilham as mesmas facades. `chat.py` não tem lógica de RAG: ele é
composition root mais laço de leitura, e o laço acrescenta o turno à `Conversation` local
depois de cada resposta ([[ADR-002-conversa-fora-do-servidor]]).

## Alternativas consideradas

### Só `chat.py`, aposentando o `ask.py`

Rejeitada. Manteria os três nomes da guideline e reduziria superfície, ao custo dos dois
critérios acima. O turno único vira caso particular do REPL na teoria e some da linha de
comando na prática.

### `ask.py` vira REPL, sem arquivo novo

Rejeitada. Preserva a contagem de arquivos e quebra a comparação: mesmo nome, comportamento
diferente entre projetos vizinhos da mesma trilha.

### `ask.py --chat`

Rejeitada. Uma flag que troca o modo de operação de um comando esconde que são dois
programas. O `parse_args` teria dois ramos e o composition root também.

## Consequências

**Positivas**
- A matriz de recusa do critério 4 fica scriptável em shell.
- A comparação com e sem histórico fica disponível sem flag.
- `ask.py` do Projeto 1 e do Projeto 2 continuam comparáveis linha a linha.

**Negativas**
- Um entrypoint a mais que a estrutura canônica, e portanto uma divergência a explicar. É
  menor que a do [[ADR-003-conversa-como-objeto-de-valor]]: acrescenta sem contrariar.
- Dois composition roots com montagem parecida, `ask.py` e `chat.py`. A tentação de
  extrair um `build_query_facade()` compartilhado vai aparecer. Se aparecer, que seja
  função no módulo do projeto e não uma camada nova, sob risco de reintroduzir a
  indireção que o ADR-007 do Projeto 1 alertou.

## Referências

- `../docs/guidelines/arquitetura-em-camadas.md`, seções 1 e 2.6
- `docs/prd.md`, critérios de aceite 4 e 5
- `docs/domains/rag/hld.md`, "Componentes e responsabilidades"
- [[ADR-002-conversa-fora-do-servidor]]
