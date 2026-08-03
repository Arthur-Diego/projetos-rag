---
provider: manual
pr:
round: 1
round_created_at: 2026-08-02T20:17:51Z
status: resolved
file: rag-04-multimodal-docs/tests
line: 1
severity: low
author: claude-code
provider_ref:
---

# Issue 014: Sem regressao automatizada do schema do contrato (T2.1/T2.2)

## Review Comment

Os casos T2.1/T2.2 da task_02 conformam por inspecao, mas nenhum teste parseia ../docs/contracts/rag-api.yaml e crava version 1.3.0, SearchHit.required == [source], IngestionReport.required == [pages, chunks, seconds] e os campos novos opcionais. Sem isso, uma versao futura pode regredir a aditividade em silencio.

Correcao sugerida: teste pequeno (yaml.safe_load) na suite do rag-04 cravando esses pontos.

## Triage

- Decision: `VALID`
- Notes: Confirmado: nenhuma regressao automatizada do schema. Fix: teste yaml.safe_load cravando version/required/campos.
- Resolution: Corrigido: tests/test_contract.py parseia o yaml e crava version 1.3.0, required de SearchHit/IngestionReport/Answer e os campos novos (kind enum, content_html, elements, docstore_originals).
