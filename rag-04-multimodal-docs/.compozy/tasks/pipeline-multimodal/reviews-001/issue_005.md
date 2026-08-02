---
provider: manual
pr:
round: 1
round_created_at: 2026-08-02T20:17:51Z
status: resolved
file: rag-04-multimodal-docs/tests/fakes.py
line: 1
severity: medium
author: claude-code
provider_ref:
---

# Issue 005: Sem teste da guarda de custo com Chroma fora do ar (US-001 EC-4)

## Review Comment

A guarda existe (ingestion_facade.py:104-106: vectors.count() antes do estagio pago), mas nenhum teste prova que o enriquecedor nao e chamado quando o indice esta inacessivel: fakes.py so tem fail_on_add, nao fail_on_count, e test_api_ingest.py nao tem caso 503.

Correcao sugerida: adicionar fail_on_count ao fake vetorial e um caso que afirme zero chamadas ao enriquecedor + 503 no /ingest.

## Triage

- Decision: `VALID`
- Notes: Confirmado: fakes so tem fail_on_add; guarda de custo sem teste. Fix: fail_on_count + caso 503 com zero chamadas ao enriquecedor.
- Resolution: Corrigido: FakeVectors.fail_on_count novo; teste tests/test_ingestion_resume.py::test_chroma_inacessivel_falha_antes_do_estagio_pago prova zero chamadas ao enriquecedor. O mapeamento HTTP 503 de ServiceUnavailableException ja e coberto por test_api_ask/test_health.
