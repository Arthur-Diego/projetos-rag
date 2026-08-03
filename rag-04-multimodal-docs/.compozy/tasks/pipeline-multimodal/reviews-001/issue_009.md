---
provider: manual
pr:
round: 1
round_created_at: 2026-08-02T20:17:51Z
status: resolved
file: rag-04-multimodal-docs/rag/facade/query_facade.py
line: 90
severity: low
author: claude-code
provider_ref:
---

# Issue 009: Caminho de recusa recalcula dense_s por subtracao

## Review Comment

_refusal publica dense_s = search_s - docstore_s embora retrieval.dense_s medido esteja disponivel no chamador; a subtracao embute overhead de loop/log e torna a decomposicao inconsistente com o caminho normal.

Correcao sugerida: passar retrieval.dense_s para _refusal.

## Triage

- Decision: `VALID`
- Notes: Confirmado: dense_s recomputado por subtracao na recusa. Fix: passar retrieval.dense_s.
- Resolution: Corrigido: _refusal recebe retrieval.dense_s medido; subtracao removida.
