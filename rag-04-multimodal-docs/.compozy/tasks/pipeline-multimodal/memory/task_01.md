# Task Memory: task_01.md

Keep only task-local execution context here. Do not duplicate facts that are obvious from the repository, task file, PRD documents, or git history.

## Objective Snapshot

Terreno executável do rag-04: deps nativas, venv, Chroma 8002, camadas, config,
models, mypy/pytest. Entregue por completo exceto o `apt install` das deps
nativas (bloqueado por senha de sudo).

## Important Decisions

- Config de mypy e pytest num `pyproject.toml` (o rag-03 não tinha arquivo de
  config e dependia das flags na linha de comando). Ambos rodam sem argumento.
- Entrypoints `ingest.py`/`ask.py` são stubs que escrevem em stderr e devolvem 1.
  Não fingem sucesso. `serve.py` é real: publica um app sem rota.
- `composition.py` já traz `build_chroma_client` e `build_docstore`; as fábricas
  das facades entram com elas (tasks 03/04).
- `RagProperties.__post_init__` valida `partition_strategy` e faixa da porta —
  um typo em `PARTITION_STRATEGY` cairia silenciosamente na contingência `fast`.
- `collection = "relatorios"` (o contrato publica o campo `collection` em
  `/health` desde a 1.0.0; o valor é escolha deste projeto).

## Learnings

- `sudo` nesta máquina exige senha; sessão não interativa não instala apt.
- Docker Desktop estava fechado; subiu via
  `cmd.exe /c start "" "C:\Program Files\Docker\Docker\Docker Desktop.exe"`,
  pronto em ~20 s.
- `docker-compose.yml` mapeia `8002:8000` — a imagem escuta 8000 dentro do
  container; só a publicação muda. O healthcheck interno testa 8000, não 8002.
- `strategy="fast"` particiona o corpus em ~8 s sem poppler/tesseract; serve de
  smoke test barato dentro do pytest.

## Files / Surfaces

Criados: `requirements.txt`, `docker-compose.yml`, `.env.example`,
`pyproject.toml`, `composition.py`, `ingest.py`, `ask.py`, `serve.py`,
`rag/{__init__,exceptions,config}.py`, `rag/domain/models.py`, `__init__.py` de
`api/facade/service/repository/presenter`, `rag/api/app.py`,
`tests/{conftest,test_config,test_smoke_partition}.py`.
Editados: `CLAUDE.md` e `AGENTS.md` (seção `## Setup` + estado).

## Errors / Corrections

- Nenhum erro de implementação. `mypy` reclamaria de `**overrides: object` em
  `config.load`; assinatura é `**overrides: Any`, como no molde do rag-03.

## Ready for Next Run

- **Pendência bloqueante:** rodar
  `sudo apt install -y poppler-utils tesseract-ocr tesseract-ocr-por` e conferir
  com `pdftoppm -v && tesseract --list-langs | grep por`. Enquanto isso não
  rodar, a task_03 tem que usar `PARTITION_STRATEGY=fast` — e `fast` não detecta
  tabela, ou seja, o objeto de estudo do projeto fica inacessível.
- `data/docstore/` já existe (criado por `build_docstore`); `data/partition/` e
  `data/figures/` são criados pelo `PartitionService` na task_03.
