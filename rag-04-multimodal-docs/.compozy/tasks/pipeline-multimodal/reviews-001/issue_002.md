---
provider: manual
pr:
round: 1
round_created_at: 2026-08-02T20:17:51Z
status: resolved
file: rag-04-multimodal-docs/rag/api/dependencies.py
line: 87
severity: high
author: claude-code
provider_ref:
---

# Issue 002: Clientes OpenAI e LocalFileStore construidos por requisicao

## Review Comment

O invariante de escopo de processo (licao do rag-03 registrada no HLD e no proprio arquivo) vale para todos os clientes estaveis, mas so o Chroma ganhou cache (_CLIENTS, linhas 71-84). provide_vectors (87), provide_docstore (99) e provide_generation (110) reconstroem OpenAIEmbeddings, LocalFileStore e ChatOpenAI a cada requisicao - cada um instancia cliente httpx com pool proprio que morre no fim do request, sem reuso de conexao TLS. Um POST /ask cria dois clientes OpenAI descartaveis.

Correcao sugerida: cachear por chave derivada das properties (mesmo molde de _CLIENTS) os tres provedores; o docstring do modulo ja declara container para o estavel.

## Triage

- Decision: `VALID`
- Notes: Confirmado por leitura direta: so o Chroma tem cache _CLIENTS; embeddings/chat/docstore reconstruidos por request. Fix: caches de processo chaveados pelas properties.
- Resolution: Corrigido: caches de processo _EMBEDDINGS/_CHAT_MODELS/_STORES em dependencies.py, chaveados pelas properties; provide_vectors/docstore/generation e a rota /ingest usam embeddings_for/chat_model_for/_store.
