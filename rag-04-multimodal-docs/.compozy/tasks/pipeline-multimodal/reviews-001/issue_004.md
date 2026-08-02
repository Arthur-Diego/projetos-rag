---
provider: manual
pr:
round: 1
round_created_at: 2026-08-02T20:17:51Z
status: resolved
file: rag-04-multimodal-docs/rag/api/routes/meta.py
line: 38
severity: medium
author: claude-code
provider_ref:
---

# Issue 004: Docstore inacessivel vira 500 cru em vez de health degraded

## Review Comment

A secao 5 do FDD manda o /health reportar degraded tambem quando o docstore esta inacessivel. synchrony() so compara contagens; se docstore.count() levantar OSError (permissao, disco), a excecao esta fora da hierarquia RagException e sai como 500 sem formato Problem, em vez de 200 degraded com evidencia.

Correcao sugerida: capturar falha de I/O do docstore na rota ou traduzir no repositorio, reportando degraded com degraded_reason.

## Triage

- Decision: `VALID`
- Notes: Confirmado: OSError de docstore.count() escapa da hierarquia RagException e vira 500. Fix: traduzir I/O do docstore em degraded com degraded_reason.
- Resolution: Corrigido: rota /health captura OSError de docstore.count(), responde 200 degraded com degraded_reason e omite docstore_originals. Teste novo em test_health.py (FakeDocstore.fail_on_count).
