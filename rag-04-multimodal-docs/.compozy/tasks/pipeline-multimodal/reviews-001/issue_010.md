---
provider: manual
pr:
round: 1
round_created_at: 2026-08-02T20:17:51Z
status: resolved
file: frontend/src/sanitiza.js
line: 38
severity: low
author: claude-code
provider_ref:
---

# Issue 010: data-* e aria-* atravessam a allowlist; comentario promete lista fechada

## Review Comment

ALLOW_DATA_ATTR e ALLOW_ARIA_ATTR do DOMPurify valem true por padrao mesmo com ALLOWED_ATTR definido; td data-x aria-label sobrevivem (confirmado empiricamente pelo revisor). Nao e vetor de XSS, mas o comentario (linhas 11-14) afirma que atributo fora da lista fica de fora.

Correcao sugerida: ALLOW_DATA_ATTR: false, decisao explicita sobre ALLOW_ARIA_ATTR (manter por acessibilidade e valido, mas dito no comentario), e caso de teste cravando o comportamento em sanitiza.test.js.

## Triage

- Decision: `VALID`
- Notes: Confirmado empiricamente pelo revisor: data-*/aria-* atravessam. Fix: ALLOW_DATA_ATTR false, aria mantido por acessibilidade e documentado, teste cravando.
- Resolution: Corrigido: ALLOW_DATA_ATTR=false e ALLOW_ARIA_ATTR=true explicitos com comentario decidindo cada um; teste novo em sanitiza.test.js cravando data-* bloqueado e aria-*/colspan mantidos.
