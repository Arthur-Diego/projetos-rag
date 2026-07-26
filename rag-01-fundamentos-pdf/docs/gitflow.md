# Gitflow

Projeto de estudo, com um único autor. O fluxo é deliberadamente enxuto — o objetivo é
rastreabilidade do aprendizado, não cerimônia de time.

## Branches

| Branch | Papel |
|---|---|
| `main` | Estado que funciona. Todo commit em `main` roda ponta a ponta. |
| `feat/<slug>` | Uma feature do FDD. Nasce de `main`, volta para `main`. |
| `exp/<slug>` | Experimento de parâmetro (chunk size, top-k, prompt). Pode ser descartado. |

Branches `exp/*` existem porque este projeto **é** experimentação: comparar
`chunk_size=200` contra `4000` é trabalho legítimo que não deve poluir o histórico de
`main` até virar conclusão.

## Commits

Formato convencional, em português:

```
feat(ingest): indexa PDFs do corpus na coleção do Chroma
exp(chunking): mede recall com chunk_size 200/1000/4000
docs(hld): registra a decisão de vector store
```

## Antes do primeiro `git add`

O `.gitignore` já está no lugar e cobre `.env`. **Confira antes de qualquer commit**:

```bash
git status --porcelain | grep -E '\.env$' && echo "PARE: .env prestes a ser commitado"
```

Chave da OpenAI em repositório público é detectada e explorada em minutos (erro nº 9 do
guia).

## Rastreabilidade

Todo `feat/*` referencia o FDD que o originou, no corpo do commit de merge:

```
Ref: docs/domains/rag/features/<feature>-fdd.md
```
