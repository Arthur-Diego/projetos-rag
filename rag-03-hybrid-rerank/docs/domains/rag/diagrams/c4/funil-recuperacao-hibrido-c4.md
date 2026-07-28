# Diagramas C4 - Funil de recuperação híbrido

Fonte: `docs/domains/rag/features/funil-recuperacao-hibrido-fdd.md` (versão 1.0), com o
HLD do domínio (`docs/domains/rag/hld.md`, versão 1.0.0) como contexto de apoio.

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

## Resumo da análise

### Elementos explícitos do FDD

- Atores: os quatro entrypoints (`ingest.py`, `ask.py`, `chat.py`, `serve.py`), o
  Elasticsearch em container, a API de embeddings da OpenAI, o cross encoder local e o
  frontend compartilhado do workspace.
- Componentes novos: `KeywordRepository` (`repository/`), `FusionService` (`service/`,
  classe concreta e função pura) e `RerankService` (`service/`, `Protocol` com
  implementação local).
- `RetrievalService` reescrito como dono do funil de quatro etapas, com validação de
  faixas, disparo dos dois caminhos, fusão, reordenação e corte em `k`.
- `QueryFacade` inalterada em orquestração; muda apenas o transporte de métrica.
- Parâmetros novos `hibrida`, `rerank`, `candidates` (1 a 50) e `rrf_k` (1 a 1000), com
  `k` mantido como corte final do funil.
- Campos novos de resposta: `timings.dense_s`, `timings.keyword_s`, `timings.fusion_s`,
  `timings.rerank_s`, `hits[].score` e `hits[].provenance`, com `hits[].distance` mantido
  e depreciado.
- Matriz de erros com `InvalidIndexMappingException` (409), `EmptyIndexException` (409),
  `InvalidParameterException` (422) e `ServiceUnavailableException` (503).
- Índice único com mapping explícito: `dense_vector` e campo de texto analisado em
  português, no mesmo documento.
- `GET /health` consultando `/_cluster/health`, e não a raiz.
- Harness de medição em `docs/operations/`, com as perguntas e as páginas esperadas em
  arquivo de dados, consultando o `KeywordRepository` diretamente para o diagnóstico
  "só BM25".
- Versões: Python 3.12.3, FastAPI 0.140.9, `langchain-elasticsearch` 1.0.0,
  `sentence-transformers` 5.6.1.

### Inferências feitas

- **Campos herdados de `SearchHit`** (`source`, `page`, `excerpt`, `distance`). A seção
  5.4 declara apenas os campos novos; os herdados foram lidos do exemplo de resposta da
  seção 5.1, que traz `source`, `page`, `excerpt` e do texto que mantém `distance`.
- **`recreate()` e `add()` no `VectorRepository`**. A tabela de sequenciamento fala em
  "mapping explícito no `recreate`" e o fluxo de ingestão descreve destruir e gravar. As
  assinaturas não são declaradas, então aparecem sem parâmetros.
- **Método que expõe o mapping**. A etapa 8 do sequenciamento prevê "método novo no
  `Protocol` para expor o mapping", sem nomeá-lo. Ele aparece só como nota, sem assinatura
  inventada.
- **Implementação local do `RerankService`**. O FDD diz "`Protocol` mais implementação
  local" sem nomear a classe. O diagrama de código mostra apenas o `Protocol`, com a
  implementação descrita em nota.
- **`Answer.timings`**. A seção 5.1 lista os campos de `timings` na resposta HTTP e a etapa
  1 do sequenciamento diz "`Answer` com os quatro tempos"; o campo aparece sem detalhar a
  estrutura interna.
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

## Descrição dos diagramas

### C1 - Contexto

- **Público**: interessados no resultado do estudo.
- **Elementos**: Estudante, `rag-03-hybrid-rerank`, API da OpenAI e Elasticsearch.
- **Valor**: mostra o que muda para quem usa (menos recusa em pergunta com nome próprio
  raro, custo por estágio publicado) e deixa explícito que o motor de busca passou a
  atender dois caminhos e que o cross encoder não é serviço externo.

### C2 - Containers

- **Público**: arquitetura e liderança técnica.
- **Containers**: `ingest.py`, `ask.py`, `chat.py`, `serve.py`, o pacote `rag/`, o harness
  de `docs/operations/` e `pdfs/`, mais o frontend, o Elasticsearch e a OpenAI do lado de
  fora.
- **Implantação**: on premises, máquina do autor, sem CI e sem orquestrador. O
  Elasticsearch é o único serviço a subir, com healthcheck obrigatório.
- **O que é novo aqui**: o Elasticsearch substitui o Qdrant e recebe **três** relações de
  busca distintas do mesmo pacote sobre o **mesmo índice** (kNN sobre `dense_vector`, BM25
  sobre o campo de texto analisado, e a conferência de cluster e mapping). O cross encoder
  aparece dentro do container `rag/`, com nota explicando por que ele não é container
  próprio e por que o provedor precisa de escopo de processo.

### C3 - Componentes

- **Público**: liderança técnica e desenvolvimento.
- **Componentes novos**: `KeywordRepository`, `FusionService` e `RerankService`, marcados
  como novos na própria descrição.
- **Componente reescrito**: `RetrievalService`, com as quatro relações do funil rotuladas
  pelo tempo que cada uma cronometra (`dense_s`, `keyword_s`, `fusion_s`, `rerank_s`).
- **Pontos de integração**: `VectorRepository` e `KeywordRepository` como os dois únicos
  pontos que falam Elasticsearch; `GenerationService` como fronteira única com o LLM.
- **Notas**: uma por decisão vinculante (matemática fora do orquestrador, `Protocol` do
  rerank, quem mede é quem executa, dois adaptadores sem vazamento) mais o invariante
  herdado de que nada reordena depois da numeração do contexto.

### C4 - Código

- **Público**: desenvolvimento.
- **Interfaces**: `RetrievalService.retrieve`, `FusionService.fuse`, `RerankService.rerank`,
  `VectorRepository.search` e `KeywordRepository.search`.
- **Estruturas**: `SearchHit` com `score` e `provenance`, `Provenance`, `RetrievalResult`
  com os quatro tempos opcionais, e `Answer`.
- **Algoritmo**: o RRF aparece como invariante em nota (soma de `1 / (rrf_k + posição + 1)`,
  deduplicação por identidade do documento, independência de escala), sem pseudocódigo.
- **Detalhes críticos**: faixas de validação e o 422 de `k` maior que `candidates`; tempo
  ausente em vez de zero; `score` e `distance` com sentidos opostos e campos separados;
  `InvalidIndexMappingException` antes do tratador genérico.

## Resultado da validação

### Checklist

- [x] Todos os elementos rastreiam ao FDD ou estão registrados como inferência
- [x] Nenhum item excluído do escopo aparece nos diagramas
- [x] Tecnologias e versões conferem com a seção 8 do FDD
- [x] Progressão de detalhe C1 → C2 → C3 → C4
- [x] Biblioteca embarcada tratada corretamente: o cross encoder não é System nem Container
- [x] `!pragma charset UTF-8` presente nos quatro arquivos
- [x] `SHOW_LEGEND()` em C1, C2 e C3, e ausente no C4 de código
- [x] Notas curtas, em tópicos, sem referência a seção de FDD
- [x] Idioma do FDD, com acentuação conferida no render
- [x] Termos técnicos e nomes de componentes mantidos em inglês

### Consistência entre níveis

- O Elasticsearch é o mesmo elemento nos três primeiros níveis, sempre com a mesma
  afirmação: um índice, um documento por trecho, dois caminhos de busca.
- O cross encoder aparece como característica do processo no C1 e no C2, e ganha
  identidade de componente só no C3, onde a decomposição interna é o assunto.
- Os quatro tempos aparecem como promessa no C1 ("tempo por estágio"), como campo de
  resposta no C2, como rótulo das relações do funil no C3 e como campos de
  `RetrievalResult` no C4.
- A `QueryFacade` chama os mesmos cinco estágios no C3 que o Projeto 2 já mostrava. A
  única diferença é a ausência da cronometragem, registrada em nota.
- Os arquivos foram renderizados com PlantUML 1.2024.7 sem erro de sintaxe.
