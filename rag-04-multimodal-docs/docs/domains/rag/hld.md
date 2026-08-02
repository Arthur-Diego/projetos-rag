### HLD: rag-04-multimodal-docs (domínio rag)

Versão: 1.0
Data: 2026-08-01
Responsável: Arthur Diego (autor da trilha)

Fonte da entrevista: fluxo dd-greenfield, conduzida em 01/08/2026. Este projeto não tem
`docs/prd.md` (ver `docs/dd.md`); o porquê de negócio está registrado aqui.

---

### Objetivo técnico

Construir um pipeline RAG que ingere PDFs complexos separando texto, tabelas e imagens
com `unstructured` na estratégia `hi_res`, enriquece na ingestão (LLM resume tabelas;
`gpt-4o-mini` em modo visão descreve imagens) e aplica o padrão multi-vector retriever:
a representação que busca bem (resumo ou descrição em linguagem natural) é indexada no
vector store, e o conteúdo que responde bem (a tabela HTML íntegra, o texto original) é
o que chega ao LLM na consulta, resolvido por `doc_id` num docstore separado.

O problema endereçado é a falha estrutural de ingestão dos projetos 1 a 3: o
`PyPDFLoader` transforma tabela em texto sem estrutura ("sopa de números" sem
cabeçalho) e ignora imagens por completo. Perguntas cuja resposta vive numa célula de
tabela ou num gráfico eram irrespondíveis por melhor que fosse a busca; o rag-03
melhorou o ranking do que estava no índice, este projeto melhora o que existe no índice
e o que chega ao LLM. Não se acha o que nunca foi indexado.

Critério de sucesso (o "funcionou se" do guia): uma pergunta cuja resposta só existe
numa célula de tabela ("qual foi a receita no 3T24?") é respondida corretamente, e o
contexto impresso mostra que chegou a tabela em HTML, não o resumo.

Corpus: Relatório de Desempenho 3T24 da Petrobras (versão resumida em reais), em
`pdfs/petrobras-desempenho-3t24.pdf`. Controle negativo de grounding (nunca indexado):
Relatório de Inflação dez/2024 do Banco Central, em `pdfs/fora-do-corpus/`.

Dependências com outros sistemas
- Contrato HTTP compartilhado `../docs/contracts/rag-api.yaml` (evolui para 1.3.0)
- Frontend genérico da trilha (`../frontend/`), consumidor do contrato
- API da OpenAI: `gpt-4o-mini` (texto e visão) e `text-embedding-3-small`
- Projetos anteriores como precedente conceitual (rag-01 a rag-03)

---

### Arquitetura geral

Monólito Python em camadas, conforme `../docs/guidelines/arquitetura-em-camadas.md`:
`api/ -> facade/ -> service/ -> repository/ -> domain/`, com `presenter/` para saída,
raiz de composição em `composition.py` e entrypoints finos (`ingest.py`, `ask.py`,
`serve.py`). Grafo estritamente descendente; nenhuma camada chama `sys.exit()` nem
escreve em stdout.

Ambiente de implantação
- Local (WSL2), autor único
- Chroma em container Docker (`chromadb/chroma:1.5.9`, porta 8002, healthcheck
  validado na trilha, volume próprio). Decisão do autor: manter o padrão de container
  dos projetos 1 a 3, em vez do Chroma embarcado sugerido pelo guia
- API FastAPI em `127.0.0.1:8080`, como nos projetos anteriores

Tecnologias principais
- Stack completa fixada em `docs/guidelines/README.md` (langchain 1.3.14,
  langchain-chroma 1.1.0, langchain-classic 1.0.8 para o MultiVectorRetriever,
  unstructured[pdf] 0.24.1, fastapi 0.141.1, mypy 2.3.0, pytest 9.1.1)
- Modelos locais do `hi_res` (sem custo de API, CPU): YOLOX para layout,
  Table Transformer para estrutura de tabela, Tesseract (por) para OCR
- Modelos pagos (OpenAI): `gpt-4o-mini` para resumos, descrições e geração;
  `text-embedding-3-small` para embeddings

Padrões adotados
- Arquitetura em camadas com raiz de composição
- Multi-vector retriever: separação entre representação indexada e conteúdo entregue
- Multi-vector seletivo: resumo é remédio para representação ruim, não pipeline padrão
  (texto narrativo entra direto; ver ADR-002)
- `Protocol` nos pontos de troca plausível (descritor de imagens; ver ADR-006)
- Ingestão idempotente por `doc_id` determinístico (ver ADR-003)
- Cache de estágio entre a fase local (partição) e a fase paga (ver ADR-005)

---

### Componentes e responsabilidades

| Componente | Responsabilidades | Dependências |
| ----------- | ----------------- | ------------ |
| `PartitionService` (novo) | Rodar `unstructured hi_res` com `infer_table_structure` e extração de imagens; classificar elementos em texto, tabela e imagem; ler e gravar o cache de partição em `data/partition/` | `unstructured`, filesystem |
| `TableSummaryService` (novo) | Resumir tabelas HTML em linguagem natural buscável (entidades, métricas, período, nomes de coluna explícitos), em lote com `max_concurrency=5` | OpenAI (gpt-4o-mini) |
| `ImageDescriptionService` (novo, atrás de `Protocol`) | Descrever imagens extraídas via `gpt-4o-mini` visão (base64 em mensagem `image_url`) | OpenAI (visão) |
| `VectorRepository` (adaptado) | Indexar e buscar as representações no Chroma (porta 8002), com `doc_id`, `kind` e página no metadado | Chroma via HttpClient |
| `DocstoreRepository` (novo) | Guardar e resolver originais por `doc_id` num `LocalFileStore` em `data/docstore/`, atrás da interface `BaseStore` | Filesystem |
| `RetrievalService` (adaptado) | Buscar top-k no vetorial, extrair `doc_id`s, resolver originais no docstore, devolver resultado com métrica por estágio | `VectorRepository`, `DocstoreRepository` |
| `IngestionFacade` | Orquestrar partição -> enriquecimento -> indexação dupla, sem lógica própria | services |
| `QueryFacade` | Orquestrar reescrita (se houver) -> retrieval -> prompt -> geração, sem lógica própria | services |
| `GenerationService`, `PromptBuilder` (herdados) | Montar o prompt com originais íntegros (HTML de tabela entra inteiro); gerar resposta com recusa quando o contexto não sustenta | OpenAI |
| Presenters, rotas, `HealthChecker` (herdados/adaptados) | Saída console e JSON; rotas do contrato; `/health` reporta Chroma, docstore e dessincronia entre os dois | camadas superiores |

---

### Fluxo de requisições e de dados

**Fluxo de requisição (ingestão: `POST /ingest` ou `ingest.py`)**
- `PartitionService` verifica o cache de partição; se ausente, roda `hi_res` no PDF
  (minutos de CPU, sem custo de API) e grava o cache em `data/partition/`
- Elementos são roteados por categoria: `Table` vira HTML estruturado; `Image` vira
  arquivo em `data/figures/`; `NarrativeText` segue como texto
- Enriquecimento pago, apenas do que mudou (idempotência por `doc_id`): tabelas passam
  pelo `TableSummaryService`, imagens pelo `ImageDescriptionService`
- Indexação dupla: representação (texto direto, resumo ou descrição) vai ao Chroma com
  `doc_id` no metadado; original (texto, HTML, caminho da imagem) vai ao docstore sob o
  mesmo `doc_id`
- Resposta do `/ingest` traz a contagem `elements` por tipo

**Fluxo de requisição (consulta: `POST /ask`)**
- Pergunta vira embedding e busca densa no Chroma sobre as representações (top-k)
- `RetrievalService` extrai os `doc_id`s dos hits e resolve os originais no docstore
- `PromptBuilder` monta o contexto com os originais íntegros
- LLM responde com citações; recusa quando o contexto não sustenta (herança dos
  projetos 2 e 3)

**Fluxo de dados**
- PDF -> partição `hi_res` -> cache (`data/partition/`) -> [tabela -> resumo | imagem ->
  descrição | texto -> direto] -> Chroma (representações) + docstore (originais)
- Pergunta -> embedding -> hits (resumos) -> `doc_id` -> originais -> prompt -> resposta

---

### Modelo de dados (alto nível)

Entidades principais
- `DocumentElement`: elemento particionado do PDF; categoria (texto, tabela, imagem),
  página, origem. Existe apenas durante a ingestão
- `IndexedRepresentation`: o que foi embedado (texto direto, resumo de tabela ou
  descrição de imagem); carrega `doc_id`, `kind` e página no metadado. Vive no Chroma
- `StoredOriginal`: o conteúdo íntegro (texto, HTML da tabela ou caminho da imagem em
  `data/figures/`), com metadados de fonte. Vive no docstore

Relações
- 1 `DocumentElement` -> 1 `StoredOriginal` -> N `IndexedRepresentation`. O N é
  deliberado: a v1 usa uma representação por original, mas o esquema já comporta
  multi-representação (perguntas hipotéticas do exercício 2, tabela crua além do
  resumo) sem migração

Fonte de verdade
- O PDF é a origem externa. Entre os armazéns, o docstore é a fonte de verdade dos
  conteúdos; o Chroma é índice derivado, reconstruível a partir do docstore sem rodar
  `hi_res` de novo (só re-embedar). Perder o Chroma custa minutos; perder o docstore
  custa a ingestão inteira

Versionamento e retenção
- Sem versionamento de documentos na v1 (corpus fixo). "Zerar" significa limpar os dois
  armazéns e reingerir, com um comando único para não deixar metade viva

---

### Interfaces públicas

| Nome | Tipo | Protocolo | Exposição | SLAs/Limites |
| ---- | ---- | ---------- | --------- | ------------- |
| `POST /ask` | API | REST (contrato 1.3.0) | Interna (loopback) | Segundos; dominado pela geração |
| `POST /ingest` | API | REST (contrato 1.3.0) | Interna (loopback) | Minutos na primeira execução (`hi_res`); síncrono com timeout generoso documentado; ingestão assíncrona é pendência declarada |
| `GET /health` | API | REST | Interna | Reporta Chroma, docstore e dessincronia |
| `GET /capabilities` | API | REST | Interna | Parâmetros ajustáveis expostos ao frontend |

Evolução do contrato compartilhado (1.2.0 -> 1.3.0, aditiva; ver ADR-004):
- `SearchHit.kind` (opcional): `texto | tabela | imagem`
- `SearchHit.content_html` (opcional): HTML da tabela original quando `kind=tabela`,
  para o frontend renderizar a tabela de verdade
- Resposta do `/ingest` ganha contagem `elements` por tipo
- Semântica sem mudança de esquema: `excerpt` carrega o resumo quando `kind=tabela` e a
  descrição quando `kind=imagem`; `page` vale para os três; `provenance` fica ausente
  (só há caminho denso neste projeto)

Fora do escopo da v1, declarado: servir o arquivo da imagem ao frontend (exigiria rota
de mídia com preocupações de path traversal e cache que não ensinam RAG); a imagem
participa como descrição textual.

---

### Considerações de escalabilidade e disponibilidade

Abordagem geral
- O gargalo é a ingestão, por desenho: `hi_res` custa minutos de CPU e o enriquecimento
  custa chamadas pagas. A consulta é leve (uma busca densa, uma resolução em disco, uma
  geração)

Técnicas aplicadas
- Resumos e descrições em lote com `max_concurrency=5` (limite de rate da OpenAI)
- Ingestão idempotente: `doc_id` determinístico por hash de conteúdo; reingerir não
  duplica entradas nem repaga resumo/embedding do que não mudou (ADR-003)
- Cache da partição bruta em `data/partition/`: iterar no prompt de resumo não paga
  `hi_res` de novo (ADR-005). O cache economiza tempo; a idempotência economiza dinheiro
- Clientes com escopo de processo (lição do rag-03): HttpClient do Chroma, cliente
  OpenAI e `LocalFileStore` criados uma vez na composição, nunca por requisição
- Sem cache de consulta, sem rate limiting próprio: autor único, sem concorrência real

Meta de disponibilidade
- Sem meta formal (estudo local). Healthcheck do container é obrigatório (padrão da
  trilha); `/health` denuncia dessincronia entre Chroma e docstore

---

### Segurança

Autenticação
- Nenhuma: API amarrada em `127.0.0.1:8080`, nada escuta fora da máquina. Chroma na
  8002 idem (container local, sem auth)

Autorização
- Não se aplica (autor único, loopback)

Proteção de dados
- Corpus 100% público (relatório de RI da Petrobras, relatório do BCB): sem PII, sem
  criptografia em repouso; TLS não se aplica em loopback
- Risco aceito e documentado: injeção via corpus. O HTML das tabelas entra íntegro no
  prompt; um PDF malicioso poderia carregar instruções numa tabela. Na v1 não há
  sanitização além do que o `unstructured` faz, porque o corpus é escolhido pelo autor.
  Em produção isso seria mitigação obrigatória
- Path traversal no docstore e nas figuras: neutralizado porque os nomes de arquivo
  derivam do `doc_id` (hash gerado pelo próprio sistema), nunca de conteúdo do PDF nem
  de entrada do usuário

Gestão de segredos
- `OPENAI_API_KEY` apenas via `.env` (nunca commitado; `.env.example` como modelo). É a
  única credencial do projeto

---

### Observabilidade

Logs
- Estruturados por estágio, com a ingestão como foco: partição (elementos por categoria
  e por página, acerto do cache), resumos e descrições (quantidade, tokens), indexação
  (vetores e originais gravados). Quando uma pergunta falhar na validação, "a tabela
  certa foi detectada?" tem que ser respondível por log, sem reingerir

Métricas
- Consulta: duração por estágio (busca, resolução no docstore, geração) e hits por
  `kind`; "chegou tabela ao prompt?" é métrica, porque é o critério de sucesso do guia
- Ingestão: durações por fase e contagem `elements` devolvida pelo `/ingest`
- Tamanho do contexto logado por consulta (guarda o risco 5)

Tracing
- Não há (processo único local). O `ConsoleReporter` herdado cumpre o papel

Dashboards e alertas
- Nenhum. A tabela de medição da validação vive em `docs/operations/`, com scripts
  reexecutáveis (que gastam chamadas pagas, como no rag-03)

---

### Riscos arquiteturais e mitigação

#### Risco 1: `hi_res` não detecta as tabelas do corpus
- **Probabilidade:** média
- **Impacto:** alto. O projeto inteiro depende da detecção; a falha é silenciosa e vira
  "multi-vector não funciona" quando a tabela nunca foi extraída
- **Mitigação:**
  - Validar a detecção cedo e isolada: script de inspeção pós-partição (contagem e
    preview das tabelas HTML contra o PDF aberto ao lado), antes de qualquer resumo
  - Primeiro botão a girar: trocar o modelo de layout do `unstructured` (configurável
    por parâmetro/variável de ambiente)
- **Plano de contingência:** trocar o corpus

#### Risco 2: resumo não casa com as perguntas reais
- **Probabilidade:** média
- **Impacto:** o acerto cai e a causa fica ambígua (busca ruim ou resumo ruim?)
- **Mitigação:**
  - Prompt de resumo do guia: entidades, métricas, período e nomes de coluna explícitos
  - Avaliar em branch `exp/` as perguntas hipotéticas do exercício 2
- **Plano de contingência:** multi-representação (o modelo 1->N da etapa 5 já comporta)

#### Risco 3: setup nativo quebra no WSL2 (poppler, tesseract, onnx)
- **Probabilidade:** média
- **Impacto:** bloqueante no início; o guia chama este de "o setup mais chato dos dez"
- **Mitigação:**
  - Instalar e rodar um smoke test de partição como primeiríssima tarefa da implementação
- **Plano de contingência:** `strategy="fast"` temporária para destravar o resto do
  pipeline enquanto o `hi_res` não sobe (sem tabelas, declarado)

#### Risco 4: dessincronia entre Chroma e docstore
- **Probabilidade:** baixa
- **Impacto:** busca acha `doc_id` órfão; metade do índice vira peso morto
- **Mitigação:**
  - `/health` compara contagens e denuncia
  - Comando único de reset: zera os dois armazéns e reingere
- **Plano de contingência:** reingestão completa

#### Risco 5: tabelas HTML grandes estouram contexto e custo do prompt
- **Probabilidade:** baixa
- **Impacto:** custo por consulta sobe; resposta degrada
- **Mitigação:**
  - top-k moderado; tamanho do contexto logado por consulta
- **Plano de contingência:** truncamento documentado por tabela, nunca silencioso

#### Risco 6: reingestão cara demais para iterar
- **Probabilidade:** média
- **Impacto:** atrito de desenvolvimento; cada ajuste de prompt de resumo custaria
  minutos de `hi_res`
- **Mitigação:**
  - Cache da partição bruta em `data/partition/` (ADR-005)
  - Idempotência por `doc_id`: não repaga resumo nem embedding do que não mudou
- **Plano de contingência:** aceitar o custo (corpus é um PDF)

---

### ADRs e próximos passos

ADRs associados (a escrever em `docs/adrs/generated/RAG/`)
- ADR-001: dois armazéns ligados por `doc_id` (Chroma em container + LocalFileStore;
  docstore como fonte de verdade; object storage e metadado-no-Chroma rejeitados)
- ADR-002: multi-vector seletivo (texto direto; resumo só para tabela e imagem;
  diverge do diagrama do guia)
- ADR-003: `doc_id` determinístico por conteúdo (idempotência; diverge do `uuid4` do guia)
- ADR-004: contrato compartilhado 1.3.0, aditivo (`kind`, `content_html`, `elements`)
- ADR-005: cache da partição bruta como fronteira entre estágio local e estágio pago
- ADR-006: descritor de imagens atrás de `Protocol` (visão da OpenAI hoje, modelo local
  como segunda implementação plausível)

Decisões pendentes
- Rota de mídia para servir figuras ao frontend (v2; hoje a imagem é descrição textual)
- Ingestão assíncrona (hoje síncrona com timeout generoso documentado)
- Multi-representação: perguntas hipotéticas (exercício 2) e tabela crua além do resumo
- Troca do modelo de layout do `unstructured`, se a validação encontrar tabelas não
  detectadas

Próximos passos
- Escrever os 6 ADRs (Passo 5 do dd-greenfield)
- Encadear `dd-feature` para a primeira feature: o pipeline multimodal de ponta a ponta
  (Passo 6)
- Na implementação, primeiras tarefas obrigatórias: setup nativo + smoke test de
  partição (risco 3) e inspeção das tabelas detectadas no corpus (risco 1)
