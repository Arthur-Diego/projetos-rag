# Diagramas C4 - Pipeline multimodal de ponta a ponta

Fonte: `docs/domains/rag/features/pipeline-multimodal-fdd.md` (versão 1.0), com o HLD do
domínio (`docs/domains/rag/hld.md`, versão 1.0) como contexto de apoio. A primeira
geração foi feita antes do código; em **2026-08-02**, com o pipeline implementado, esta
geração foi **conferida contra o código real de `rag/`** (como o precedente do rag-03
fez na segunda geração) e o nível C3 foi ajustado para refletir o que existe. Tudo
rastreia ao FDD, ao HLD, aos seis ADRs de `docs/adrs/generated/RAG/` e, agora, a `rag/`.

Idioma detectado no FDD: **português brasileiro**. Os três diagramas foram escritos no
mesmo idioma, com acentuação correta, mantendo em inglês os termos técnicos e os nomes de
componentes, tecnologias e campos (`Service`, `Repository`, `Protocol`, `Facade`,
`LocalFileStore`, `doc_id`, `kind`, `content_html`, `elements`).

## Diagramas gerados

**Criados** (embutidos neste arquivo, em blocos PlantUML)

- C1, Contexto
- C2, Containers
- C3, Componentes do pacote `rag/`

**Pulados**: o nível C4, de código. O precedente do rag-03 só o gerou porque a seção 5.4
daquele FDD trazia assinaturas explícitas de `Protocol` e de classe; o FDD desta feature
declara contratos HTTP (seção 5) e componentes prováveis (seção 11), mas não assinaturas
de código, então o nível de código não tem base documental antes da implementação.

Para renderizar, use qualquer ferramenta compatível com PlantUML.

## Convenções adotadas

O `include` remoto fixado em `C4-PlantUML v2.10.0`, o `!pragma charset UTF-8` como
segunda linha, o formato das notas e o `SHOW_LEGEND()` seguem os diagramas C4 do
Projeto 3 (`../rag-03-hybrid-rerank/docs/domains/rag/diagrams/c4/`), para que os dois
conjuntos sejam comparáveis lado a lado.

Três diferenças em relação àqueles arquivos, todas deliberadas:

- Os diagramas vivem num único markdown, em blocos ```plantuml```, em vez de arquivos
  `.puml` separados. É o formato pedido para esta geração.
- O frontend genérico aparece já no C1. No rag-03 ele só entrava no C2; aqui ele é ator
  de primeira ordem da feature (a renderização da tabela é critério de aceite) e o FDD o
  declara na mesma entrega.
- A API da OpenAI aparece também no C3. No rag-03 só o `GenerationService` falava com o
  LLM; aqui são três componentes (`TableSummaryService`, `ImageDescriptionService`,
  `GenerationService`), e desenhar o sistema externo torna essa tripla fronteira visível.

## Resumo da análise

### Elementos explícitos do FDD

- Atores: autor-consulente (frontend genérico) e autor-operador (CLI), colapsados na
  mesma pessoa; entrypoints `ingest.py`, `ask.py`, `serve.py` e script CLI de reset.
- Sistemas externos: API da OpenAI (`gpt-4o-mini` texto e visão,
  `text-embedding-3-small`) e Chroma em container (`chromadb/chroma:1.5.9`, porta 8002,
  healthcheck, volume próprio).
- API FastAPI 0.141.1 em `127.0.0.1:8080`, contrato compartilhado 1.3.0 aditivo
  (`SearchHit.kind`, `SearchHit.content_html`, `elements` no `IngestionReport`).
- Armazéns e caches locais: docstore `LocalFileStore` em `data/docstore/` (originais,
  fonte de verdade), cache de partição em `data/partition/` (fronteira entre estágio
  local e estágio pago), figuras extraídas em `data/figures/`.
- Componentes novos: `PartitionService` (partição `hi_res` com cache e roteamento por
  categoria), `TableSummaryService` (resumo em lote, `max_concurrency=5`),
  `ImageDescriptionService` atrás de `Protocol` (visão, base64 em `image_url`),
  `DocstoreRepository`.
- Componentes adaptados ou herdados: `VectorRepository`, `RetrievalService` (resolve
  originais por `doc_id` e descarta hit órfão com warning), `PromptBuilder`
  (`format_context` com originais íntegros, HTML inteiro para tabela),
  `GenerationService` (recusa), `HealthChecker` (dessincronia entre armazéns),
  `IngestionFacade`, `QueryFacade`, presenters (`JsonPresenter`, `ConsoleReporter`).
- Invariantes: original no docstore antes da representação no índice; conteúdo de hit
  `kind=tabela` enviado ao LLM vem do docstore, nunca do índice; `doc_id` determinístico
  por hash; campo opcional ausente é omitido do JSON, nunca `null`; `content_html`
  apenas com `kind=tabela`; nenhuma chamada paga antes de índice acessível.
- Matriz de erros: 422 na borda, 409 de índice vazio no `POST /ask` antes de custo,
  503 para Chroma ou OpenAI fora do ar, 500 para configuração ausente; `/health`
  responde 200 com `status=degraded` na dessincronia.
- Corpus: `pdfs/*.pdf` com glob não recursivo; `pdfs/fora-do-corpus/` como controle
  negativo de grounding, jamais indexado.
- Harness de medição e script de inspeção pós-partição em `docs/operations/`.
- Versões: Python 3.12.3, unstructured[pdf] 0.24.1, langchain 1.3.14,
  langchain-classic 1.0.8, langchain-chroma 1.1.0, fastapi 0.141.1, chroma 1.5.9.

### Inferências feitas

- **Nomes de arquivo dos componentes.** A seção 11 do FDD lista os caminhos prováveis
  (`rag/service/partition_service.py`, `rag/facade/ingestion_facade.py` etc.); os
  diagramas usam os nomes de classe correspondentes, no padrão dos projetos anteriores.
- **`rag/api/` como componente único.** O FDD cita rotas, validação na borda e
  `/capabilities` sem decompor o pacote; o C3 o representa como um componente, como o
  precedente do rag-03 fez.
- **`config.py` e `exceptions.py` na raiz do pacote.** Vêm da arquitetura em camadas do
  HLD e do precedente; o FDD só os implica (matriz de erros, faixas de `k`).
- **Quem lê `data/figures/`.** O FDD diz que a imagem vira base64 em mensagem
  `image_url`; a leitura do arquivo foi atribuída ao `ImageDescriptionService`, que é
  quem monta essa mensagem.
- **Roteamento por categoria dentro do `PartitionService`.** Era a inferência da
  primeira geração (o HLD atribuía a ele a classificação). **Superada pelo código**: a
  implementação separou o roteamento em `ElementRoutingService`, com o `chunk_by_title`
  (~1000 caracteres) como responsabilidade dele. A conferência de 2026-08-02 atualizou o
  C3 de acordo.

### Exclusões confirmadas

Nenhum destes aparece em qualquer diagrama:

- Rota de mídia para servir a imagem ao frontend (ADR-004 do projeto; v2). A imagem
  participa apenas como descrição textual.
- Conversa com histórico e reescrita de pergunta; `chat.py` não existe neste projeto.
- Streaming de resposta; `stream` fora de `features`.
- Segunda implementação local do descritor de imagens. Ela aparece apenas como a
  justificativa de o `ImageDescriptionService` ser `Protocol`, nunca como elemento.
- Multi-representação por original e ingestão assíncrona (pendências declaradas).
- Sanitização do corpus contra injeção na ingestão (risco aceito no HLD).
- Caminho híbrido e rerank: `provenance` fica ausente, só há busca densa.

### Natureza dos componentes

- **Chroma: sistema independente, out-of-process.** Container Docker acessado por HTTP
  na porta 8002. Modelado como `ContainerDb_Ext` no C2 e no C3; no C1 os dois armazéns
  são característica interna do sistema, resumida em nota.
- **Docstore, cache de partição e figuras: armazéns do próprio sistema.** Diretórios no
  filesystem local (`data/`), dentro da fronteira. Modelados como `ContainerDb` no C2 e
  no C3, nunca como sistemas externos.
- **API da OpenAI: sistema externo.** `System_Ext` nos três níveis.
- **Frontend: consumidor externo.** `System_Ext` no C1 e `Container_Ext` no C2, fora da
  fronteira do sistema, como no precedente.
- **Modelos locais do `hi_res` (YOLOX, Table Transformer, Tesseract): biblioteca
  embarcada, in-process.** Rodam dentro do processo, em CPU, sem custo de API. Não são
  `System()` nem `Container()`: aparecem como característica do `PartitionService`.

## Descrição dos diagramas

### C1 - Contexto

- **Público**: interessados no resultado do estudo.
- **Elementos**: Autor, `rag-04-multimodal-docs`, frontend genérico e API da OpenAI.
- **Valor**: mostra o que muda para quem usa (pergunta de célula de tabela vira
  respondível, tabela chega renderizada, imagem participa como descrição) e fixa que o
  enriquecimento pago acontece na ingestão, uma vez, e não a cada consulta.

```plantuml
@startuml contexto
!pragma charset UTF-8
!include https://raw.githubusercontent.com/plantuml-stdlib/C4-PlantUML/v2.10.0/C4_Context.puml

LAYOUT_LEFT_RIGHT()

title C1 • Contexto - Pipeline multimodal de ponta a ponta (rag-04-multimodal-docs)

Person(autor, "Autor", "Único usuário, e um por vez. Consulente pelo frontend genérico e operador pela linha de comando (ingestão, reset, inspeção). Loopback, sem concorrência.")

System(rag, "rag-04-multimodal-docs", "RAG que particiona PDFs complexos em texto, tabela e imagem (unstructured hi_res), indexa a representação que busca bem e entrega ao LLM o original que responde bem, resolvido por doc_id.")

System_Ext(frontend, "Frontend genérico", "Cliente compartilhado da trilha, consumidor do contrato 1.3.0. Renderiza content_html como tabela real após sanitização, com selo de kind e contagens elements no relatório de ingestão.")

System_Ext(openai, "API da OpenAI", "gpt-4o-mini em texto para resumos de tabela e geração, em visão para descrição de imagens; text-embedding-3-small para embeddings. Única credencial do projeto.")

Rel(autor, rag, "Ingere o corpus, pergunta, inspeciona as tabelas detectadas e reseta os armazéns", "CLI e HTTP")
Rel(autor, frontend, "Pergunta e confere a tabela renderizada na fonte", "navegador")
Rel(frontend, rag, "POST /ask, POST /ingest, GET /health, GET /capabilities", "HTTP/JSON, contrato 1.3.0")
Rel(rag, openai, "Resume tabelas, descreve imagens, embeda e gera", "HTTPS")
Rel_Back(autor, rag, "Resposta com kind por hit, tabela em HTML íntegro e recusa quando o contexto não sustenta", "CLI e HTTP")

note right of rag
  Dois armazéns ligados por doc_id
  • Representação buscável no índice vetorial
  • Original íntegro no docstore local, fonte de verdade
  • Enriquecimento pago só do que embeda mal
  • A composição interna é detalhe do C2
end note

note right of autor
  O que muda para quem usa
  • Pergunta de célula de tabela vira respondível
  • A tabela chega como HTML, não sopa de números
  • Imagem participa como descrição textual
  • Reingestão do corpus inalterado custa zero
end note

note right of openai
  Custo concentrado na ingestão
  • Resumo e descrição pagos uma vez por unidade nova
  • Idempotência por doc_id: não repaga o que não mudou
  • Na consulta: um embedding e uma geração
end note

SHOW_LEGEND()
@enduml
```

### C2 - Containers

- **Público**: arquitetura e liderança técnica.
- **Containers**: `ingest.py`, `ask.py`, `serve.py` (FastAPI em `127.0.0.1:8080`), o
  script de reset, o pacote `rag/`, o harness de `docs/operations/`, `pdfs/`,
  `data/docstore/`, `data/partition/` e `data/figures/`, mais o frontend, o Chroma
  (porta 8002) e a OpenAI do lado de fora.
- **Implantação**: on premises, máquina do autor (WSL2), sem CI e sem orquestrador. O
  Chroma é o único serviço a subir, com healthcheck obrigatório.
- **O que é novo aqui**: os dois armazéns sincronizados por `doc_id` com ordem de
  gravação fixa (original primeiro), o cache de partição como fronteira entre o estágio
  local e o estágio pago, e as figuras extraídas em disco. Notas fixam as três decisões
  e a semântica de status.

```plantuml
@startuml container
!pragma charset UTF-8
!include https://raw.githubusercontent.com/plantuml-stdlib/C4-PlantUML/v2.10.0/C4_Container.puml

LAYOUT_TOP_DOWN()

title C2 • Containers - Pipeline multimodal de ponta a ponta (rag-04-multimodal-docs)

Person(autor, "Autor", "Único usuário")

System_Boundary(sistema, "rag-04-multimodal-docs") {
  Container(ingest, "ingest.py", "Python 3.12.3", "Entrypoint de ingestão. Lê pdfs/*.pdf, glob NÃO recursivo: pdfs/fora-do-corpus/ fica de fora de propósito. Valida o caminho antes de qualquer custo.")
  Container(ask, "ask.py", "Python 3.12.3", "Turno único, sem histórico (decisão da sessão de PRD). Mantém a medição scriptável.")
  Container(serve, "serve.py", "FastAPI 0.141.1 e uvicorn", "API HTTP em 127.0.0.1:8080. Implementa o contrato compartilhado 1.3.0, aditivo: kind, content_html e elements entram; nada obrigatório muda.")
  Container(reset, "script de reset", "Python 3.12.3, CLI", "Zera a coleção do Chroma e data/docstore/ numa operação só, para nunca deixar metade viva. Preserva data/partition/ por padrão. Idempotente.")
  Container(pacote, "rag/", "Pacote Python 3.12.3 em camadas", "api, facade, service, repository, presenter, domain. Os modelos locais do hi_res (YOLOX, Table Transformer, Tesseract) rodam DENTRO deste processo, em CPU, sem custo de API.")
  Container(harness, "docs/operations/", "Python 3.12.3", "Script de inspeção pós-partição (contagem e preview das tabelas, sem API) e harness de medição com golden set por classe de alvo e modo --sem-geracao.")
  ContainerDb(corpus, "pdfs/", "Sistema de arquivos", "Corpus fixo: Relatório de Desempenho 3T24 da Petrobras. pdfs/fora-do-corpus/ é o controle negativo, jamais alcançado pelo glob.")
  ContainerDb(docstore, "data/docstore/", "LocalFileStore, sistema de arquivos", "Originais íntegros por doc_id: texto, HTML da tabela, caminho da imagem. FONTE DE VERDADE entre os armazéns; perdê-lo custa a ingestão inteira.")
  ContainerDb(particao, "data/partition/", "Sistema de arquivos", "Cache da partição bruta, por hash do PDF. Com cache válido a partição cai de minutos para segundos. Cache corrompido é descartado e refeito, com log.")
  ContainerDb(figuras, "data/figures/", "Sistema de arquivos", "Imagens extraídas pelo hi_res. Nomes derivados do doc_id, nunca de conteúdo do PDF. Fora do git.")
}

Container_Ext(frontend, "frontend/", "React e Vite", "Cliente genérico do contrato, compartilhado pelo workspace. Sanitiza content_html antes do DOM; campo ausente degrada para o comportamento atual (compatível com os projetos 1 a 3).")

ContainerDb_Ext(chroma, "Chroma", "Container Docker chromadb/chroma:1.5.9, porta 8002, healthcheck, volume próprio", "Representações embedadas (texto direto, resumo de tabela, descrição de imagem) com doc_id, kind, page e source no metadado. Índice DERIVADO, reconstruível a partir do docstore.")

System_Ext(openai, "API da OpenAI", "Resumos, descrições em visão, embeddings e geração")

Rel(autor, ingest, "Ingere", "shell")
Rel(autor, ask, "Pergunta e sai", "shell")
Rel(autor, reset, "Zera os dois armazéns", "shell")
Rel(autor, harness, "Inspeciona tabelas e mede por classe de alvo", "shell")
Rel(autor, frontend, "Pergunta e confere a tabela renderizada", "navegador")

Rel(frontend, serve, "POST /ask e POST /ingest com options", "HTTP/JSON")
Rel(serve, frontend, "Answer com kind, excerpt e content_html; IngestionReport com elements", "HTTP/JSON")

Rel(ingest, pacote, "IngestionFacade")
Rel(ask, pacote, "QueryFacade")
Rel(serve, pacote, "rag.api sobre as mesmas facades")
Rel(harness, pacote, "Roda a consulta nas medições; a inspeção lê só o cache")

Rel(ingest, corpus, "Lê", "glob pdfs/*.pdf")
Rel(pacote, particao, "Lê e grava o cache da partição, por hash do PDF", "filesystem")
Rel(pacote, figuras, "Grava as imagens extraídas; lê para o base64 da descrição", "filesystem")
Rel(pacote, docstore, "Grava o original PRIMEIRO; resolve originais por doc_id na consulta", "LocalFileStore")
Rel(pacote, chroma, "Indexa as representações DEPOIS do original; busca densa top-k", "HTTP :8002")
Rel(pacote, openai, "Resumos e descrições (max_concurrency=5), embeddings e geração", "HTTPS")
Rel(reset, docstore, "Zera", "filesystem")
Rel(reset, chroma, "Zera a coleção", "HTTP :8002")

note as ADR001
  **ADR-001: dois armazéns, uma chave, uma ordem.**
  Representação no Chroma, original no docstore, ligados
  por doc_id. O original é gravado ANTES da representação:
  um hit no índice sempre encontra o original.

  • Docstore é a fonte de verdade; o Chroma é derivado
  • Perder o Chroma custa minutos; perder o docstore, a ingestão
  • Hit com doc_id órfão é descartado com warning, nunca 500
end note

note as ADR005
  **ADR-005: o cache de partição é a fronteira local/pago.**
  hi_res custa minutos de CPU; o cache faz a segunda
  ingestão cair para segundos. O cache economiza tempo;
  a idempotência por doc_id economiza dinheiro (ADR-003).

  • Reingestão inalterada: novos=0, zero chamada paga
  • Reset preserva data/partition/ por padrão
  • Cache corrompido: descarta, refaz, regrava, loga
end note

note as SAUDE
  **Saúde REPORTA estado; quem falha é quem trabalha.**
  GET /health responde 200 com status degraded quando há
  dessincronia entre índice e docstore, e nunca 409.

  • O 409 é do POST /ask com índice vazio, antes de custo
  • Chroma ou OpenAI fora do ar é 503
  • Falha no meio do enriquecimento: 503, e a reexecução retoma
end note

ADR001 .. docstore
ADR005 .. particao
SAUDE .. serve

SHOW_LEGEND()
@enduml
```

### C3 - Componentes

- **Público**: liderança técnica e desenvolvimento.
- **Camadas**: `api/`, `facade/`, `service/`, `repository/`, `presenter/`, `domain/`,
  no grafo estritamente descendente da guideline.
- **Componentes novos** (conferidos contra `rag/` em 2026-08-02): `PartitionService`
  sobre o par `UnstructuredPartitioner`/`FilePartitionCache` (repository, atrás dos
  `Protocol` `Partitioner`/`PartitionCache`), `ElementRoutingService`,
  `EnrichmentService`, `IndexingService`, `TableSummaryService`,
  `ImageDescriptionService` (atrás de `Protocol`), `DocstoreRepository`,
  `PdfCorpusReader` (atrás do `Protocol` `CorpusReader`), `ResetFacade` e a porta
  `IngestionLog` (o `ConsoleReporter` é o adaptador).
- **Cadeia da ingestão**: `IngestionFacade` orquestra seleção, partição, roteamento,
  idempotência (`known` nos dois armazéns, com retomada de falha parcial),
  enriquecimento e indexação dupla, sem lógica própria; a ordem que garante a
  invariante (docstore primeiro, Chroma depois) vive no `IndexingService`.
- **Cadeia da consulta**: `QueryFacade` chama `RetrievalService` (busca densa, resolução
  dos originais por `doc_id`), `PromptBuilder` (originais íntegros, HTML inteiro) e
  `GenerationService` (recusa).
- **Pontos de integração**: `VectorRepository` como único ponto que fala Chroma, com a
  operação `known(ids)` usada na reconciliação de retomada; `DocstoreRepository` como
  único ponto que fala o docstore; três componentes falam OpenAI (`TableSummaryService`,
  `ImageDescriptionService`, `GenerationService`).
- **Notas**: uma por decisão vinculante (multi-vector seletivo, `doc_id` determinístico,
  `Protocol` do descritor, invariante do prompt), mais a semântica de status.

```plantuml
@startuml componente
!pragma charset UTF-8
!include https://raw.githubusercontent.com/plantuml-stdlib/C4-PlantUML/v2.10.0/C4_Component.puml

LAYOUT_TOP_DOWN()

title C3 • Componentes do pacote rag/ - Pipeline multimodal de ponta a ponta (rag-04-multimodal-docs)

Container_Boundary(pacote, "rag/") {

  Component(api, "rag/api/", "FastAPI", "Rotas do contrato 1.3.0: /ask, /ingest, /health, /capabilities. Valida question e options.k na borda (422) e aplica require_index (409) antes de qualquer chamada paga. Traduz exceção de domínio em status.")

  Component(ingestionFacade, "IngestionFacade", "facade", "Caso de uso da ingestão. Orquestra seleção, partição, roteamento, idempotência, enriquecimento e indexação dupla, sem lógica própria. RECONCILIA, não recria: pula doc_id que já existe no docstore e retoma falha parcial re-indexando original sem representação, sem repagar enriquecimento.")
  Component(queryFacade, "QueryFacade", "facade", "Caso de uso da consulta. Orquestra retrieval, prompt e geração, sem lógica própria. Pergunta única, sem histórico e sem reescrita.")
  Component(resetFacade, "ResetFacade", "facade", "Caso de uso do reset. Zera o índice PRIMEIRO e o docstore DEPOIS (inverso exato da ordem de gravação) numa operação só, para nunca deixar metade viva. Preserva data/partition/ (ADR-005). Idempotente.")

  Component(partition, "PartitionService", "service", "Estágio local da ingestão: devolve os elementos brutos do PDF pagando o hi_res só quando não há cache válido. Não conhece unstructured nem disco: coordena um Partitioner e um PartitionCache injetados. Acerto e descarte de cache são sempre anunciados, nunca silenciosos.")
  Component(routing, "ElementRoutingService", "service", "Única tradução de Element do unstructured para DocumentUnit do domínio. Texto agrupado com chunk_by_title (~1000 caracteres); cada Table e cada Image como unidade própria, NUNCA agrupada. Copia a figura canônica para data/figures/ por doc_id e deduplica conteúdo idêntico.")
  Component(enrichment, "EnrichmentService", "service", "Estágio PAGO da ingestão: orquestra TableSummaryService e ImageDescriptionService para preencher a representação das unidades NOVAS. Seletivo (ADR-002): texto narrativo passa direto. Não decide quem é novo e não grava nada.")
  Component(indexing, "IndexingService", "service", "Gravação nos dois armazéns em ordem FIXA (ADR-001): o original vai ao docstore ANTES de a representação ir ao índice. Falha no meio deixa original sem representação (a retomada completa), nunca hit órfão.")
  Component(tableSummary, "TableSummaryService", "service", "Resume tabelas HTML em linguagem natural buscável: entidades, métricas, período e nomes de coluna explícitos. Em lote, max_concurrency=5, só para unidades novas.")
  Component(imageDesc, "ImageDescriptionService", "service (Protocol)", "Descreve imagens via gpt-4o-mini visão: base64 em mensagem image_url, prompt qualitativo com ressalva de precisão. Respeita descrever_imagens (default true). Implementação OpenAI; modelo local previsto como segunda.")
  Component(retrieval, "RetrievalService", "service", "Busca densa top-k no vetorial, extrai os doc_ids dos hits e resolve os originais no docstore. Hit órfão é descartado com warning e a consulta segue. Devolve resultado com métrica por estágio.")
  Component(promptBuilder, "PromptBuilder", "service", "format_context com os originais ÍNTEGROS: texto cru para kind=texto, HTML completo para kind=tabela, descrição para kind=imagem. Numeração 1-based preservada; tamanho do contexto logado; truncamento por tabela nunca silencioso.")
  Component(generation, "GenerationService", "service", "Gera a resposta com instrução de recusa quando o contexto não sustenta. Fronteira da geração com o LLM.")
  Component(health, "HealthChecker", "service", "Reporta Chroma, docstore e a dessincronia entre os dois (contagens incompatíveis viram status degraded). Chroma fora do ar é 503.")
  Component(ingestionLog, "IngestionLog", "service (Protocol)", "Porta de diagnóstico por estágio da ingestão, declarada em service/ e consumida por services e facades. NullIngestionLog é o default: log é diagnóstico, não comportamento. O ConsoleReporter é o adaptador; nada em service/ ou facade/ importa presenter.")

  Component(vectorRepo, "VectorRepository", "repository (Protocol)", "Indexa e busca as representações no Chroma via HttpClient, com doc_id, kind, page e source no metadado. Expõe known(ids), usado na reconciliação de retomada da ingestão (ADR-007). Cliente com escopo de processo, criado uma vez na composição.")
  Component(docstoreRepo, "DocstoreRepository", "repository (Protocol)", "Guarda e resolve originais por doc_id num LocalFileStore em data/docstore/, atrás da interface BaseStore. known(ids) decide quem é novo na ingestão. Nomes de arquivo derivam do doc_id, nunca de conteúdo do PDF.")
  Component(corpusReader, "PdfCorpusReader", "repository (Protocol CorpusReader)", "Seleção dos PDFs de entrada: glob pdfs/*.pdf NÃO recursivo, pdfs/fora-do-corpus/ fica de fora de propósito. files() lista sem custo; require_files() falha com corpus vazio ANTES de qualquer trabalho.")
  Component(unstrPartitioner, "UnstructuredPartitioner", "repository (Protocol Partitioner)", "Roda o hi_res com infer_table_structure e extração de imagens para data/figures/ (modelos locais em CPU: YOLOX, Table Transformer, Tesseract). O que atravessa esta fronteira é Element do unstructured, de propósito: a tradução para domínio acontece uma vez, no ElementRoutingService.")
  Component(partitionCache, "FilePartitionCache", "repository (Protocol PartitionCache)", "Persiste e restaura os Elements da partição bruta em data/partition/, por hash do CONTEÚDO do PDF (ADR-005). Cache corrompido é descartado, anunciado e refeito.")

  Component(console, "ConsoleReporter", "presenter", "Único componente que escreve no terminal. Adaptador da porta IngestionLog. Logs estruturados por estágio: contagens por categoria e página, acerto de cache, doc_ids pulados, hits órfãos descartados, truncamento de tabela.")
  Component(json, "JsonPresenter", "presenter", "Serializa no contrato 1.3.0. Omite campo opcional ausente, nunca emite null; content_html só com kind=tabela; HTML nunca dentro de excerpt.")

  Component(dominio, "domain/ (models.py, identity.py)", "domínio", "DocumentUnit, ElementCounts, IndexMatch, SearchHit, RetrievalResult, Answer, IngestionReport (com elements), ResetReport; compute_doc_id determinístico por hash de conteúdo + origem + tipo. Folha: não importa LangChain nem vocabulário do Chroma.")
  Component(config, "config.py + exceptions.py", "base", "Faixas de k (1 a 20), default de descrever_imagens, strategy do unstructured (fast como contingência via .env), propriedades do Chroma e a hierarquia RagException.")
}

ContainerDb_Ext(chroma, "Chroma", "Container Docker, porta 8002", "Representações com doc_id, kind, page e source no metadado")
ContainerDb(corpusDb, "pdfs/", "Sistema de arquivos", "Corpus de entrada; pdfs/fora-do-corpus/ jamais alcançado pelo glob")
ContainerDb(docstoreDb, "data/docstore/", "LocalFileStore", "Originais por doc_id, fonte de verdade")
ContainerDb(particaoDb, "data/partition/", "Sistema de arquivos", "Cache da partição bruta")
ContainerDb(figurasDb, "data/figures/", "Sistema de arquivos", "Imagens extraídas")
System_Ext(openai, "API da OpenAI", "gpt-4o-mini texto e visão, text-embedding-3-small")

Rel(api, ingestionFacade, "monta na rota e chama")
Rel(api, queryFacade, "monta na rota e chama")
Rel(api, json, "serializa")
Rel(api, health, "confere antes de servir")

Rel(ingestionFacade, corpusReader, "require_files() antes de qualquer custo")
Rel(ingestionFacade, partition, "particiona, com cache")
Rel(ingestionFacade, routing, "roteia os elementos por categoria")
Rel(ingestionFacade, docstoreRepo, "known(ids): decide quem é novo")
Rel(ingestionFacade, vectorRepo, "count() antes do estágio pago; known(ids) na reconciliação de retomada")
Rel(ingestionFacade, enrichment, "enriquece as unidades NOVAS")
Rel(ingestionFacade, indexing, "indexa na ordem fixa")

Rel(enrichment, tableSummary, "resume as tabelas novas")
Rel(enrichment, imageDesc, "descreve as imagens novas, se descrever_imagens")

Rel(indexing, docstoreRepo, "grava o original PRIMEIRO")
Rel(indexing, vectorRepo, "indexa a representação DEPOIS")

Rel(resetFacade, vectorRepo, "zera o índice PRIMEIRO")
Rel(resetFacade, docstoreRepo, "zera o docstore DEPOIS")

Rel(queryFacade, retrieval, "retrieve(pergunta, k)")
Rel(queryFacade, promptBuilder, "format_context(originais)")
Rel(queryFacade, generation, "generate()")

Rel(retrieval, vectorRepo, "busca densa top-k, cronometrada em search_s")
Rel(retrieval, docstoreRepo, "resolve originais por doc_id")
Rel(retrieval, dominio, "devolve resultado com métrica")

Rel(partition, unstrPartitioner, "Partitioner.partition(), só quando não há cache")
Rel(partition, partitionCache, "load e save, por hash do conteúdo")
Rel(partitionCache, particaoDb, "persiste e restaura os Elements", "filesystem")
Rel(unstrPartitioner, figurasDb, "extrai as imagens", "filesystem")
Rel(corpusReader, corpusDb, "glob pdfs/*.pdf, NÃO recursivo", "filesystem")
Rel(routing, figurasDb, "copia a figura canônica, nomeada pelo doc_id", "filesystem")
Rel(imageDesc, figurasDb, "lê a imagem para o base64", "filesystem")

Rel(health, vectorRepo, "conta o índice")
Rel(health, docstoreRepo, "conta o docstore")

Rel(vectorRepo, chroma, "indexa e busca", "HTTP :8002")
Rel(docstoreRepo, docstoreDb, "grava e resolve", "LocalFileStore")

Rel(tableSummary, openai, "resumo, com retries e backoff", "HTTPS")
Rel(imageDesc, openai, "descrição em visão", "HTTPS")
Rel(generation, openai, "geração com recusa", "HTTPS")

Rel(console, ingestionLog, "implementa a porta, sem import: Protocol estrutural")
Rel(ingestionFacade, ingestionLog, "diagnóstico por estágio, pela porta")

Rel(console, dominio, "lê")
Rel(json, dominio, "lê")

note as ADR002
  **ADR-002: multi-vector SELETIVO.**
  Resumo é remédio para representação ruim, não pipeline
  padrão. Texto narrativo embeda direto; só tabela e
  imagem ganham representação enriquecida.

  • Diverge do diagrama do guia, de propósito
  • 1 original para N representações: o esquema já comporta
  • Multi-representação é pendência declarada, não escopo
end note

note as ADR003
  **ADR-003: doc_id determinístico por conteúdo.**
  Hash de conteúdo + origem + tipo, idêntico em qualquer
  execução. É a chave da idempotência e da ligação entre
  os dois armazéns.

  • Unidade com doc_id existente é pulada: sem repagar
  • Falha no meio do enriquecimento: a reexecução retoma
  • Diverge do uuid4 do guia
end note

note as ADR006
  **ADR-006: o descritor de imagens é Protocol.**
  Visão da OpenAI hoje; modelo local é a segunda
  implementação plausível, sem reescrita.

  • base64 em image_url, prompt qualitativo
  • Evidência de imagem qualitativa, sem prometer valor exato
  • descrever_imagens=false: extrai e conta, não descreve
end note

note as PROMPT
  **Invariante central: o índice acha, o docstore responde.**
  Para hit kind=tabela, o conteúdo enviado ao LLM vem do
  docstore, NUNCA do índice. O resumo busca; o HTML responde.

  • excerpt carrega resumo ou descrição; content_html, a tabela
  • HTML nunca dentro de excerpt
  • Tamanho do contexto logado; truncamento nunca silencioso
end note

note as SAUDE
  **Saúde REPORTA estado; quem falha é quem trabalha.**
  GET /health responde 200 com status degraded na
  dessincronia, e nunca 409. O 409 é do POST /ask com
  índice vazio, antes de qualquer chamada paga.
end note

ADR002 .. enrichment
ADR003 .. dominio
ADR006 .. imageDesc
PROMPT .. promptBuilder
SAUDE .. health

SHOW_LEGEND()
@enduml
```

## Rastreabilidade aos ADRs

O projeto tem **oito ADRs** (`docs/adrs/generated/RAG/`) — os seis da primeira geração
mais os ADR-007 e ADR-008, surgidos com a implementação — e os três diagramas os
referenciam por número nas notas e descrições.

| ADR | Onde aparece |
| --- | --- |
| 001, dois armazéns ligados por `doc_id` | nota do C1, nota e ordem de gravação no C2, relações da `IngestionFacade` no C3 |
| 002, multi-vector seletivo | nota do C3 |
| 003, `doc_id` determinístico por conteúdo | nota do C1 (custo), nota do C2 (idempotência), nota do C3 |
| 004, contrato compartilhado 1.3.0 aditivo | descrição do `serve.py` e do frontend no C2, `rag/api/` e `JsonPresenter` no C3 |
| 005, cache da partição bruta | nota do C2, `PartitionService` no C3 |
| 006, descritor de imagens atrás de `Protocol` | nota do C3, `ImageDescriptionService` |
| 007, idempotência reconciliada pelos dois armazéns | descrição da `IngestionFacade` e `known(ids)` do `VectorRepository` no C3 |
| 008, `content_html` só com HTML estrutural | invariante servida pelo par `RetrievalService` e `JsonPresenter` no C3 |

As três decisões da sessão de PRD (frontend na mesma entrega, pergunta única sem
histórico, evidência de imagem qualitativa) aparecem, respectivamente, no frontend do C1
e do C2, na descrição do `ask.py` e da `QueryFacade`, e na nota do ADR-006.

## Resultado da validação

### Checklist

- [x] Todos os elementos rastreiam ao FDD, ao HLD ou estão registrados como inferência
- [x] Nenhum item excluído do escopo aparece nos diagramas
- [x] Tecnologias e versões conferem com a seção 8 do FDD
- [x] Progressão de detalhe C1 → C2 → C3
- [x] Biblioteca embarcada tratada corretamente: os modelos do hi_res não são System nem Container
- [x] `!pragma charset UTF-8` presente nos três diagramas
- [x] `SHOW_LEGEND()` presente nos três diagramas
- [x] Notas curtas, em tópicos, sem referência a seção de FDD
- [x] Idioma do FDD, português brasileiro, com acentuação correta
- [x] Termos técnicos e nomes de componentes mantidos em inglês
- [x] Portas conferidas: API em 8080, Chroma em 8002, nenhuma outra inventada
- [x] **Conferência contra o código real de `rag/` feita em 2026-08-02** (segunda
      geração, como o precedente do rag-03): nomes de classe, camadas e relações do C3
      batem com `rag/facade/`, `rag/service/`, `rag/repository/` e `rag/presenter/`
- [x] Divergências código × primeira geração incorporadas: `ElementRoutingService`
      separado do `PartitionService`, `EnrichmentService`, `IndexingService`,
      `PdfCorpusReader`, `ResetFacade`, porta `IngestionLog`, par
      `UnstructuredPartitioner`/`FilePartitionCache` e `known(ids)` no
      `VectorRepository`

### Consistência entre níveis

- Os dois armazéns são a mesma afirmação nos três níveis: nota no C1, `ContainerDb`
  com ordem de gravação no C2, relações da `IngestionFacade` e do `RetrievalService`
  no C3, sempre com o docstore como fonte de verdade.
- O cache de partição aparece como custo zero de reingestão no C1, como `ContainerDb`
  com a fronteira local/pago no C2 e como responsabilidade do `PartitionService` no C3.
- O enriquecimento seletivo aparece como "só do que embeda mal" no C1, como chamada em
  lote no C2 e como os dois services de enriquecimento com a nota do ADR-002 no C3.
- A semântica de status (200 `degraded` na saúde, 409 do `/ask` antes de custo) é
  afirmada com o mesmo texto no C2 e no C3.
- O contrato 1.3.0 aditivo aparece na relação frontend-sistema no C1, na descrição do
  `serve.py` e do frontend no C2 e no par `rag/api/` e `JsonPresenter` no C3.
- Conferência contra `rag/` **feita em 2026-08-02**, como o precedente do rag-03 fez na
  segunda geração dos diagramas dele. O C3 foi ajustado para o código real; C1 e C2
  permanecem válidos como estavam (a decomposição interna do pacote é detalhe do C3).
