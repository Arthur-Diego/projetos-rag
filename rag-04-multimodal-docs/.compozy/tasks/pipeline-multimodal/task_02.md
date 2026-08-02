---
status: pending
title: Contrato compartilhado 1.3.0
type: docs
complexity: low
---

# Task 2: Contrato compartilhado 1.3.0

## Overview

Publica a evolução aditiva 1.2.0 → 1.3.0 do contrato HTTP compartilhado da trilha,
criando os campos que o pipeline multimodal precisa (`SearchHit.kind`,
`SearchHit.content_html`, `IngestionReport.elements`) antes de qualquer consumidor
implementá-los. É o gate contracts-fit: o backend (task_03/04) e o frontend (task_05)
só podem implementar o que este yaml publicar.

<critical>
- ALWAYS READ the PRD, the TechSpec, and their catalogs (`_user_stories.md`, `_tests.md`) before starting
- REFERENCE TECHSPEC for implementation details — do not duplicate here
- FOCUS ON "WHAT" — describe what needs to be accomplished, not how
- MINIMIZE CODE — show code only to illustrate current structure or problem areas
- TESTS REQUIRED — implement every test case assigned in ## Tests
</critical>

<requirements>
- MUST editar `/home/arthu/code/projetos-rag/docs/contracts/rag-api.yaml`: `info.version` para `1.3.0` e changelog na descrição seguindo o padrão das versões anteriores.
- MUST adicionar em `SearchHit` os campos opcionais `kind` (string, enum `[texto, tabela, imagem]`) e `content_html` (string), com descrições que fixem a semântica do ADR-004: `content_html` presente apenas quando `kind=tabela`; com `kind=tabela` o `excerpt` carrega o resumo; com `kind=imagem`, a descrição; HTML nunca dentro de `excerpt`.
- MUST adicionar em `IngestionReport` o campo opcional `elements` (objeto com `textos`, `tabelas`, `imagens`, inteiros; zero explícito, não ausente, quando a categoria não ocorre).
- MUST acrescentar na descrição do `POST /ingest` a nota aditiva: projetos com ingestão idempotente reconciliam em vez de recriar o índice (decisão da entrevista de FDD; o comportamento destrutivo continua válido para os projetos anteriores).
- MUST resolver as duas ambiguidades registradas em `rag-04-multimodal-docs/docs/domains/rag/postman/divergencias.md`: (a) nomear o campo informativo de contagem do docstore no `/health` (campo opcional novo, ex.: `docstore_originals`, integer) e (b) garantir que o exemplo de 422 do `/ingest` cubra parâmetro de tipo errado (ex.: `descrever_imagens` não booleano).
- MUST manter a evolução estritamente aditiva: nenhum campo sai de `required`, nenhum obrigatório muda de tipo; `required` de `SearchHit` continua `[source]`.
- MUST validar o yaml (parser OpenAPI ou ao menos parse YAML limpo) após a edição.
- SHOULD atualizar `rag-04-multimodal-docs/docs/domains/rag/postman/divergencias.md` marcando o checklist como resolvido.
</requirements>

## Subtasks

- [ ] 2.1 Bump de versão e changelog no cabeçalho do yaml
- [ ] 2.2 Campos `kind` e `content_html` no `SearchHit` com semântica completa
- [ ] 2.3 Campo `elements` no `IngestionReport`
- [ ] 2.4 Nota de idempotência na descrição do `POST /ingest`
- [ ] 2.5 Campo de contagem do docstore no `/health` e exemplo de 422 do `/ingest`
- [ ] 2.6 Validar o yaml e atualizar `divergencias.md`

## Implementation Details

Arquivo único: `../docs/contracts/rag-api.yaml` (workspace, fora do diretório do
projeto). Seguir o estilo editorial do próprio yaml (descrições em pt-BR, changelog
por versão, precedente de relaxamento documentado nas linhas 45-53). O delta exato
está na seção 5 do techspec e no ADR-004 do projeto.

### Relevant Files

- `../docs/contracts/rag-api.yaml` — o contrato a evoluir (SearchHit linhas ~305-343; IngestionReport ~518-528)
- `docs/adrs/generated/RAG/ADR-004-contrato-compartilhado-1-3-0.md` — nomes e semântica decididos
- `docs/domains/rag/postman/divergencias.md` — checklist das divergências a fechar

### Dependent Files

- `docs/domains/rag/postman/pipeline-multimodal.postman_collection.json` — os testes da coleção validam contra o schema publicado
- `../frontend/src/` — consumidor da 1.3.0 (task_05)

### Related ADRs

- [ADR-004 do projeto: contrato compartilhado 1.3.0](../../../docs/adrs/generated/RAG/ADR-004-contrato-compartilhado-1-3-0.md) — a decisão que esta task executa

## Deliverables

- `rag-api.yaml` publicado em 1.3.0, aditivo, com changelog
- `divergencias.md` com o checklist fechado
- Every test case assigned in `## Tests` implemented and passing **(REQUIRED)**

## Tests

Sem `_tests.md`; casos inline (verificação de schema, sem serviço):

- [ ] T2.1 — O yaml parseia sem erro e `info.version == 1.3.0`; `SearchHit.required` continua exatamente `[source]` e `IngestionReport.required` continua `[pages, chunks, seconds]`.
- [ ] T2.2 — Os campos `kind`, `content_html` e `elements` existem como opcionais com os enums/tipos do ADR-004.

## Success Criteria

- Every assigned test case implemented and passing
- Nenhuma mudança em campos obrigatórios (diff do yaml audita isso)
- Divergências MÉDIAS da coleção Postman zeradas no papel
