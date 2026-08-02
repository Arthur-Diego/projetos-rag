---
status: completed
title: Consulta, saúde e presenters
type: backend
complexity: high
---

# Task 4: Consulta, saúde e presenters

## Overview

Fecha o lado da leitura: `POST /ask` que busca as representações, resolve os
originais por `doc_id` e entrega ao LLM a tabela HTML íntegra, com recusa por
grounding; mais `/health` com detecção de dessincronia, `/capabilities`, o script
CLI de reset e os presenters que serializam a semântica 1.3.0. É onde o critério de
sucesso do guia se torna verificável.

<critical>
- ALWAYS READ the PRD, the TechSpec, and their catalogs (`_user_stories.md`, `_tests.md`) before starting
- REFERENCE TECHSPEC for implementation details — do not duplicate here
- FOCUS ON "WHAT" — describe what needs to be accomplished, not how
- MINIMIZE CODE — show code only to illustrate current structure or problem areas
- TESTS REQUIRED — implement every test case assigned in ## Tests
</critical>

<requirements>
- MUST implementar `RetrievalService` no padrão do rag-03: valida faixas na construção, `require_index` falha com 409 antes de chamada paga, devolve resultado com métrica por estágio; busca densa top-k no Chroma e resolução dos originais no `DocstoreRepository`.
- MUST descartar hit com `doc_id` órfão com log de warning e seguir com os demais (nunca 500 por hit órfão; decisão da entrevista).
- MUST implementar `PromptBuilder.format_context` entregando o original íntegro por `kind` (texto cru, HTML completo de tabela, descrição de imagem), preservando numeração 1-based, logando o tamanho do contexto e o truncamento por tabela quando houver (nunca silencioso).
- MUST implementar `GenerationService` (Protocol + adaptador OpenAI `gpt-4o-mini`) com instrução de recusa quando o contexto não sustenta; retries com backoff só nas chamadas OpenAI.
- MUST expor `POST /ask` conforme contrato 1.3.0: hits com `kind`, `excerpt` (trecho/resumo/descrição conforme tipo) e `content_html` apenas quando `kind=tabela`; `refused` correto; timings por estágio; status 200/409/422/500/503 conforme a matriz da seção 6.
- MUST implementar `GET /health` reportando Chroma, docstore e dessincronia (contagens incompatíveis → `degraded` com evidência; campo de contagem do docstore conforme o nome publicado na task_02) e `GET /capabilities` com `features=[ask, ingest, sources]` e parâmetros `k` (default 4, 1 a 20) e `descrever_imagens` (boolean, default true, applies_to ingest).
- MUST implementar o script CLI de reset: zera a coleção do Chroma e `data/docstore/` numa operação, preserva `data/partition/`, idempotente.
- MUST implementar `JsonPresenter` com a regra dura do rag-03: campo opcional ausente é OMITIDO, nunca `null`; e `ConsoleReporter` para `ask.py`.
- MUST completar `ask.py` e `serve.py` como entrypoints finos; nenhuma camada chama `sys.exit()` nem escreve em stdout.
</requirements>

## Subtasks

- [x] 4.1 `RetrievalService` com `require_index`, métrica por estágio e descarte de órfão
- [x] 4.2 `PromptBuilder` com originais íntegros por `kind` e log de contexto
- [x] 4.3 `GenerationService` (Protocol + OpenAI) com recusa e retries
- [x] 4.4 `QueryFacade`, `ask.py`, `POST /ask` com semântica 1.3.0
- [x] 4.5 `HealthChecker` com dessincronia e `GET /health`; `GET /capabilities`
- [x] 4.6 Script CLI de reset (dois armazéns, preserva partição)
- [x] 4.7 `JsonPresenter` (omissão de opcionais) e `ConsoleReporter`; `serve.py`
- [x] 4.8 Testes do escopo fixado e validação manual da pergunta-critério

## Implementation Details

Seguir as seções 4 (fluxo de consulta), 5 (contratos 1, 3 e 4) e 6 (erros e
invariantes) do techspec. Moldes do rag-03:
`service/retrieval/retrieval_service.py` (validação na construção, ADR-007 de lá),
`service/prompt_builder.py` (numeração 1-based, `ESCAPE_PHRASE`),
`service/generation_service.py` (Protocol + tradução de falha),
`service/health_checker.py` (checagens separadas, urllib puro),
`presenter/json_presenter.py` (regra da omissão). O diagrama
`sequencia-consulta.mmd` desenha o fluxo completo.

### Relevant Files

- `_techspec.md` seções 4, 5, 6, 7 — fluxo, contratos, erros, observabilidade
- `../rag-03-hybrid-rerank/rag/service/retrieval/retrieval_service.py` — molde central
- `../rag-03-hybrid-rerank/rag/service/prompt_builder.py` — ponto de mudança central (format_context)
- `../rag-03-hybrid-rerank/rag/presenter/json_presenter.py` — regra da omissão de opcionais
- `docs/domains/rag/diagrams/mermaid/sequencia-consulta.mmd` — sequência desenhada

### Dependent Files

- `rag/service/**`, `rag/facade/query_facade.py`, `rag/api/**`, `rag/presenter/**`, `ask.py`, `serve.py`, script de reset — criados/preenchidos aqui
- `docs/domains/rag/postman/pipeline-multimodal.postman_collection.json` — roda contra o serviço desta task

### Related ADRs

- [ADR-001](../../../docs/adrs/generated/RAG/ADR-001-dois-armazens-ligados-por-doc-id.md) — resolução por `doc_id`, docstore fonte de verdade
- [ADR-004](../../../docs/adrs/generated/RAG/ADR-004-contrato-compartilhado-1-3-0.md) — semântica de `kind`/`content_html`/`excerpt`
- [adr-002 da sessão](adrs/adr-002.md) — pergunta única; capabilities sem history/stream
- [adr-003 da sessão](adrs/adr-003.md) — prompt de geração não promete valor exato de gráfico

## Deliverables

- `POST /ask`, `GET /health`, `GET /capabilities` funcionando conforme 1.3.0
- Script de reset e entrypoints completos
- Pergunta-critério respondida com HTML de tabela evidenciado no log
- Every test case assigned in `## Tests` implemented and passing **(REQUIRED)**

## Tests

Sem `_tests.md`; casos inline:

- [x] T4.1 — `format_context`: hit de tabela entra com o HTML do docstore (não o excerpt); hit de texto entra com o texto; numeração 1-based preservada.
- [x] T4.2 — Órfão: hit com `doc_id` inexistente no docstore é descartado com warning e a resposta sai 200 com os demais.
- [x] T4.3 — `require_index`: índice vazio produz 409 antes de qualquer chamada ao gerador (fake conta chamadas).
- [x] T4.4 — Presenter: hit `kind=texto` serializado NÃO contém a chave `content_html`; hit `kind=tabela` contém; nenhum campo `null`.
- [x] T4.5 — Validação de borda: `k=0` e `k=21` produzem 422; `question` vazia produz 422.
- [x] T4.6 — Health: contagens divergentes injetadas produzem `status=degraded` com evidência.
- [x] T4.7 — Reset: após reset com armazéns fake populados, ambos vazios e segunda execução não falha.

## Success Criteria

- Every assigned test case implemented and passing
- Coleção Postman do domínio passa contra o serviço local (meta/, ask/, ingest/ e erros/ provocáveis)
- Recusa comprovada para pergunta do corpus BCB
- mypy limpo
