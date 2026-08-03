---
provider: manual
pr:
round: 1
round_created_at: 2026-08-02T20:17:51Z
status: resolved
file: rag-04-multimodal-docs/docs/operations/inspeciona-tabelas.py
line: 1
severity: medium
author: claude-code
provider_ref:
---

# Issue 006: Script de inspecao sem nenhum teste (criterio da secao 9)

## Review Comment

O script e criterio de aceite da secao 9 (lista tabelas com pagina e preview, sem chamada de API) e mitigacao do risco 1, mas nao tem um unico teste; a evidencia e narrativa (README de operations). A marcacao de tabela suspeita (HTML sem td) tambem esta sem verificacao.

Correcao sugerida: teste que roda o script sobre um cache de particao sintetico (fixture pequena) e afirma contagem, paginas e marcacao de suspeita, alem de zero chamadas de rede.

## Triage

- Decision: `VALID`
- Notes: Confirmado: script e criterio da secao 9 sem teste. Fix: teste com cache de particao sintetico.
- Resolution: Corrigido: tests/test_inspeciona_tabelas.py roda o script contra cache sintetico (import por caminho, config.load monkeypatched) e afirma contagem, paginas, marcacao SUSPEITA e custo zero.
