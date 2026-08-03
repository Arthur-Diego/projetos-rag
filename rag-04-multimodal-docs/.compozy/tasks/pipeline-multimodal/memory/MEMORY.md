# Workflow Memory

Keep only durable, cross-task context here. Do not duplicate facts that are obvious from the repository, PRD documents, or git history.

## Current State

- **task_06 entregue: o PRD `pipeline-multimodal` está completo.** Golden set por
  classe de alvo, script de medição com `--sem-geracao` e rodada de 02/08/2026
  publicada em `docs/operations/README.md`. mypy limpo, 96 testes verdes.
- task_05 entregue: frontend genérico consome a 1.3.0 (tabela real sanitizada,
  selo de `kind`, `elements` no relatório) e a lista de hits duplicada virou
  `../frontend/src/Trecho.jsx`. 18 testes verdes, oxlint e build limpos.
  Falta só a task_06 (medição).
- task_04 entregue e validada contra o corpus REAL: `POST /ask`, `GET /health`
  com dessincronia, `GET /capabilities`, recuperação com resolução de originais,
  prompt com HTML íntegro, geração com recusa, `reset.py`, presenters e
  `ask.py`. mypy limpo, 76 testes verdes, Postman `meta/ingest/ask` 37/37.
- **O corpus ESTÁ ingerido** nos dois armazéns: 50 unidades (36 textos, 9
  tabelas, 5 imagens), Chroma 8002 no ar. O `hi_res` funciona — o autor rodou o
  `apt install` e criou o `.env`. Reingerir de novo custa dinheiro: a
  idempotência do ADR-003 protege, mas `reset.py` a desfaz.
- task_03 entregue em código: ingestão multimodal de ponta a ponta (partição com
  cache, roteamento, `doc_id`, dois armazéns, enriquecimento seletivo, `POST
  /ingest`, `ingest.py`, script de inspeção).
- task_02 entregue: `../docs/contracts/rag-api.yaml` publicado em **1.3.0**, aditivo.
  Backend (03/04) e frontend (05) já podem implementar contra ele.
- task_01 entregue exceto o `apt install` das dependências nativas. Venv com a
  stack fixada, Chroma 1.5.9 saudável na 8002, camadas + config + models de pé,
  `mypy` e `pytest` limpos (rodam sem argumento; config no `pyproject.toml`).

## Shared Decisions

- Nomes publicados na 1.3.0, obrigatórios para quem consumir: `SearchHit.kind`
  (`texto|tabela|imagem`), `SearchHit.content_html` (só com `kind=tabela`),
  `IngestionReport.elements` (`textos`/`tabelas`/`imagens`, zero explícito) e
  `GET /health` → **`docstore_originals`** (integer). Todos opcionais.
- O yaml compartilhado mora fora deste repositório (`../docs/contracts/`): a mudança
  dele não aparece no `git status` do rag-04 e precisa de commit próprio lá.
- Ferramentas rodam sem flag: `.venv/bin/python -m mypy` e
  `.venv/bin/python -m pytest`. Não passe caminhos nem `--ignore-missing-imports`
  na linha de comando; o `pyproject.toml` é a fonte.
- Entrypoints não implementados escrevem em stderr e devolvem 1, em vez de
  fingir sucesso. Mantenha o padrão ao substituí-los.
- **Porta `IngestionLog`** (`rag/service/ingestion_log.py`): diagnóstico por
  estágio sai por ela, implementada pelo `ConsoleReporter`. É como facade e
  serviços "logam" sem quebrar as regras 2.2 e 2.3 da guideline. Reutilize na
  consulta em vez de criar um segundo mecanismo.
- **Corpo de requisição opcional no contrato exige `Modelo | None = None` na
  assinatura da rota.** Com o corpo obrigatório, o Pydantic recusa antes do
  error handler e a resposta sai fora do formato `Problem`. Vale para toda rota
  cujo `requestBody` seja `required: false`.
- **Parâmetro de `options` com TIPO errado é 422**, nunca default silencioso
  (exigência explícita da 1.3.0). Chave ausente é que cai no default.
- O tratador de `RagException` alcança exceções levantadas dentro de `Depends`
  (verificado com `OPENAI_API_KEY` ausente → 500 com `Problem`).
- **A suíte NUNCA pode ler o `.env`.** `config.load()` chama `load_dotenv`, que
  preenche variável ausente: um teste que apaga `OPENAI_API_KEY` do ambiente a
  recebe de volta do arquivo e segue para o caminho pago. Aconteceu de verdade
  na task_04 (ingestão real do corpus disparada por um `pytest` sem argumento,
  ~207 mil tokens). A fixture autouse `sem_dotenv` em `tests/conftest.py`
  neutraliza `load_dotenv`; não remova. Sintoma de regressão: a suíte inteira
  passar de ~12 s para minutos.
- **O frontend genérico (`../frontend/`) tem suíte a partir da task_05**: `npm test`
  (vitest + jsdom). Ambiente jsdom é obrigatório — o DOMPurify sem `window`
  devolveria o HTML intacto. `npm run lint` é oxlint; `npm run build` é vite.
- **HTML só entra no DOM do frontend por `src/sanitiza.js`.** Há um único
  `dangerouslySetInnerHTML` no cliente (`src/Trecho.jsx`), sobre o retorno do
  sanitizador. A auditoria da regra é `grep -rn dangerouslySetInnerHTML src/`.
- **Campo novo no frontend é campo com guard `!= null`, no molde da
  `Procedencia`**: ausente não renderiza nada. O markup de um payload 1.2.0 é
  idêntico byte a byte ao anterior à 1.3.0, e isso é verificável comparando
  `renderToStaticMarkup` contra a versão do `git show HEAD:frontend/src/App.jsx`.
- **`data/docstore/` é fonte gratuita de `content_html` real** para exercitar
  cliente ou presenter sem chamar o `/ask` pago.
- **`QueryFacade.retrieve()` é público** (task_06): mede-se a recuperação sem
  gerar. O rag-03 furava o encapsulamento (`facade._retrieval`); aqui não.
- **A medição é anticircular por teste, não por disciplina**: as âncoras saem do
  PDF por `pypdf`, e `tests/test_medicao.py` reabre o PDF pelo caminho
  independente e cobra que cada âncora esteja lá. Nunca use o `unstructured` do
  próprio sistema para descobrir âncora.
- `GET /health` reporta `ok` com os dois armazéns VAZIOS: `degraded` é só para
  incompatibilidade entre eles ou docstore inacessível (seção 5 do FDD). Diverge
  do rag-03. Índice vazio é 409 do `/ask`.

## Shared Learnings

- `sudo` exige senha nesta máquina: nenhuma task consegue instalar pacote apt
  sozinha. Peça ao autor.
- Docker Desktop costuma estar fechado. Suba com
  `cmd.exe /c start "" "C:\Program Files\Docker\Docker\Docker Desktop.exe"` e
  espere ~20 s antes do `docker compose up -d chroma`.
- O compose publica `8002:8000`: a imagem escuta 8000 dentro do container. Nada
  configura a porta interna.

## Open Risks

- **Risco 3 do FDD MEDIDO (task_06), e o diagnóstico mudou de nome:** o gargalo é
  o **ranking**, não a indexação. Perguntas de tabela dão 1/5 com `k=8` e **5/5
  com `k=20`**, sempre resolvidas pelo `content_html` — as tabelas certas estão
  no índice, em 16º a 20º lugar. Causa medida: os nove resumos começam com a
  mesma abertura (`A tabela apresenta...`) e 36 trechos de prosa competem com 9
  resumos em busca densa. Contingência declarada: multi-representação por
  tabela. Números e análise em `docs/operations/README.md`.
- **Risco 3 do FDD confirmado, com número (task_04):** a pergunta-critério do
  guia na forma nua ("Qual foi a receita no 3T24?") NÃO recupera a tabela — ela
  fica em 7º com `k=10`, atrás de dez trechos de texto, e a resposta é recusa.
  Com "receita de vendas ... Petrobras ... em milhões de reais" e `k=8` a tabela
  sobe para 3º e a resposta sai certa. Causa provável: todos os resumos de
  tabela começam com a mesma prosa ("A tabela apresenta dados financeiros da
  empresa..."), e o prefixo comum dilui o sinal. **É trabalho da task_06**
  (medição por classe de alvo); a contingência declarada é multi-representação.
- **Toda execução que gasta API é decisão do autor.** A ingestão real cobra um
  resumo por tabela e uma descrição de visão por figura; o corpus atual custou
  ~207 mil tokens. `reset.py` desfaz a idempotência que protege esse gasto.
- Ambiente destravado desde 02/08: poppler/tesseract instalados (o `hi_res`
  detectou 9 tabelas) e `.env` com chave real presente na raiz.

## Handoffs

- task_03 herda `RagProperties` com `partition_cache_dir`, `docstore_dir`,
  `figures_dir`, `partition_strategy`, `DEFAULT_MAX_CHARACTERS` (1000) e
  `MAX_CONCURRENCY` (5), e o `DocumentUnit` de `rag/domain/models.py` (original
  em `content`, representação em `representation`, ligados por `doc_id`).
  O cálculo do `doc_id` determinístico (ADR-003) ainda não existe: é da task_03.
- `composition.build_ingestion_facade(properties, client, reporter)` é o molde
  para a `build_query_facade`; os armazéns são construídos UMA vez e
  compartilhados entre facade e serviço de gravação.
- **task_05 (frontend) herda o contrato já servido de verdade**: `kind` em todo
  hit, `content_html` apenas com `kind=tabela`, `elements` no relatório,
  `docstore_originals` no `/health` e `features=[ask, ingest, sources]` (sem
  `history`, sem `stream`). Suba com
  `.venv/bin/uvicorn serve:app --host 127.0.0.1 --port 8080`.
- **task_06 (medição) herda o achado do risco 3** acima e o corpus já ingerido;
  o golden set precisa separar "a tabela foi recuperada?" de "a resposta está
  certa?", porque neste corpus os dois divergem por frase da pergunta.
