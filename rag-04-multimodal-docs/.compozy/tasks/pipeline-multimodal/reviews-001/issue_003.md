---
provider: manual
pr:
round: 1
round_created_at: 2026-08-02T20:17:51Z
status: resolved
file: rag-04-multimodal-docs/rag/api/dependencies.py
line: 41
severity: medium
author: claude-code
provider_ref:
---

# Issue 003: Reload de properties por requisicao nao entrega o que o comentario promete

## Review Comment

provide_properties justifica a reconstrucao por requisicao com o .env pode mudar sem reiniciar o servidor, mas load_dotenv usa override=False (default): apos a primeira carga, edicoes do .env sao ignoradas porque as chaves ja estao em os.environ. O custo por requisicao (releitura + reconstrucao dos objetos, raiz da issue 002) e pago sem beneficio.

Correcao sugerida: ou load_dotenv(..., override=True) para honrar o comentario, ou carregar uma vez e cachear as properties (mais coerente com o desenho de escopo de processo).

## Triage

- Decision: `VALID`
- Notes: Confirmado: load_dotenv default override=False; comentario promete hot-reload que nao existe. Fix: override=True para honrar o contrato do comentario.
- Resolution: Corrigido: load_dotenv(..., override=True) em config.load, com comentario explicando; o reload por requisicao agora entrega o que o docstring de provide_properties promete.
