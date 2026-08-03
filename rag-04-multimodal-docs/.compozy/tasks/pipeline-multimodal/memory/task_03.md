# Task Memory: task_03.md

Keep only task-local execution context here. Do not duplicate facts that are obvious from the repository, task file, PRD documents, or git history.

## Objective Snapshot

Ingestão multimodal de ponta a ponta entregue: partição com cache, roteamento por
categoria, `doc_id` determinístico, dois repositórios, enriquecimento seletivo,
gravação ordenada, `POST /ingest`, `ingest.py` e script de inspeção.
**Não executado:** a ingestão REAL do corpus (critério "tabelas > 0") — bloqueada
por falta de poppler/tesseract e de `.env` com chave. Ver "Ready for Next Run".

## Important Decisions

- **Roteamento em serviço próprio** (`ElementRoutingService`), não dentro do
  `PartitionService` como a task_01 previa: particionar custa minutos e rotear
  custa microssegundos; juntá-los faria o teste T3.1 depender de um PDF real.
  O docstring de `domain/models.py` foi corrigido para apontar o novo dono.
- **Porta `IngestionLog`** (`service/ingestion_log.py`) implementada pelo
  `ConsoleReporter`. Resolve a tensão entre "só o presenter escreve" (2.3) e "a
  facade não conhece o mundo de fora" (2.2) numa ingestão que leva minutos.
- **Sem `Protocol` no `TableSummaryService`** (ADR-006 rejeita explicitamente). O
  dublê dos testes é um `SimpleChatModel` contador (`tests/fakes.CountingChatModel`),
  o que faz o serviço real rodar com o prompt real. `ImageDescriptionService` É
  `Protocol` (ADR-006).
- **`doc_id` de imagem sai do hash dos BYTES do arquivo**, não do `text` do
  elemento: figura sem OCR tem texto vazio, e hashear isso colapsaria todas as
  figuras num id só.
- **Chave do cache inclui a estratégia** (`<hash>-<hi_res|fast>.json`): um cache
  de `fast` servido ao `hi_res` seria o risco 1 disfarçado de risco 2.
- **Corpo do `POST /ingest` é opcional** (`IngestRequest | None = None`): o yaml
  declara `requestBody.required: false`, e com o corpo obrigatório o Pydantic
  recusa antes do error handler e responde fora do formato `Problem`.
- **`descrever_imagens` com tipo errado é 422**, nunca default silencioso
  (exigência explícita da 1.3.0; o parâmetro controla gasto de visão).
- `PartitionFailedException` mapeada em **422** (`PARTITION_FAILED`): a receita
  (instalar as nativas ou cair para `fast`) é do operador, não defeito do servidor.

## Learnings

- `chunk_by_title` COMBINA seções pequenas até `combine_text_under_n_chars`
  (default = `max_characters`). Fixture de teste com duas frases curtas sai como
  uma unidade só; para provar o corte por título é preciso que cada seção caiba
  na janela e as duas juntas não caibam (~600 caracteres cada, com janela 1000).
- `tests/__init__.py` é obrigatório: sem ele o mypy vê `tests/fakes.py` sob dois
  nomes de módulo e aborta a verificação inteira antes de checar qualquer coisa.
- `batch()` do LangChain exige `list[LanguageModelInput]` anotado; `list[list[HumanMessage]]`
  falha no mypy por invariância de `list`.
- Métodos que recebem listas de subclasses de `Element` precisam de
  `Sequence[Element]` (invariância de `list`).
- O tratador de `RagException` alcança exceções levantadas DENTRO de `Depends`
  (verificado: `OPENAI_API_KEY` ausente → 500 com `Problem`).
- Corpus real com `strategy=fast`: 1170 elementos → 44 unidades de texto em 16
  páginas, `tabelas=0` (esperado — `fast` não detecta tabela). Acerto de cache na
  segunda leitura em 0,04 s.

## Files / Surfaces

- Novos em `rag/`: `domain/identity.py`; `repository/{corpus_reader,pdf_partitioner,
  docstore_repository,vector_repository}.py`; `service/{ingestion_log,partition_service,
  routing_service,table_summary_service,image_description_service,enrichment_service,
  indexing_service,openai_models}.py`; `facade/ingestion_facade.py`;
  `presenter/{console_reporter,json_presenter}.py`; `api/{schemas,error_handlers,
  dependencies}.py` e `api/routes/ingest.py`.
- Preenchidos: `rag/api/app.py`, `composition.py`, `ingest.py`.
- Corrigido: docstring de `rag/domain/models.py` (dono da tradução `Element` →
  `DocumentUnit`).
- Novos fora de `rag/`: `docs/operations/inspeciona-tabelas.py`, `tests/__init__.py`,
  `tests/fakes.py` e cinco arquivos de teste (T3.1 a T3.8 + borda HTTP).

## Errors / Corrections

- Primeira versão do `composition.build_ingestion_facade` construía os dois
  repositórios duas vezes (um par para a facade, outro para o `IndexingService`):
  dois pools de conexão contra o mesmo container. Corrigido para instância única.
- `POST /ingest` sem corpo devolvia o 422 do Pydantic, fora do contrato.
  Encontrado por teste de borda, não por revisão.

## Ready for Next Run

- **Ingestão real pendente, com dois bloqueios independentes:**
  (1) `sudo apt install -y poppler-utils tesseract-ocr tesseract-ocr-por` continua
  sem rodar — sem ele `hi_res` falha e `tabelas` fica em 0;
  (2) não existe `.env` na máquina, então não há chave da OpenAI, e a ingestão
  real gasta dinheiro do autor. Ambos exigem o autor.
  Quando destravar: `.venv/bin/python docs/operations/inspeciona-tabelas.py`
  ANTES de `ingest.py` (valida o risco 1 sem gastar nada).
- A task_04 herda: `VectorRepository` sem `search()` e sem `reset()`, e
  `DocstoreRepository` já com `get()`/`count()` prontos para a resolução de
  originais e para o `/health`. `error_handlers` já mapeia `EmptyIndexException`
  (409), que só passa a ocorrer com o `/ask`.
- `JsonPresenter` e `ConsoleReporter` existem só com os métodos de ingestão.
