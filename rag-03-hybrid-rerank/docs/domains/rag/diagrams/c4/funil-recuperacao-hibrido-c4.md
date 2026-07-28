# Diagramas C4 - Funil de recuperação híbrido

Fonte: `docs/domains/rag/features/funil-recuperacao-hibrido-fdd.md` (versão 1.0, com a
seção 9.1 de estado da validação), com o HLD do domínio (`docs/domains/rag/hld.md`,
versão 1.0.0) como contexto de apoio e o código de `rag/` como conferência final.

Idioma detectado no FDD: **português brasileiro**. Os quatro diagramas foram escritos no
mesmo idioma, com acentuação correta, mantendo em inglês os termos técnicos e os nomes de
componentes, tecnologias e campos (`Service`, `Repository`, `Protocol`, `Elasticsearch`,
`dense_vector`, `SearchHit`, `timings`).

## Arquivos gerados

**Criados**

- `contexto.puml` - C1, Contexto
- `container.puml` - C2, Containers
- `componente.puml` - C3, Componentes do pacote `rag/`
- `codigo.puml` - C4, Código

**Pulados**: nenhum. O FDD tem contexto de negócio (seção 1), stack e unidades de
implantação (seções 4 e 8), decomposição interna (seções 1, 4 e 11) e assinaturas de
código (seção 5.4 e modelo de dados), então os quatro níveis têm base documental.

Para renderizar, use qualquer ferramenta compatível com PlantUML.

## Convenções adotadas

Os nomes de arquivo, o `include` remoto fixado em `C4-PlantUML v2.10.0` e o formato das
notas seguem os três diagramas C4 do Projeto 2
(`../rag-02-conversacional-citacoes/docs/domains/rag/diagrams/c4/`), para que os dois
conjuntos sejam comparáveis lado a lado.

Duas diferenças em relação àqueles arquivos, ambas deliberadas:

- `!pragma charset UTF-8` foi acrescentado como segunda linha, e o texto usa acentuação
  correta. Os diagramas do Projeto 2 são escritos sem acento; aqui a acentuação foi
  conferida no render.
- Existe um quarto diagrama, de nível de código, que o Projeto 2 não tem. Ele foi gerado
  porque a seção 5.4 do FDD traz assinaturas explícitas de `Protocol` e de classe, e o
  modelo de dados declara os campos novos de `SearchHit`, `Provenance` e `RetrievalResult`.

## O que esta revisão corrigiu

Esta é a segunda geração dos quatro arquivos. A primeira foi escrita a partir do FDD
antes de dois refactors, e ficou divergente do código em seis pontos. As correções, e a
decisão que sustenta cada uma:

| Correção | Onde | Fundamento |
| --- | --- | --- |
| O funil mora em `rag/service/retrieval/`, pacote próprio com cinco arquivos | C2, C3, C4 | ADR-008 |
| O `RetrievalService` fala com `DenseSearchService` e `KeywordSearchService`, e não com os repositórios | C3, C4 | ADR-009 |
| `SearchHit` tem `text` (não `excerpt`) e ganhou `doc_id` | C4 | `domain/models.py`, e a seção 5.4 do FDD |
| O `ConsoleReporter` monta uma linha com campos separados; `score` e `distância` podem coexistir nela | C3 | `presenter/console_reporter.py` |
| O reordenador padrão é o multilíngue `mmarco-mMiniLMv2-L12-H384-v1` | C1, C2, C3, C4 | Revisão do ADR-004 |
| `GET /health` responde 200 com `status: degraded` e **nunca** 409; quem devolve 409 é o `POST /ask` | C2, C3, C4 | Critério de aceite 10 e `api/routes/meta.py` |

Uma sétima correção, de conteúdo e não de estrutura: a nota do C1 sobre o que muda para
quem usa prometia "menos recusa em pergunta com nome próprio raro". A seção 9.1 do FDD
registra que **a busca híbrida não demonstrou ganho neste corpus**, então a promessa foi
substituída pelo que a validação de fato entregou: procedência por trecho, custo por
estágio e três configurações comparáveis.

## Resumo da análise

### Elementos explícitos do FDD

- Atores: os quatro entrypoints (`ingest.py`, `ask.py`, `chat.py`, `serve.py`), o
  Elasticsearch em container, a API de embeddings da OpenAI, o cross encoder local e o
  frontend compartilhado do workspace.
- Componentes novos: `KeywordRepository` (`repository/`), e o pacote
  `service/retrieval/` com `DenseSearchService`, `KeywordSearchService`, `FusionService`
  (classe concreta e função pura), `RerankService` (`Protocol` com implementação local) e
  o `RetrievalService` reescrito.
- `RetrievalService` como dono do funil de quatro etapas, com validação de faixas na
  construção, disparo dos dois caminhos, fusão, reordenação e corte em `k`. Fala com
  serviços, nunca com repositórios.
- `DenseSearchService` e `KeywordSearchService` como delegação pura, sem política própria.
- `QueryFacade` inalterada em orquestração; muda apenas o transporte de métrica.
- Parâmetros novos `hibrida`, `rerank`, `candidates` (1 a 50) e `rrf_k` (1 a 1000), com
  `k` mantido como corte final do funil.
- Campos novos de resposta: `timings.dense_s`, `timings.keyword_s`, `timings.fusion_s`,
  `timings.rerank_s`, `hits[].score` e `hits[].provenance`, com `hits[].distance` mantido
  e depreciado.
- `SearchHit` com `doc_id`, chave de deduplicação da fusão e campo interno, não emitido
  no JSON.
- Matriz de erros com `InvalidIndexMappingException` (409), `EmptyIndexException` (409),
  `InvalidParameterException` (422) e `ServiceUnavailableException` (503).
- Semântica de status distinguível (critério 10): `GET /health` responde 200 com
  `status: degraded`, e o `POST /ask` responde 409.
- Índice único com mapping explícito: `dense_vector` e campo de texto analisado em
  português, no mesmo documento.
- `GET /health` consultando `/_cluster/health`, e não a raiz, com vermelho reprovando e
  amarelo passando.
- Harness de medição em `docs/operations/`, com as perguntas e as páginas esperadas em
  arquivo de dados, usando o diagnóstico só léxico.
- Versões: Python 3.12.3, FastAPI 0.140.9, `langchain-elasticsearch` 1.0.0,
  `sentence-transformers` 5.6.1.
- Reordenador `mmarco-mMiniLMv2-L12-H384-v1`, registrado na seção 9.1 do FDD.

### Inferências feitas

- **Assinaturas dos serviços de caminho.** A seção 5.4 declara `DenseSearchService` com
  `search()` e `indexed_count()`, e `KeywordSearchService` com `search()`. Os corpos, que
  são repasse, foram conferidos no código.
- **`CrossEncoderRerankService` como nome da implementação local.** O FDD diz "`Protocol`
  mais implementação local" sem nomear a classe; o nome veio de
  `rag/service/retrieval/rerank_service.py` e aparece no C4 porque é a única
  implementação existente.
- **Métodos do `VectorRepository`.** A seção 5.4 declara apenas `text_field_analyzed()`
  como sexto método. Os outros cinco (`search`, `recreate`, `add`, `count`,
  `vector_size`) foram lidos do `Protocol` no código; a tabela de sequenciamento os
  descreve sem assinatura.
- **`Answer.timings`.** A seção 5.1 lista os campos na resposta HTTP; no domínio eles são
  campos planos de `Answer`, conferido no código, e aparecem agrupados no C4.
- **`JsonPresenter` omitindo campo opcional vazio**. É o comportamento herdado do Projeto 2,
  e é o mecanismo pelo qual o invariante do FDD "estágio não executado tem tempo ausente,
  nunca zero" chega à resposta.
- **Porta da API HTTP**. O FDD e o HLD dizem apenas `127.0.0.1`, sem número. Nenhuma porta
  foi inventada para a aplicação; a `:9200` do Elasticsearch está no HLD.
- **Entrypoints, `pdfs/` e frontend**. Descritos no FDD como inalterados em papel; os
  detalhes de comportamento vieram do próprio FDD (glob não recursivo, corpus de controle,
  descoberta por `GET /capabilities`).

### Exclusões confirmadas

Nenhum destes aparece em qualquer diagrama:

- Qdrant e `langchain-qdrant` como elementos, e a migração de dados do Qdrant para o
  Elasticsearch. O Qdrant aparece apenas como referência textual ao que foi substituído,
  na descrição do Elasticsearch.
- `rank-bm25`.
- Fusão nativa do motor (retriever `rrf` do Elasticsearch).
- Segunda implementação de rerank por API hospedada. Ela aparece apenas como a
  justificativa de o `RerankService` ser `Protocol`, nunca como elemento.
- Execução concorrente dos dois caminhos de busca.
- Logging estruturado, tracing, dashboards e alertas.
- `top_n` como parâmetro público novo. Ele aparece só como argumento do contrato interno
  do `RerankService`, exatamente como na seção 5.4.
- Autenticação, autorização e persistência de conversa no servidor.

### Natureza dos componentes

- **Cross encoder: biblioteca embarcada, in-process.** O FDD diz "cross encoder local,
  carregado uma vez por processo" e "nenhum trecho sai da máquina no estágio de rerank,
  porque ele roda local". Portanto **não** é `System()` no C1 nem `Container()` no C2:
  aparece como característica do processo `rag/` e como o componente `RerankService` no C3.
- **Elasticsearch: sistema independente, out-of-process.** Container Docker acessado por
  HTTP. Modelado como `System_Ext` no C1 e `ContainerDb_Ext` no C2 e no C3.
- **API da OpenAI: sistema externo.** `System_Ext` nos três primeiros níveis.
- **Frontend: container externo.** É o cliente genérico compartilhado do workspace, fora da
  fronteira do sistema, modelado como `Container_Ext`.
- **`service/retrieval/`: fronteira interna, não container.** No C3 é um `Boundary()`
  aninhado dentro do `Container_Boundary` de `rag/`: agrupa componentes do mesmo processo,
  e existe para o diagrama mostrar as quatro etapas do funil como pares.

## Descrição dos diagramas

### C1 - Contexto

- **Público**: interessados no resultado do estudo.
- **Elementos**: Estudante, `rag-03-hybrid-rerank`, API da OpenAI e Elasticsearch.
- **Valor**: mostra o que muda para quem usa (procedência por trecho, custo por estágio,
  três configurações comparáveis) e deixa explícito que o motor de busca passou a atender
  dois caminhos e que o cross encoder, agora multilíngue, não é serviço externo.

### C2 - Containers

- **Público**: arquitetura e liderança técnica.
- **Containers**: `ingest.py`, `ask.py`, `chat.py`, `serve.py`, o pacote `rag/`, o harness
  de `docs/operations/` e `pdfs/`, mais o frontend, o Elasticsearch e a OpenAI do lado de
  fora.
- **Implantação**: on premises, máquina do autor, sem CI e sem orquestrador. O
  Elasticsearch é o único serviço a subir, com healthcheck obrigatório.
- **O que é novo aqui**: o Elasticsearch substitui o Qdrant e recebe **quatro** relações
  distintas do mesmo pacote sobre o **mesmo índice** (gravação com mapping explícito, kNN
  sobre `dense_vector`, BM25 sobre o campo de texto analisado, e a conferência de cluster
  e mapping). O cross encoder aparece dentro do container `rag/`, com nota explicando por
  que ele não é container próprio, por que o modelo foi trocado por medição e por que o
  provedor precisa de escopo de processo. Uma terceira nota fixa a semântica de status:
  `GET /health` reporta, `POST /ask` falha.

### C3 - Componentes

- **Público**: liderança técnica e desenvolvimento.
- **Fronteira nova**: `service/retrieval/`, agrupando `RetrievalService`,
  `DenseSearchService`, `KeywordSearchService`, `FusionService` e `RerankService`.
- **Componentes novos**: `KeywordRepository`, mais os cinco do pacote do funil.
- **Cadeia de chamada do funil**: `RetrievalService` chama os dois serviços de caminho,
  cada relação rotulada pelo tempo que cronometra (`dense_s`, `keyword_s`, `fusion_s`,
  `rerank_s`); os serviços de caminho delegam aos repositórios, e a delegação está
  rotulada como repasse sem política.
- **Pontos de integração**: `VectorRepository` e `KeywordRepository` como os dois únicos
  pontos que falam Elasticsearch; `GenerationService` como fronteira única com o LLM.
- **Notas**: uma por decisão vinculante (pacote do funil, serviço por caminho, matemática
  fora do orquestrador, `Protocol` do rerank, quem mede é quem executa, dois adaptadores
  sem vazamento), mais a semântica de status e o invariante herdado de que nada reordena
  depois da numeração do contexto.

### C4 - Código

- **Público**: desenvolvimento.
- **Pacotes**: `facade/`, `service/retrieval/`, `repository/`, `domain/models.py` e
  `exceptions.py`.
- **Interfaces**: `RetrievalService.retrieve` e `keyword_only`, `DenseSearchService.search`
  e `indexed_count`, `KeywordSearchService.search`, `FusionService.fuse`,
  `RerankService.rerank` com `CrossEncoderRerankService` como implementação, e os seis
  métodos do `VectorRepository`.
- **Estruturas**: `SearchHit` com `text`, `source`, `page`, `doc_id`, `distance`, `score` e
  `provenance`; `Provenance`; `RetrievalResult` com os quatro tempos opcionais; e `Answer`.
- **Algoritmo**: o RRF aparece como invariante em nota (soma de `1 / (rrf_k + posição + 1)`,
  rankings rotulados, deduplicação por `doc_id`, independência de escala), sem pseudocódigo.
- **Detalhes críticos**: faixas validadas na construção e o 422 de `k` maior que
  `candidates`; tempo `None` em vez de zero; `score` e `distance` com sentidos opostos,
  podendo coexistir no mesmo hit mas nunca no mesmo campo; `doc_id` como chave de
  deduplicação e campo interno; `InvalidIndexMappingException` antes do tratador genérico,
  e o 409 pertencendo ao `POST /ask`.

## Rastreabilidade aos ADRs

O projeto tem **nove ADRs** (`docs/adrs/generated/RAG/`), e os quatro diagramas os
referenciam por número nas notas. Os **ADR-003, 004 e 005 têm seções de Revisão**
posteriores à validação, e o conteúdo revisto é o que vale nos diagramas.

| ADR | Onde aparece | Revisto |
| --- | --- | --- |
| 001, Elasticsearch como armazém único | C1, C2, C3 | não |
| 002, RRF em Python | nota de fusão no C3 e no C4 | não |
| 003, `FusionService` próprio e `SearchHit` com procedência | C3, C4 | sim: `SearchHit` ganhou `doc_id`, que o desenho não previa |
| 004, cross encoder local atrás de `Protocol` | C1, C2, C3, C4 | sim: o modelo passou a ser o multilíngue, por medição |
| 005, contrato compartilhado 1.2.0 | C2 | sim: aditivo com um relaxamento declarado, `distance` fora de `required` |
| 006, buscas em sequência | C1, C3 | não |
| 007, `RetrievalService` devolve resultado com métrica | C3 | não |
| 008, o funil mora em `service/retrieval/` | C2, C3, C4 | não |
| 009, um service por caminho de busca | C3, C4 | não |

## Resultado da validação

### Checklist

- [x] Todos os elementos rastreiam ao FDD, ao HLD ou estão registrados como inferência
- [x] Nenhum item excluído do escopo aparece nos diagramas
- [x] Tecnologias e versões conferem com a seção 8 do FDD
- [x] Progressão de detalhe C1 → C2 → C3 → C4
- [x] Biblioteca embarcada tratada corretamente: o cross encoder não é System nem Container
- [x] `!pragma charset UTF-8` presente nos quatro arquivos
- [x] `SHOW_LEGEND()` em C1, C2 e C3, e ausente no C4 de código
- [x] Notas curtas, em tópicos, sem referência a seção de FDD
- [x] Idioma do FDD, com acentuação conferida no render
- [x] Termos técnicos e nomes de componentes mantidos em inglês
- [x] Estrutura de pacotes conferida contra `rag/`, e não apenas contra o documento

### Consistência entre níveis

- O Elasticsearch é o mesmo elemento nos três primeiros níveis, sempre com a mesma
  afirmação: um índice, um documento por trecho, dois caminhos de busca.
- O cross encoder aparece como característica do processo no C1 e no C2, ganha identidade
  de componente no C3 e de `Protocol` mais implementação no C4. O nome do modelo é o mesmo
  nos quatro.
- O pacote `service/retrieval/` aparece como menção na descrição do container `rag/` no
  C2, como fronteira com cinco componentes no C3 e como `package` com seis classes no C4.
- Os quatro tempos aparecem como promessa no C1 ("tempo por estágio"), como campo de
  resposta no C2, como rótulo das relações do funil no C3 e como campos de
  `RetrievalResult` no C4.
- A semântica de status (200 `degraded` na saúde, 409 no `/ask`) é afirmada com o mesmo
  texto no C2, no C3 e na nota de erro do C4.
- A `QueryFacade` chama os mesmos cinco estágios no C3 que o Projeto 2 já mostrava. A
  única diferença é a ausência da cronometragem, registrada em nota.
- Os quatro arquivos foram renderizados com PlantUML 1.2025.4 sem erro de sintaxe, e as
  imagens de conferência foram descartadas.
