# Task Memory: task_02.md

Keep only task-local execution context here. Do not duplicate facts that are obvious from the repository, task file, PRD documents, or git history.

## Objective Snapshot

Publicar `../docs/contracts/rag-api.yaml` em 1.3.0, aditivo. Entregue.

## Important Decisions

- Nome do campo do docstore no `/health`: **`docstore_originals`** (integer,
  opcional). Era ambiguidade 5 do `divergencias.md`; agora é contrato para a task_04.
- 422 do `/ingest` publicado com dois exemplos nomeados (`faixa` e `tipo`) em vez de
  trocar o exemplo antigo — trocar removeria o caso dos projetos 1 a 3.
- Nota de idempotência entrou como parágrafo aditivo, mantendo o texto destrutivo
  original acima dela: a destrutividade continua sendo o padrão dos outros projetos.
- Erros de lint pré-existentes do yaml (aspas faltando em descrições flow-style,
  `security`/`operationId` ausentes) ficaram fora de escopo — ver Ready for Next Run.

## Learnings

- Validação usada: parse com `yaml.safe_load` + diff estrutural contra
  `git show HEAD:docs/contracts/rag-api.yaml` (required, tipos, rotas, status).
  Lint OpenAPI via `npx @redocly/cli lint` funciona offline-ish e serve de baseline.
- O yaml compartilhado vive **fora** deste repositório git (`../docs/contracts/`):
  o diff dele não aparece no `git status` do rag-04.

## Files / Surfaces

- `../docs/contracts/rag-api.yaml` — 1.3.0 (repo do workspace, não o do rag-04).
- `docs/domains/rag/postman/divergencias.md` — checklist de fechamento no fim.

## Errors / Corrections

- Nenhum.

## Ready for Next Run

- Follow-up 1 (task_04 ou avulso): apertar o teste do `GET /health` na coleção
  Postman, hoje aceita qualquer chave contendo `docstore`; o nome publicado é
  `docstore_originals`.
- Follow-up 2 (fora do escopo desta task): 5 erros `struct` pré-existentes no yaml,
  todos do mesmo bug de aspas — `description: X, Y` em mapa flow vira duas chaves.
  Atinge `ParameterSpec.label/help`, `SearchHit.page`, `Citation.page/excerpt`.
  Corrigir exige tocar campos de outros projetos; não é mudança semântica.
