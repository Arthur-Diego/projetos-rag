---
provider: manual
pr:
round: 1
round_created_at: 2026-08-02T20:17:51Z
status: resolved
file: docs/contracts/rag-api.yaml
line: 147
severity: low
author: claude-code
provider_ref:
---

# Issue 013: Exemplos por campo do /health montam juntos uma resposta degraded

## Review Comment

docstore_originals example 58 convive com indexed_chunks example 617; a propria descricao nova diz que divergencia denuncia orfao. Quem compoe a resposta-exemplo a partir dos exemplos por campo obtem um sistema degradado com status ok implicito.

Correcao sugerida: alinhar os dois exemplos ou adicionar um exemplo de resposta completo e coerente.

## Triage

- Decision: `VALID`
- Notes: Confirmado: exemplos 617 vs 58 compoem resposta degraded implicita. Fix: alinhar exemplos.
- Resolution: Corrigido: example de docstore_originals alinhado a indexed_chunks (617) com comentario explicando por que os exemplos por campo devem compor uma resposta consistente.
