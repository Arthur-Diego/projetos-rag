---
status: pending
title: Pipeline de ingestão de ponta a ponta
type: backend
complexity: high
---

# Task 3: Pipeline de ingestão de ponta a ponta

## Overview

Entrega a ingestão multimodal completa: partição `hi_res` com cache, roteamento por
categoria com `chunk_by_title`, `doc_id` determinístico, os dois repositórios
(docstore e vetorial), o enriquecimento pago seletivo e o `POST /ingest` com o
relatório `elements` — mais o script de inspeção que valida a detecção de tabelas
antes de qualquer gasto (risco 1). É o coração do projeto: o que não for indexado
aqui não existe para a consulta.

<critical>
- ALWAYS READ the PRD, the TechSpec, and their catalogs (`_user_stories.md`, `_tests.md`) before starting
- REFERENCE TECHSPEC for implementation details — do not duplicate here
- FOCUS ON "WHAT" — describe what needs to be accomplished, not how
- MINIMIZE CODE — show code only to illustrate current structure or problem areas
- TESTS REQUIRED — implement every test case assigned in ## Tests
</critical>

<requirements>
- MUST implementar `PartitionService` (fluxo da seção 4 do techspec): hash do PDF, cache em `data/partition/` chaveado por hash de conteúdo (acerto em segundos, descarte de cache corrompido com log), `hi_res` com `infer_table_structure=True` e extração de imagens para `data/figures/`; seleção de arquivos por glob `pdfs/*.pdf` sem recursão.
- MUST rotear por categoria: narrativo agrupado com `chunk_by_title` (~1000 caracteres); cada `Table` vira unidade própria com HTML; cada `Image` vira unidade própria com caminho do arquivo. Tabelas e imagens nunca entram no agrupamento.
- MUST calcular `doc_id` determinístico por hash de conteúdo + origem + tipo, com serialização estável antes do hash (ADR-003); nomes de arquivo derivados do `doc_id`.
- MUST implementar `DocstoreRepository` (`LocalFileStore` em `data/docstore/` atrás de `BaseStore`, ADR-001) e `VectorRepository` (Chroma via HttpClient na 8002, metadados `doc_id`, `kind`, `page`, `source`), ambos atrás de interfaces no molde do rag-03 (nenhum vocabulário do motor atravessa a camada).
- MUST implementar o enriquecimento seletivo (ADR-002): `TableSummaryService` (prompt do guia: entidades, métricas, período, nomes de coluna) e `ImageDescriptionService` atrás de `Protocol` (ADR-006; adaptador OpenAI visão, base64 em `image_url`, prompt qualitativo com ressalva de precisão), em lote com `max_concurrency=5`, apenas para unidades cujo `doc_id` não existe no docstore.
- MUST gravar na ordem: original no docstore primeiro, representação no Chroma depois (invariante do risco 4).
- MUST expor `POST /ingest` conforme o contrato 1.3.0 (task_02): aceita `options.descrever_imagens` (boolean, default true), responde `IngestionReport` com `pages`, `chunks`, `seconds` e `elements` (zeros explícitos); status 422/500/503 conforme a matriz de erros da seção 6.
- MUST implementar `ingest.py` (entrypoint fino) e `IngestionFacade` sem lógica própria; clientes com escopo de processo criados na composição.
- MUST implementar o script de inspeção pós-partição (contagem e preview das tabelas HTML por página, sem chamada de API) em `docs/operations/`.
- MUST logar por estágio: elementos por categoria e página, acerto de cache, `doc_id`s pulados por idempotência, contagens de resumos/descrições, vetores e originais gravados, tokens gastos.
- MUST manter idempotência de custo: reingestão do corpus inalterado gera zero chamadas de enriquecimento e zero embeddings novos (log `novos=0, reaproveitados=N`).
- SHOULD respeitar a contingência `strategy=fast` via env (risco 2/3), declarada no log quando ativa.
</requirements>

## Subtasks

- [ ] 3.1 `PartitionService` com cache por hash e descarte de cache corrompido
- [ ] 3.2 Roteamento por categoria com `chunk_by_title` e unidades próprias para tabela/imagem
- [ ] 3.3 `doc_id` determinístico no domínio, com serialização estável
- [ ] 3.4 `DocstoreRepository` e `VectorRepository` atrás de interfaces
- [ ] 3.5 `TableSummaryService` e `ImageDescriptionService` (Protocol + adaptador OpenAI)
- [ ] 3.6 `IngestionFacade`, `ingest.py`, `POST /ingest` com `elements` e idempotência
- [ ] 3.7 Script de inspeção de tabelas em `docs/operations/` (sem custo)
- [ ] 3.8 Logs estruturados por estágio e testes do escopo fixado

## Implementation Details

Seguir a seção 4 do techspec (fluxo de ingestão) e a seção 6 (matriz de erros e
invariantes). Moldes do rag-03: `repository/vector_repository.py` (Protocol de
repositório, tri-estado de índice ausente), `service/` (services que orquestram sem
calcular), `api/app.py` e `api/dependencies.py` (montagem HTTP separada da
composição). A rota `/ingest` só implementa o que o yaml 1.3.0 publica (task_02);
divergência descoberta aqui volta para reconciliação, nunca vira rota fora do
contrato.

### Relevant Files

- `_techspec.md` seções 4, 5 (contrato 2), 6 — fluxo, contrato e erros
- `../rag-03-hybrid-rerank/rag/repository/vector_repository.py` — padrão de Protocol e conversão de similaridade
- `../rag-03-hybrid-rerank/rag/api/` — molde de rotas, dependencies e descriptor
- `docs/domains/rag/diagrams/mermaid/ingestao.mmd` — o fluxo desenhado
- `docs/guidelines/README.md` — escopo de testes: roteamento por categoria e correspondência resumo/original por `doc_id`

### Dependent Files

- `rag/**`, `composition.py`, `ingest.py` — criados/preenchidos aqui
- `data/partition/`, `data/docstore/`, `data/figures/` — criados em runtime, fora do git

### Related ADRs

- [ADR-001](../../../docs/adrs/generated/RAG/ADR-001-dois-armazens-ligados-por-doc-id.md), [ADR-002](../../../docs/adrs/generated/RAG/ADR-002-multi-vector-seletivo.md), [ADR-003](../../../docs/adrs/generated/RAG/ADR-003-doc-id-deterministico.md), [ADR-005](../../../docs/adrs/generated/RAG/ADR-005-cache-da-particao-bruta.md), [ADR-006](../../../docs/adrs/generated/RAG/ADR-006-descritor-de-imagens-atras-de-protocol.md) — todos executados nesta task

## Deliverables

- Ingestão completa funcionando: `ingest.py` e `POST /ingest` com relatório `elements`
- Script de inspeção de tabelas rodando sem API
- Corpus Petrobras ingerido nos dois armazéns, ligado por `doc_id`
- Every test case assigned in `## Tests` implemented and passing **(REQUIRED)**

## Tests

Sem `_tests.md`; casos inline (pytest, escopo fixado nas guidelines — unitários sem
rede; os de integração com Chroma local quando disponível):

- [ ] T3.1 — Roteamento: lista sintética de elementos (narrativos, `Table`, `Image`) produz unidades com `kind` correto; tabela e imagem nunca agrupadas; narrativo agrupado por título.
- [ ] T3.2 — `doc_id`: mesmo conteúdo produz o mesmo id em duas chamadas; conteúdos diferentes produzem ids diferentes; id não contém caracteres de caminho perigosos.
- [ ] T3.3 — Correspondência: após indexar unidade sintética, a representação no vetorial e o original no docstore compartilham o `doc_id` e o `kind`.
- [ ] T3.4 — Idempotência: indexar a mesma unidade duas vezes não duplica no docstore nem dispara segundo enriquecimento (enriquecedor fake conta chamadas).
- [ ] T3.5 — Cache: partição com cache válido não invoca o particionador (fake conta chamadas); cache corrompido é descartado e refeito.
- [ ] T3.6 — Glob: arquivos em `pdfs/fora-do-corpus/` nunca entram na seleção.
- [ ] T3.7 — Ordem de gravação: falha injetada na gravação vetorial deixa o original no docstore (nunca o inverso).
- [ ] T3.8 — Relatório: ingestão sintética devolve `elements` com zeros explícitos quando a categoria não ocorre.

## Success Criteria

- Every assigned test case implemented and passing
- Ingestão real do corpus conclui com `tabelas > 0` no relatório (ou denuncia `tabelas: 0` como sinal do risco 1)
- Reingestão imediata reporta `novos=0` e não gasta API
- mypy limpo; grafo de camadas descendente
