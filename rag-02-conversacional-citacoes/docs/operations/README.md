# Runbooks e evidências de validação

Os scripts desta pasta produziram a evidência da seção 9.1 do
[FDD](../domains/rag/features/consulta-ciente-do-historico-fdd.md). Todos gastam
chamadas à API paga: rode com o limite mensal configurado na conta.

Pré-requisitos comuns: `.env` com `OPENAI_API_KEY`, `docker compose up -d qdrant`,
`python ingest.py` já executado, e o venv ativo.

| Arquivo | Critério | O que faz |
|---|---|---|
| `verificar-citacoes.py` | 3 | Faz perguntas, e para cada `[n]` devolvido **abre a página citada no PDF** e procura o trecho. É a conferência manual que o PRD pede, automatizada para poder ser repetida. Resultado em 27/07/2026: 7 de 7. |
| `experimento-reescrita-e-janela.py` | 5 e 6 | Roda a mesma conversa com `conditional_rewrite` ligado e desligado, contando chamadas de LLM; depois varia a janela entre 0, 2 e 20 e imprime a query reescrita de cada uma. |
| `conversa-http.py` | 11 | Três turnos pelo caminho HTTP exato do frontend: guarda a transcrição no cliente e a devolve em `options.history`. Exige `python serve.py` no ar. |
| `troca-de-vector-store.diff` | 7 | O diff da troca Qdrant → Chroma e o resultado dos dois lados. |

## Coleção Postman

```bash
python serve.py &
cd docs/domains/rag/postman
npx newman run *.postman_collection.json -e *.postman_environment.json
```

Dois dos 18 requests (`/ask` com índice vazio e `/ingest` com corpus vazio) exigem
estado de infraestrutura oposto ao dos demais e falham numa rodada normal. Está
documentado no README de lá; os mesmos casos estão cobertos deterministicamente
em `tests/test_api.py`.

## Reconstruir o índice do zero

```bash
docker compose down -v && docker compose up -d qdrant && python ingest.py
```

O índice é derivado e descartável. A fonte de verdade são os PDFs em `pdfs/`.
