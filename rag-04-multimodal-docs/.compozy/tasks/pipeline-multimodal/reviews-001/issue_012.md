---
provider: manual
pr:
round: 1
round_created_at: 2026-08-02T20:17:51Z
status: resolved
file: frontend/src/Trecho.test.jsx
line: 115
severity: low
author: claude-code
provider_ref:
---

# Issue 012: Sem caso de teste para kind=texto explicito

## Review Comment

Ha teste para imagem, kind desconhecido e kind ausente, mas nenhum para kind: texto emitido explicitamente - caminho distinto no componente (KINDS_CONHECIDOS o contem; CSS .selo-kind.texto existe).

Correcao sugerida: caso assertando selo texto + excerpt como texto (US-010.AC-3).

## Triage

- Decision: `VALID`
- Notes: Confirmado: caminho kind=texto sem teste. Fix: caso novo.
- Resolution: Corrigido: caso kind=texto explicito adicionado em Trecho.test.jsx (selo texto + excerpt).
