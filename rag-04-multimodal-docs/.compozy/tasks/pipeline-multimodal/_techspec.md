### FDD: Pipeline multimodal de ponta a ponta

Versão: 1.0
Data: 2026-08-02
Responsável: Arthur Diego (autor da trilha)

PRD da feature: `.compozy/tasks/pipeline-multimodal/_prd.md` (user stories em
`.compozy/tasks/pipeline-multimodal/_user_stories.md`). Terreno: HLD
`docs/domains/rag/hld.md` v1.0 e ADRs 001 a 006 em `docs/adrs/generated/RAG/`.

---

### 1. Contexto e motivação técnica

O `PyPDFLoader` dos projetos 1 a 3 converte tabela em texto sem estrutura e ignora
imagens: perguntas cujo alvo vive numa célula ou num gráfico são irrespondíveis por
melhor que seja a recuperação. Esta feature implementa o pipeline completo do HLD do
rag-04: partição `hi_res` do `unstructured` separando texto, tabela e imagem;
enriquecimento pago apenas do que embeda mal (resumo de tabela, descrição de imagem);
indexação dupla ligada por `doc_id` determinístico (representação no Chroma 8002,
original íntegro no `LocalFileStore`); consulta que resolve os `doc_id`s e entrega ao
LLM o original inteiro, com a tabela em HTML.

Atores: autor-consulente (frontend genérico) e autor-operador (CLI). Sistemas externos:
API da OpenAI (`gpt-4o-mini` texto e visão, `text-embedding-3-small`), Chroma em
container (porta 8002), frontend genérico da trilha como segundo consumidor do contrato
1.3.0. Limite do escopo: corpus fixo (Petrobras 3T24), autor único, loopback.

Suposições e restrições explícitas:

- As seis decisões estruturais dos ADRs do projeto valem integralmente (dois armazéns
  por `doc_id`, multi-vector seletivo, `doc_id` por hash, contrato aditivo, cache de
  partição, `ImageDescriptor` atrás de `Protocol`).
- Decisões da sessão de PRD: frontend na mesma entrega (adr-001), pergunta única sem
  histórico (adr-002), evidência de imagem qualitativa (adr-003).
- Decisões desta entrevista: texto narrativo agrupado com `chunk_by_title`
  (~1000 caracteres), tabelas e imagens fora do agrupamento; `/capabilities` expõe
  `k` (ask, default 4, 1 a 20) e `descrever_imagens` (ingest, boolean, default true);
  `/ingest` é idempotente-incremental, reset apenas por script CLI.

---

### 2. Objetivos técnicos

- Pergunta com resposta em célula de tabela respondida corretamente, com evidência em
  log de que o HTML íntegro (não o resumo) entrou no prompt. Invariante: para hit
  `kind=tabela`, o conteúdo enviado ao LLM vem do docstore, nunca do índice.
- Reingestão do corpus inalterado: zero chamadas de enriquecimento, zero embeddings
  novos, contagens dos dois armazéns inalteradas. Medida: log de ingestão reporta
  `novos=0, reaproveitados=N`.
- Segunda ingestão com cache de partição válido dispensa o `hi_res`: estágio de
  partição em segundos, com acerto de cache registrado em log.
- Contrato 1.3.0 estritamente aditivo: consumidores 1.2.0 continuam funcionando sem
  alteração (validável apontando o frontend atual para o rag-04).
- Recusa preservada: pergunta cuja resposta só existe no PDF do BCB (nunca indexado)
  retorna `refused=true`.
- Grafo de camadas estritamente descendente, mypy limpo, testes de roteamento por
  categoria e correspondência resumo/original por `doc_id` (escopo de teste fixado em
  `docs/guidelines/README.md`).

---

### 3. Escopo e exclusões

**Incluído**

- Evolução do contrato compartilhado `../docs/contracts/rag-api.yaml` para 1.3.0
  (aditiva: `SearchHit.kind`, `SearchHit.content_html`, `elements` no
  `IngestionReport`, nota de semântica idempotente no `/ingest`).
- Backend rag-04 completo em camadas: partição com cache, roteamento por categoria,
  enriquecimento (resumo e descrição), indexação dupla, consulta com resolução de
  originais, geração com recusa, `/health` com sincronia, `/capabilities`.
- Entrypoints `ingest.py`, `ask.py`, `serve.py` e script CLI de reset (zera os dois
  armazéns numa operação).
- Script de inspeção pós-partição (contagem e preview das tabelas, sem custo de API).
- Frontend genérico: renderização sanitizada de `content_html`, selo de `kind`,
  contagens `elements` no relatório de ingestão.
- Medição: `docs/operations/` com golden set por classe de alvo e script com modo
  `--sem-geracao`.
- Infra local: `docker-compose.yml` do Chroma 1.5.9 na porta 8002 com healthcheck,
  `requirements.txt`, `.env.example`, setup nativo documentado.

**Excluído**

- Conversa com histórico e reescrita de pergunta (adr-002 da sessão).
- Rota de mídia para servir a imagem ao frontend (ADR-004; v2).
- Streaming de resposta; `stream` fora de `features`.
- Valor exato lido de gráfico como promessa (adr-003 da sessão).
- Sanitização do corpus contra injeção na ingestão (risco aceito no HLD).
- Multi-representação por original e ingestão assíncrona (pendências declaradas).

---

### 4. Fluxos detalhados e diagramas

**Fluxo principal (ingestão: `POST /ingest` ou `ingest.py`)**

- Seleção de arquivos: apenas `pdfs/*.pdf` (glob sem recursão; `fora-do-corpus/` nunca
  entra).
- `PartitionService` calcula o hash do PDF e consulta `data/partition/`; com cache
  válido, carrega os elementos em segundos; sem cache, roda `hi_res` com
  `infer_table_structure=True` e extração de imagens para `data/figures/` (minutos de
  CPU) e grava o cache.
- Roteamento por categoria: elementos narrativos são agrupados com `chunk_by_title`
  (~1000 caracteres) em unidades de texto; cada `Table` vira unidade própria com HTML;
  cada `Image` vira unidade própria com caminho do arquivo.
- `doc_id` determinístico por unidade (hash de conteúdo + origem + tipo). Unidades
  cujo `doc_id` já existe no docstore são puladas (idempotência: sem novo
  enriquecimento, sem novo embedding).
- Enriquecimento pago só das unidades novas, com `max_concurrency=5`: tabelas passam
  pelo `TableSummaryService` (resumo com entidades, métricas, período e nomes de
  coluna); imagens pelo `ImageDescriptionService` se `descrever_imagens=true`
  (base64 em mensagem `image_url`, prompt qualitativo com ressalva de precisão).
- Indexação dupla na ordem: original no docstore primeiro, representação no Chroma
  depois (metadados `doc_id`, `kind`, `page`, `source`). A ordem garante que um hit no
  índice sempre encontra o original.
- Resposta: `IngestionReport` com `pages`, `chunks`, `seconds` e `elements`
  (`textos`, `tabelas`, `imagens`).

**Fluxo principal (consulta: `POST /ask` ou `ask.py`)**

- Validação de `question` e `options.k` na borda; `require_index` falha com 409 antes
  de qualquer chamada paga se o índice está vazio.
- Embedding da pergunta e busca densa top-k no Chroma sobre as representações.
- `RetrievalService` extrai os `doc_id`s dos hits e resolve os originais no
  `DocstoreRepository`; devolve resultado com métrica por estágio.
- `PromptBuilder.format_context` monta o contexto com os originais íntegros: texto
  cru para `kind=texto`, HTML completo para `kind=tabela`, descrição para
  `kind=imagem`; numeração 1-based preservada; tamanho do contexto logado.
- `GenerationService` gera com instrução de recusa quando o contexto não sustenta.
- Resposta: `Answer` com hits carregando `kind`, `excerpt` (trecho, resumo ou
  descrição conforme o tipo) e `content_html` apenas quando `kind=tabela`.

**Fluxos alternativos e exceções**

- Cache de partição corrompido ou ilegível: descarta, refaz `hi_res`, regrava; log
  denuncia o descarte.
- Falha da OpenAI no meio do enriquecimento: a ingestão para com 503; unidades já
  gravadas ficam; a reexecução retoma do que falta (idempotência por `doc_id`).
- Hit com `doc_id` sem original no docstore (dessincronia): o hit é descartado com log
  de warning e a consulta segue com os demais; `/health` denuncia a dessincronia.
  (Hipótese confirmada na entrevista: nunca 500 por hit órfão.)
- Partição sem nenhuma tabela detectada: ingestão conclui com `tabelas: 0` explícito
  no relatório (sinal do risco 1, não falha silenciosa).
- `descrever_imagens=false`: imagens são extraídas e contadas, mas não descritas nem
  indexadas nesta execução; unidades de imagem ficam pendentes para uma ingestão
  futura com a flag ligada.
- Reset (script CLI): zera coleção do Chroma e `data/docstore/` na mesma operação;
  preserva `data/partition/` por padrão; idempotente.
- Frontend: `kind` ausente (projetos 1 a 3) mantém comportamento atual;
  `kind=tabela` sem `content_html` degrada para excerpt como texto.

**Diagramas**

- A gerar pelo dd-mermaid a partir deste FDD (fluxo de ingestão, sequência da
  consulta, visão dos dois armazéns) em `docs/domains/rag/diagrams/mermaid/`.

---

### 5. Contratos públicos (assinaturas, endpoints, headers, exemplos)

Contrato compartilhado: `../docs/contracts/rag-api.yaml` versão 1.3.0 (evolução
aditiva sobre 1.2.0; editar o yaml ANTES de implementar o consumidor). Base URL local:
`http://127.0.0.1:8080`.

**Contrato 1: POST /ask**

- Tipo: endpoint
- Assinatura/Rota: `POST /ask`
- Método: POST
- Semântica de status:
  - 200: resposta com hits; `refused=true` quando o contexto não sustenta
  - 409: índice vazio; rode a ingestão
  - 422: `question` vazia ou `options.k` fora de 1 a 20
  - 500: configuração ausente ou inconsistente
  - 503: Chroma ou OpenAI fora do ar
- Semântica dos campos novos (1.3.0): `kind` em cada hit (`texto|tabela|imagem`);
  com `kind=tabela`, `excerpt` carrega o resumo e `content_html` o HTML original; com
  `kind=imagem`, `excerpt` carrega a descrição; `content_html` presente apenas quando
  `kind=tabela`; `provenance` ausente (só caminho denso). Opcional ausente é omitido
  do JSON, nunca `null`.

**Exemplo de requisição**

```json
{ "question": "Qual foi a receita no 3T24?", "options": { "k": 4 } }
```

**Exemplo de resposta**

```json
{
  "text": "A receita no 3T24 foi de R$ 129,6 bilhões [1].",
  "refused": false,
  "hits": [
    {
      "source": "petrobras-desempenho-3t24.pdf",
      "page": 3,
      "kind": "tabela",
      "score": 0.62,
      "excerpt": "Tabela de resultados consolidados do 3T24: receita de vendas, EBITDA ajustado e lucro líquido por trimestre, em bilhões de reais.",
      "content_html": "<table><tr><th>Indicador</th><th>3T24</th></tr><tr><td>Receita de vendas</td><td>129,6</td></tr></table>"
    }
  ],
  "timings": { "search_s": 0.18, "generation_s": 2.4 }
}
```

**Contrato 2: POST /ingest**

- Tipo: endpoint
- Assinatura/Rota: `POST /ingest`
- Método: POST
- Semântica de status: 200 relatório; 422 parâmetro inválido; 500 configuração; 503
  dependência externa fora do ar
- Semântica 1.3.0: `elements` (`textos`, `tabelas`, `imagens`) no `IngestionReport`;
  nota aditiva na descrição registra que projetos com ingestão idempotente reconciliam
  em vez de recriar (o rag-04 não apaga o índice ao reingerir)
- Limites: síncrono; primeira execução leva minutos (partição `hi_res` em CPU);
  timeout documentado de 15 minutos (hipótese; ajustável na validação); execuções com
  cache concluem em segundos

**Exemplo de requisição**

```json
{ "options": { "descrever_imagens": true } }
```

**Exemplo de resposta**

```json
{
  "pages": 20,
  "chunks": 58,
  "seconds": 312.4,
  "elements": { "textos": 41, "tabelas": 12, "imagens": 5 }
}
```

**Contrato 3: GET /health**

- Tipo: endpoint
- Assinatura/Rota: `GET /health`
- Método: GET
- Semântica: 200 com `status=ok|degraded`; `degraded` quando Chroma responde mas há
  dessincronia entre índice e docstore (contagens incompatíveis) ou docstore
  inacessível; 503 quando o Chroma está fora do ar. Campos opcionais do contrato
  (`collection`, `indexed_chunks`, `embedding_model`, `embedding_dimensions`)
  preenchidos; contagem do docstore reportada em campo informativo do projeto.

**Contrato 4: GET /capabilities**

- Tipo: endpoint
- Assinatura/Rota: `GET /capabilities`
- Método: GET
- Semântica: `features = [ask, ingest, sources]` (sem `history`, sem `stream`);
  `parameters`: `k` (integer, default 4, 1 a 20, applies_to ask) e
  `descrever_imagens` (boolean, default true, applies_to ingest).

**Consumidor frontend (mesma entrega)**

- Renderiza `content_html` como tabela real após sanitização (biblioteca de
  sanitização definida na implementação; hipótese: DOMPurify); selo de `kind` no
  cabeçalho do hit no molde da `Procedencia`; contagens `elements` no relatório de
  ingestão. Campos ausentes degradam para o comportamento atual.

---

### 6. Erros, exceções e fallback

Matriz de erros previstos e tratamentos:

| Condição | Tratamento | Observações |
| --- | --- | --- |
| `question` vazia ou `k` fora de faixa | 422 com `Problem` | validação na borda, antes de custo |
| Índice vazio no `/ask` | 409 com `Problem` | `require_index` antes de chamada paga (precedente rag-03) |
| Chroma fora do ar | 503 com `Problem` | ingestão e consulta falham pelo mesmo motivo |
| OpenAI indisponível ou rate limit persistente | 503 com `Problem` | após retries com backoff |
| `OPENAI_API_KEY` ausente | 500 com `Problem` | configuração, não dependência |
| PDF ausente no `ingest.py` | erro claro no console antes de custo | entrypoint valida caminho |
| Cache de partição corrompido | refaz `hi_res` e regrava | log denuncia o descarte |
| Falha no meio do enriquecimento | ingestão para com 503; reexecução retoma | unidades gravadas não repagam |
| Hit com `doc_id` órfão | descarta o hit com warning; consulta segue | `/health` denuncia dessincronia |
| Tabela maior que o limite de contexto | truncamento por tabela, logado | nunca silencioso (risco 5 do HLD) |

- Estratégias de resiliência: timeouts no cliente OpenAI e no HttpClient do Chroma;
  retries com backoff exponencial apenas nas chamadas OpenAI (enriquecimento e
  geração); `max_concurrency=5` no enriquecimento em lote; sem circuit breaker (autor
  único, processo local).
- Política de fallback: não há fallback de modelo nem de armazém na v1; falha vira
  erro explícito do contrato. Contingência de desenvolvimento: `strategy=fast` via
  `.env` destrava o pipeline sem tabelas enquanto o `hi_res` não sobe (risco 3).
- Invariantes:
  - Original no docstore antes da representação no índice; nunca o inverso.
  - Nenhuma chamada paga antes de índice acessível e estágio local concluído.
  - `doc_id` idêntico para conteúdo idêntico, em qualquer execução.
  - HTML nunca dentro de `excerpt`; `content_html` apenas com `kind=tabela`.
  - Campo opcional ausente é omitido do JSON, nunca `null`.
  - Nenhuma camada chama `sys.exit()` nem escreve em stdout.

---

### 7. Observabilidade

**Métricas**

- Ingestão: duração por fase (partição, enriquecimento, indexação), acerto de cache,
  unidades novas vs reaproveitadas, contagens `elements` por tipo, tokens gastos em
  resumos e descrições.
- Consulta: duração por estágio (`search_s`, resolução no docstore, `generation_s`),
  hits por `kind` (a métrica "chegou tabela ao prompt?" é o critério do guia),
  tamanho do contexto em caracteres, taxa de recusa.

**Logs**

- Estruturados por estágio via `ConsoleReporter` herdado; campos essenciais:
  estágio, duração, contagens por categoria e página na partição, `doc_id`s pulados
  por idempotência, descartes de cache, hits órfãos descartados, truncamento de
  tabela quando houver.

**Tracing**

- Não há (processo único local); os timings por estágio no `Answer` cumprem o papel.

**Dashboards e alertas**

- Nenhum. A tabela de medição vive em `docs/operations/` com resultados datados
  (padrão rag-03); o script avisa custo no cabeçalho e tem `--sem-geracao`.

---

### 8. Dependências e compatibilidade

| Componente | Versão mínima | Observações |
| --- | --- | --- |
| Python | 3.12.3 | venv obrigatório; sem pip no sistema |
| unstructured[pdf] | 0.24.1 | fixada; não subir para 0.25.0 (guideline) |
| langchain | 1.3.14 | fixada em guidelines/README.md |
| langchain-classic | 1.0.8 | MultiVectorRetriever |
| langchain-chroma | 1.1.0 | cliente do vetorial |
| fastapi | 0.141.1 | API |
| chromadb/chroma (container) | 1.5.9 | porta 8002, healthcheck, volume próprio |
| poppler-utils, tesseract-ocr(-por) | apt | setup nativo WSL2; primeira tarefa |
| OpenAI API | gpt-4o-mini, text-embedding-3-small | única credencial: OPENAI_API_KEY |
| mypy / pytest | 2.3.0 / 9.1.1 | mypy limpo é critério de aceite |
| frontend genérico | contrato 1.3.0 | segundo consumidor; sanitização obrigatória |

**Garantias de compatibilidade**

- 1.3.0 é aditiva: nenhum campo obrigatório muda; consumidores 1.2.0 seguem
  funcionando; o frontend evoluído continua funcionando com os projetos 1 a 3
  (campo ausente = comportamento atual).
- Portas: 8002 exclusiva do rag-04; um serviço por vez no workspace.

---

### 9. Critérios de aceite técnicos

- Pergunta de célula de tabela ("qual foi a receita no 3T24?") respondida
  corretamente; log da consulta mostra o HTML da tabela no contexto enviado ao LLM.
- Hit da tabela na resposta carrega `kind=tabela`, `excerpt` com o resumo e
  `content_html` com a tabela íntegra; validação da resposta contra o schema 1.3.0.
- Frontend renderiza a tabela de verdade (linhas e colunas visíveis) na fonte, após
  sanitização; selo de `kind` visível; `elements` no relatório de ingestão.
- Reingestão do corpus inalterado: log reporta zero unidades novas; contagens dos
  dois armazéns inalteradas; nenhuma chamada de enriquecimento disparada.
- Segunda ingestão usa o cache de partição: estágio de partição em segundos, acerto
  registrado em log.
- Controle negativo: pergunta do relatório do BCB retorna `refused=true`.
- `/health` reporta `ok` com armazéns consistentes; após remoção manual de um
  original do docstore, reporta `degraded` com evidência.
- Script de reset zera os dois armazéns numa operação; `/health` volta a consistente;
  cache de partição preservado.
- Script de inspeção lista as tabelas detectadas com página e preview, sem chamada de
  API.
- Medição em `docs/operations/`: acerto de recuperação e taxa de recusa por classe de
  alvo (texto, tabela, imagem), âncoras extraídas por caminho independente do
  pipeline; resultados datados.
- mypy limpo; pytest verde no escopo fixado (roteamento por categoria,
  correspondência resumo/original por `doc_id`); consumidor 1.2.0 (frontend atual)
  continua funcionando apontado para o rag-04.

---

### 10. Riscos e mitigação

### Risco 1: `hi_res` não detecta as tabelas do corpus

- **Probabilidade:** média
- **Impacto:** alto; falha silenciosa vira "multi-vector não funciona"
- **Mitigação:**
    - Script de inspeção pós-partição antes de qualquer resumo pago (critério 9)
    - Relatório `elements` denuncia `tabelas: 0`
    - Modelo de layout configurável por variável de ambiente (primeiro botão a girar)
- **Plano de contingência:** trocar o corpus

### Risco 2: setup nativo quebra no WSL2 (poppler, tesseract, onnx)

- **Probabilidade:** média
- **Impacto:** bloqueante no início ("o setup mais chato dos dez")
- **Mitigação:**
    - Setup nativo e smoke test de partição como primeira etapa do build order
- **Plano de contingência:** `strategy=fast` via `.env` destrava o resto do pipeline
  sem tabelas, declarado no log

### Risco 3: resumo não casa com as perguntas reais (drift resumo/conteúdo)

- **Probabilidade:** média
- **Impacto:** acerto cai com causa ambígua (busca ruim ou resumo ruim)
- **Mitigação:**
    - Prompt de resumo do guia: entidades, métricas, período, nomes de coluna
    - Medição por classe de alvo separa o sintoma (US-014)
- **Plano de contingência:** multi-representação (modelo 1 para N já comporta; branch
  `exp/`)

### Risco 4: dessincronia entre Chroma e docstore

- **Probabilidade:** baixa
- **Impacto:** hit órfão; metade do índice morta em silêncio
- **Mitigação:**
    - Ordem de gravação (original primeiro), `/health` comparando contagens, hit
      órfão descartado com warning
- **Plano de contingência:** reset e reingestão (cache preserva o `hi_res`)

### Risco 5: tabelas HTML grandes estouram contexto e custo

- **Probabilidade:** baixa
- **Impacto:** custo por consulta sobe; resposta degrada
- **Mitigação:**
    - top-k moderado (default 4), tamanho de contexto logado por consulta
- **Plano de contingência:** truncamento documentado por tabela, nunca silencioso

### Risco 6: XSS ao renderizar `content_html` no frontend

- **Probabilidade:** baixa (corpus do autor)
- **Impacto:** execução de script no navegador
- **Mitigação:**
    - Sanitização obrigatória antes do DOM; `dangerouslySetInnerHTML` só sobre HTML
      sanitizado; regra registrada no adr-001 da sessão
- **Plano de contingência:** desligar a renderização (degrada para excerpt)

---

### 11. Sequenciamento de implementação (Build Order)

| Ordem | Etapa | Depende de | Componentes/arquivos prováveis | Critérios que fecha (da seção 9) |
| --- | --- | --- | --- | --- |
| 1 | Setup nativo + infra local + smoke test de partição | - | `requirements.txt`, `.env.example`, `docker-compose.yml` (Chroma 8002), apt (poppler, tesseract), smoke script | risco 2 mitigado; pré-requisito de tudo |
| 2 | Contrato 1.3.0 no yaml compartilhado | - | `../docs/contracts/rag-api.yaml` (versão, `kind`, `content_html`, `elements`, nota do `/ingest`) | base do critério de schema; gate contracts-fit |
| 3 | Fundações do projeto | 1 | `rag/domain/models.py`, `rag/config.py`, `composition.py` (esqueleto), estrutura de camadas, mypy/pytest | mypy limpo desde o início |
| 4 | Partição com cache + inspeção | 1, 3 | `rag/service/partition_service.py`, cache em `data/partition/`, `docs/operations/inspeciona-tabelas.py` | inspeção sem API; cache em segundos |
| 5 | Armazéns e `doc_id` | 3 | `rag/repository/docstore_repository.py`, `rag/repository/vector_repository.py`, `doc_id` determinístico no domínio | invariantes de idempotência |
| 6 | Enriquecimento | 4, 5 | `rag/service/table_summary_service.py`, `rag/service/image_description_service.py` (`Protocol` + adaptador OpenAI) | resumo e descrição com `max_concurrency=5` |
| 7 | Ingestão de ponta a ponta | 6 | `rag/facade/ingestion_facade.py`, `ingest.py`, `POST /ingest`, relatório `elements`, idempotência | reingestão zero-custo; `elements` no relatório |
| 8 | Consulta de ponta a ponta | 5, 7 | `rag/service/retrieval/retrieval_service.py`, `rag/service/prompt_builder.py`, `rag/service/generation_service.py`, `rag/facade/query_facade.py`, `ask.py`, `POST /ask` | pergunta da tabela; HTML no prompt logado; recusa |
| 9 | Saúde, reset e presenters | 7, 8 | `rag/service/health_checker.py`, script de reset, `rag/presenter/{json_presenter,console_reporter}.py`, `GET /health`, `GET /capabilities`, `rag/api/` | `/health` com dessincronia; reset único |
| 10 | Frontend 1.3.0 | 2, 8 | `../frontend/src/` (render sanitizado de `content_html`, selo `kind`, `elements` no relatório) | tabela renderizada; aditividade com projetos 1 a 3 |
| 11 | Medição e runbook | 8, 9 | `docs/operations/perguntas.json`, script de medição, README de operações | medição por classe; resultados datados |
