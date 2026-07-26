<!-- GERADO por gerar.py a partir de _relatorio.md e mermaid/*.mmd. Não edite este
     arquivo: edite _relatorio.md e rode `python docs/domains/rag/diagrams/gerar.py`. -->

# Relatório de diagramas — domínio `rag`

Estado em 25/07/2026, após o ADR-005 (segregação por responsabilidade).

> **Para ver os diagramas no VS Code:** abra este arquivo e aperte `Ctrl+Shift+V`.
> A extensão `bierner.markdown-mermaid` renderiza Mermaid **apenas** dentro do Markdown
> Preview, ou seja, só em blocos ```mermaid dentro de `.md`. Abrir um `.mmd` solto e
> apertar `Ctrl+Shift+V` não faz nada, e essa é a pegadinha mais comum.
>
> Os `.mmd` em `mermaid/` continuam sendo a fonte de verdade. Este arquivo embute cópias,
> geradas por `gerar.py`.

Os diagramas descrevem três coisas diferentes. **Sequência** mostra a ordem temporal: quem
chama quem, e quando. **Fluxograma** mostra a lógica: as decisões e os desvios.
**C4** mostra a estrutura: que peças existem. Uma refatoração muda o C4 e não muda a
sequência nem o fluxo, e foi exatamente o que aconteceu com o ADR-005.

## Inventário

| Arquivo | Tipo | O que responde | Validado |
| --- | --- | --- | --- |
| `mermaid/sequencia-consulta.mmd` | sequência | Ordem exata de uma pergunta, do argv à resposta | parser Mermaid 11 |
| `mermaid/sequencia-ingestao.mmd` | sequência | Ordem exata de uma indexação | parser Mermaid 11 |
| `mermaid/consulta.mmd` | fluxograma | Decisões e desvios da consulta | parser Mermaid 11 |
| `mermaid/ingestao.mmd` | fluxograma | Decisões e pontos de falha da ingestão | parser Mermaid 11 |
| `mermaid/componentes.mmd` | estrutura | Quem importa quem, extraído do código por AST | parser Mermaid 11 |
| `c4/contexto.puml` | C4 nível 1 | Quem usa o sistema e de que ele depende | PlantUML 1.2026.6, PNG conferido |
| `c4/container.puml` | C4 nível 2 | Que unidades executáveis existem | PlantUML 1.2026.6, PNG conferido |
| `c4/componente.puml` | C4 nível 3 | Os dez módulos de `rag/` e suas relações | PlantUML 1.2026.6, PNG conferido |

---

## 1. A sequência de uma consulta

**Comece por aqui se o objetivo é entender como o RAG funciona.** É o diagrama que mostra
a ordem real das chamadas, incluindo os dois momentos em que se fala com a OpenAI.

```mermaid
---
title: Sequência de uma consulta (python ask.py "pergunta")
---
sequenceDiagram
    autonumber
    actor U as Você
    participant ASK as ask.py<br/>(composition root)
    participant CFG as RagProperties
    participant PRE as HealthChecker
    participant FAC as QueryFacade
    participant RET as RetrievalService
    participant ST as VectorRepository
    participant PR as PromptBuilder
    participant GEN as GenerationService
    participant REP as ConsoleReporter
    participant CH as Chroma<br/>(Docker :8000)
    participant AI as API OpenAI

    U->>ASK: python ask.py "pergunta"

    rect rgba(90, 120, 170, 0.13)
    note over ASK,CH: PRE-VOO - falhar antes de gastar dinheiro
    ASK->>CFG: config.load()
    CFG->>CFG: le .env e valida a chave
    CFG-->>ASK: RagProperties (se existe, e valida)
    ASK->>PRE: check()
    PRE->>CH: GET /api/v2/heartbeat
    CH-->>PRE: 200
    ASK->>FAC: open_index()
    FAC->>RET: require_index()
    RET->>ST: count()
    ST->>CH: get_collection().count()
    CH-->>ST: 617
    ST-->>RET: 617
    RET-->>FAC: 617
    FAC-->>ASK: 617
    ASK->>REP: index_opened("livros", 617, k=4)
    end

    rect rgba(60, 150, 120, 0.13)
    note over ASK,AI: RETRIEVE - a pergunta vira vetor e busca vizinhos
    ASK->>FAC: ask("pergunta")
    FAC->>RET: retrieve("pergunta")
    RET->>ST: search("pergunta", k=4)
    ST->>AI: embed("pergunta")
    AI-->>ST: vetor de 1536 dimensoes
    ST->>CH: similarity_search_with_score
    CH-->>ST: 4 pares (chunk, distancia)
    ST-->>RET: hits
    RET-->>FAC: hits
    note right of CH: devolve os 4 mais proximos SEMPRE,<br/>mesmo que todos sejam ruins.<br/>Nao ha limiar. Nada aqui avalia<br/>se o resultado presta.
    end

    rect rgba(200, 140, 50, 0.13)
    note over ASK,AI: AUGMENT + GENERATE - o unico ponto que pode recusar
    FAC->>PR: build(pergunta, hits)
    PR-->>FAC: prompt com contexto numerado<br/>+ instrucao de escape
    FAC->>GEN: generate(prompt)
    GEN->>AI: chat completion (temperatura 0)
    AI-->>GEN: resposta OU frase de escape
    GEN-->>FAC: texto
    FAC-->>ASK: Answer(text, hits, search_s, generation_s)
    end

    rect rgba(150, 100, 180, 0.13)
    note over ASK,REP: SAIDA - a facade devolveu DADO, o entrypoint apresenta
    ASK->>REP: answer(Answer)
    REP-->>U: stderr: busca 0.31s | geracao 1.12s
    REP-->>U: stdout: a resposta
    REP-->>U: stderr: [1] arquivo p.2 dist 0.875 ...
    end
```

Quatro coisas que este diagrama revela e que não são óbvias lendo o código:

**A OpenAI é chamada duas vezes por pergunta, não uma.** A primeira, no passo do
`embed`, converte a sua pergunta em vetor para poder buscar. A segunda gera a resposta.
Quem paga a primeira é a busca, e ela é barata; a segunda é a cara.

**A conversão da pergunta em vetor acontece dentro de `store`, não em `retrieval`.** O
`embedding_function` foi injetado no adaptador do Chroma, então quem dispara a chamada é a
camada de persistência. É o único ponto do desenho onde a responsabilidade fica menos
óbvia do que os nomes dos módulos sugerem.

**O Chroma devolve 4 chunks sempre.** Não existe um passo entre a busca e o prompt que
descarte resultado ruim. Se a resposta não estiver no corpus, ele devolve os 4 menos
irrelevantes, com distância alta, e segue em frente.

**A única coisa capaz de recusar é o LLM.** A caixa da decisão está no final, depois da
geração, não depois da busca. Isso é a definição de Naive RAG: nada no caminho avalia a
qualidade da recuperação. O grading do Projeto 5 é justamente inserir essa avaliação
entre a busca e o prompt.

---

## 2. A sequência da ingestão

```mermaid
---
title: Sequência da ingestão (python ingest.py)
---
sequenceDiagram
    autonumber
    actor U as Você
    participant ING as ingest.py<br/>(composition root)
    participant CFG as RagProperties
    participant PRE as HealthChecker
    participant FAC as IngestionFacade
    participant LOAD as DocumentReader
    participant CHK as ChunkingService
    participant ST as VectorRepository
    participant REP as ConsoleReporter
    participant CH as Chroma<br/>(Docker :8000)
    participant AI as API OpenAI

    U->>ING: python ingest.py

    rect rgba(90, 120, 170, 0.13)
    note over ING,CH: PRE-VOO
    ING->>CFG: config.load()
    CFG-->>ING: RagProperties validada
    ING->>PRE: check()
    PRE->>CH: GET /api/v2/heartbeat
    CH-->>PRE: 200
    ING->>REP: service_ok(url)
    ING->>CHK: RecursiveChunkingService(1000, 150)
    note right of CHK: valida overlap < size<br/>ANTES de ler qualquer PDF
    end

    rect rgba(190, 90, 80, 0.13)
    note over ING,CH: RECRIAR - por que nao acrescentar
    ING->>FAC: files()
    FAC-->>ING: [harry-potter.pdf]
    ING->>FAC: ingest()
    FAC->>ST: recreate()
    ST->>CH: count() e delete_collection()
    CH-->>ST: 617 chunks descartados
    ST-->>FAC: 617
    
    note right of ST: acrescentar geraria chunks<br/>duplicados: k=4 devolveria<br/>4 copias do mesmo trecho<br/>sem nenhum aviso
    end

    rect rgba(60, 150, 120, 0.13)
    note over ING,LOAD: LOAD - glob NAO recursivo
    ING->>LOAD: files()
    LOAD-->>ING: [harry-potter.pdf]
    ING->>REP: reading(arquivo)
    ING->>LOAD: config.load()
    LOAD->>LOAD: PyPDFLoader, 1 Document por pagina<br/>metadados source e page
    LOAD->>LOAD: descarta paginas sem texto
    LOAD-->>FAC: 274 paginas, 0 descartadas
    note right of LOAD: pdfs/fora-do-corpus/ nunca entra:<br/>o glob e pdfs/*.pdf, sem recursao.<br/>E o corpus de controle (ADR-004)
    end

    rect rgba(200, 140, 50, 0.13)
    note over ING,AI: SPLIT + EMBED + STORE - o unico estagio pago
    FAC->>CHK: split(paginas)
    CHK-->>FAC: 617 chunks
    FAC->>ST: add(chunks)
    ST->>AI: embed(chunks) em lote
    AI-->>ST: 617 vetores de 1536d
    ST->>CH: add_documents
    CH-->>ST: gravado no volume chroma_data
    end

    FAC-->>ING: IngestionReport(274, 617, ...)
    ING->>REP: ingestion(report)
    REP-->>U: stdout: 274 paginas -> 617 chunks
```

O ponto que mais surpreende aqui é a ordem: **a coleção é apagada antes dos PDFs serem
lidos.** Parece arriscado, e é deliberado. Se a leitura falhar, você fica sem índice, o
que é ruidoso e óbvio. A alternativa (ler primeiro, apagar depois) deixaria o índice
antigo intacto durante uma falha parcial, e você poderia consultar dados velhos achando
que reindexou.

---

## 3. O fluxo da consulta, com as decisões

A sequência mostra a ordem; o fluxograma mostra os desvios.

```mermaid
---
title: Fluxo de consulta (ask.py)
---
flowchart TD
    START([python ask.py]) --> V1{"chave e Chroma ok?"}
    V1 -->|não| E1["exit 1<br/>mensagem acionavel"]
    V1 -->|sim| V2{"colecao existe<br/>e tem chunks?"}
    V2 -->|não| E2["exit 1<br/>rode ingest.py primeiro"]

    V2 -->|sim| MODE{"veio pergunta<br/>por argv?"}
    MODE -->|sim| Q[pergunta unica]
    MODE -->|não| REPL["REPL: reaproveita<br/>cliente e colecao"]
    REPL --> READ["le a entrada"]
    READ --> V3{"o que veio?"}
    V3 -->|"linha vazia"| READ
    V3 -->|"comando de saida,<br/>EOF ou Ctrl+C"| BYE([exit 0])
    V3 -->|"uma pergunta"| Q

    Q --> EMBQ["embeda a pergunta"]
    EMBQ --> SEARCH["similarity_search_with_score<br/>k=4"]
    DB[("colecao 'livros'")] -.-> SEARCH
    SEARCH --> T1["mede latencia de busca"]

    T1 --> PROMPT["monta o prompt:<br/>instrucao de fundamentacao<br/>+ frase de escape<br/>+ contexto numerado<br/>+ pergunta"]
    PROMPT --> LLM["gpt-4o-mini<br/>temperatura 0"]
    LLM --> T2["mede latencia de geracao"]

    T2 --> DEC{"o contexto<br/>respondia?"}
    DEC -->|sim| ANS["resposta fundamentada"]
    DEC -->|não| ESC["'Nao encontrei essa informacao<br/>nos documentos.'<br/>literal, verificavel por string"]

    ANS --> OUT1[/"stdout: so a resposta"/]
    ESC --> OUT1
    OUT1 --> OUT2[/"stderr: chunks, source, page,<br/>distancia e latencias por estagio"/]
    OUT2 --> BACK{"modo REPL?"}
    BACK -->|sim| READ
    BACK -->|não| OK([exit 0])

    classDef erro fill:#4a1a1a,stroke:#d94a4a,color:#fff
    classDef ok fill:#1a4a2e,stroke:#4ad98a,color:#fff
    classDef escape fill:#3a3a1a,stroke:#d9c94a,color:#fff
    class E1,E2 erro
    class OK,BYE ok
    class ESC escape
```

---

## 4. O fluxo da ingestão, com os pontos de falha

```mermaid
---
title: Fluxo de ingestão (ingest.py)
---
flowchart TD
    START([python ingest.py]) --> V1{"OPENAI_API_KEY<br/>definida?"}
    V1 -->|não| E1["exit 1<br/>copie .env.example para .env"]
    V1 -->|sim| V2{"Chroma responde<br/>/api/v2/heartbeat?"}
    V2 -->|não| E2["exit 1<br/>docker compose up -d chroma"]
    V2 -->|sim| V3{"overlap menor<br/>que size?"}
    V3 -->|não| E3["exit 1<br/>parametros invalidos"]

    V3 -->|sim| G["glob pdfs/*.pdf<br/>NAO recursivo"]
    G -.->|fora-do-corpus/ nunca entra<br/>ADR-004| CTRL[["pdfs/fora-do-corpus/<br/>corpus de controle"]]
    G --> V4{"achou algum PDF?"}
    V4 -->|não| E4["exit 1<br/>pdfs/ vazio"]

    V4 -->|sim| L["PyPDFLoader<br/>1 Document por pagina<br/>metadados: source, page"]
    L --> F{"pagina tem texto?"}
    F -->|não| SKIP["avisa e descarta<br/>hipotese: PDF escaneado"]
    SKIP --> V5
    F -->|sim| V5{"sobrou alguma<br/>pagina com texto?"}
    V5 -->|não| E5["exit 1<br/>nenhum texto extraido"]

    V5 -->|sim| C{"colecao ja existe?"}
    C -->|sim| DEL["reporta N chunks antigos<br/>e apaga a colecao"]
    C -->|não| SPLIT
    DEL --> SPLIT["RecursiveCharacterTextSplitter<br/>size 1000 / overlap 150"]

    SPLIT --> EMB["OpenAIEmbeddings em lote<br/>text-embedding-3-small - 1536d<br/>max_retries=3"]
    EMB -.->|429 ou 5xx| RETRY["backoff exponencial<br/>do proprio SDK da OpenAI<br/>ate 3 tentativas"]
    RETRY -.-> EMB
    EMB -.->|401| E6["exit 1<br/>o SDK nao retenta 401"]

    EMB --> W[("colecao 'livros'<br/>volume chroma_data")]
    W --> OUT["reporta paginas, chunks<br/>e tempo total"]
    OUT --> OK([exit 0])

    classDef erro fill:#4a1a1a,stroke:#d94a4a,color:#fff
    classDef ok fill:#1a4a2e,stroke:#4ad98a,color:#fff
    classDef nota fill:#3a3a1a,stroke:#d9c94a,color:#fff
    class E1,E2,E3,E4,E5,E6 erro
    class OK,OUT ok
    class CTRL,SKIP,RETRY nota
```

Os seis nós vermelhos são todos os jeitos de a ingestão terminar mal, e todos encerram com
código 1 e mensagem que nomeia o comando de correção. Nenhum deles propaga traceback de
biblioteca.

---

## 5. A estrutura: os dez módulos

Este grafo não foi desenhado de memória. Foi extraído do código percorrendo a AST de cada
arquivo e coletando os `import` internos. Se ele diverge do código, o código mudou.

```mermaid
---
title: Camadas e dependências (ADR-005 + 006 + 007)
---
flowchart TD
    subgraph ROOTS["ENTRYPOINTS — argparse + composition root"]
        ING["ingest.py"]
        ASK["ask.py"]
    end

    subgraph FAC["facade/ — casos de uso, sem terminal"]
        IFAC["IngestionFacade<br/><i>ingest() → IngestionReport</i>"]
        QFAC["QueryFacade<br/><i>ask() → Answer</i>"]
    end

    subgraph SVC["service/ — regra de uma responsabilidade"]
        HEALTH["HealthChecker"]
        CHUNK["ChunkingService"]
        RETR["RetrievalService"]
        PROMPT["PromptBuilder"]
        GEN["GenerationService"]
    end

    subgraph REPO["repository/ — fontes externas"]
        READER["DocumentReader"]
        VEC["VectorRepository"]
    end

    subgraph PRES["presenter/ — unico que escreve"]
        REP["ConsoleReporter"]
    end

    subgraph BASE["base — folhas do grafo"]
        MODELS["domain.models<br/><i>SearchHit, Answer,<br/>IngestionReport</i>"]
        CFG["config<br/><i>RagProperties</i>"]
        EXC["exceptions"]
    end

    ING --> IFAC & HEALTH & REP & CFG & EXC
    ASK --> QFAC & HEALTH & REP & CFG & EXC

    IFAC --> READER & CHUNK & VEC & MODELS
    QFAC --> RETR & PROMPT & GEN & MODELS

    RETR --> VEC & MODELS & EXC
    PROMPT --> MODELS
    VEC --> MODELS
    REP --> MODELS
    READER --> EXC
    CHUNK --> EXC
    HEALTH --> CFG & EXC
    CFG --> EXC

    classDef root fill:#1a3a52,stroke:#4a90d9,color:#fff
    classDef fac fill:#2a3a5a,stroke:#6a90d9,color:#fff
    classDef svc fill:#1a4a2e,stroke:#4ad98a,color:#fff
    classDef repo fill:#3a2a4a,stroke:#a97ad9,color:#fff
    classDef pres fill:#4a2a3a,stroke:#d97aa9,color:#fff
    classDef base fill:#4a3a1a,stroke:#d9a94a,color:#fff
    class ING,ASK root
    class IFAC,QFAC fac
    class HEALTH,CHUNK,RETR,PROMPT,GEN svc
    class READER,VEC repo
    class REP pres
    class MODELS,CFG,EXC base
```

Três propriedades que o grafo prova:

**É acíclico.** `erros` e `store` são folhas; nada aponta de volta para os entrypoints.
Dependência circular é o defeito mais comum em decomposições feitas às pressas, e não há
nenhuma aqui.

**As duas arestas tracejadas são o único ponto discutível.** `prompting` e `reporting`
importam `store` apenas pelo tipo `Achado`, o par (chunk, distância). Não é dependência de
camada, é dependência de forma de dado. A alternativa seria um décimo primeiro módulo só
para tipos. Ficou como está porque o módulo que define o `Protocol` também define o tipo
que ele devolve.

**Cada módulo tem uma razão única para mudar:**

| Módulo | Muda quando |
| --- | --- |
| `erros` | surge uma nova classe de falha |
| `config` | muda um parâmetro ou a fonte de configuração |
| `preflight` | muda o que precisa estar no ar |
| `loading` | é preciso suportar outro formato de arquivo |
| `chunking` | muda a estratégia de divisão |
| `store` | troca o armazém vetorial |
| `retrieval` | muda `k`, ordenação ou filtro |
| `prompting` | muda a instrução ou o formato do contexto |
| `generation` | troca de provedor ou de modelo |
| `reporting` | muda o formato ou o destino do diagnóstico |

---

## 6. C4

Renderizados e conferidos. Os PNG estão versionados ao lado dos `.puml` para poderem ser
vistos sem instalar nada.

| Nível | Fonte | Render |
| --- | --- | --- |
| 1 — Contexto | [`c4/contexto.puml`](c4/contexto.puml) | [`c4/contexto.png`](c4/contexto.png) |
| 2 — Container | [`c4/container.puml`](c4/container.puml) | [`c4/container.png`](c4/container.png) |
| 3 — Componente | [`c4/componente.puml`](c4/componente.puml) | [`c4/componente.png`](c4/componente.png) |

![C4 nível 1 - Contexto](c4/contexto.png)

![C4 nível 2 - Container](c4/container.png)

![C4 nível 3 - Componente](c4/componente.png)

---

## Duas invariantes desenhadas de propósito

**`pdfs/fora-do-corpus/` aparece nos diagramas como ausente.** No `ingestao.mmd` é um nó
alcançado por aresta tracejada com a nota "nunca entra"; no `container.puml` é um
container com a relação "ausente por construção". Desenhar algo que não acontece parece
estranho, e é deliberado: essa ausência é o mecanismo do teste negativo de grounding
(ADR-004), e é frágil. Quem trocar o glob por recursivo destrói o teste em silêncio. O
diagrama existe para que a quebra fique visível numa revisão.

**A retentativa é do SDK, não nossa.** O `ingestao.mmd` mostra o laço de backoff
etiquetado como "do próprio SDK da OpenAI". Uma versão anterior deste diagrama sugeria um
laço implementado à mão, o que teria levado alguém a procurar no código um `for` de
retentativa que não existe.

---

## Como regenerar

```bash
# Este relatório, a partir dos .mmd
python docs/domains/rag/diagrams/gerar.py

# C4 (precisa de Java; baixe o jar uma vez de github.com/plantuml/plantuml/releases)
java -jar plantuml.jar -tpng -o . docs/domains/rag/diagrams/c4/*.puml
```

O `mermaid-cli` **não funciona neste ambiente**: depende de um Chromium headless via
Puppeteer que não inicia aqui, e falha com código 1 sem mensagem. A validação de sintaxe
foi feita pelo parser do Mermaid 11 diretamente, sem navegador.

---

## O que estes diagramas deliberadamente não mostram

Escalabilidade, disponibilidade, autenticação e tracing distribuído. Não por omissão: o
sistema tem um usuário, roda local e não expõe rede. O HLD registra a ausência como
decisão, e desenhar caixas vazias de "load balancer" seria pior que não desenhar.
