---
provider: manual
pr:
round: 1
round_created_at: 2026-08-02T20:17:51Z
status: resolved
file: rag-04-multimodal-docs/rag/service/routing_service.py
line: 158
severity: low
author: claude-code
provider_ref:
---

# Issue 008: Fallback sem text_as_html publica texto plano em content_html

## Review Comment

Quando o Table Transformer nao devolve text_as_html, content = table.text (fallback documentado), mas esse texto plano depois viaja no campo content_html do hit (retrieval_service.py:154), que o contrato 1.3.0 define como o HTML original. O frontend renderizaria sopa de numeros como tabela.

Correcao sugerida: marcar a unidade sem HTML estrutural e omitir content_html nesse caso, deixando o hit degradar para excerpt como o contrato ja preve (mesmo caminho do frontend EC-3).

## Triage

- Decision: `VALID`
- Notes: Confirmado: fallback table.text viaja em content_html. Fix: flag de HTML estrutural na unidade; content_html omitido quando nao ha HTML.
- Resolution: Corrigido: campo content_is_html no DocumentUnit (default True; False no fallback sem text_as_html), persistido no docstore (releitura compat com registros antigos) e exigido pelo retrieval para publicar content_html. Testes novos em test_routing.py e test_retrieval.py.
