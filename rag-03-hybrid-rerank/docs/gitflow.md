# Gitflow

Projeto de estudo, com um único autor, dentro do repositório `projetos-rag`. O fluxo é
deliberadamente enxuto — o objetivo é rastreabilidade do aprendizado, não cerimônia de
time. Mesmo fluxo do `rag-01-fundamentos-pdf` e do `rag-02-conversacional-citacoes`.

## Branches

| Branch | Papel |
|---|---|
| `main` | Estado que funciona. Todo commit em `main` roda ponta a ponta. |
| `feat/<slug>` | Uma feature do FDD. Nasce de `main`, volta para `main`. |
| `exp/<slug>` | Experimento de parâmetro (`k` do RRF, quantidade de candidatos, top_n do rerank). Pode ser descartado. |

Branches `exp/*` importam mais aqui do que nos projetos anteriores. O entregável real
deste projeto é uma **tabela de medição** — 10 perguntas × 3 configurações — e chegar
nela exige variar parâmetros e comparar. Esse trabalho é legítimo e não deve poluir o
histórico de `main` até virar conclusão.

## Commits

Formato convencional, em português. Como o repositório abriga os dez projetos, o escopo
carrega o número do projeto quando a mudança não é óbvia:

```
feat(rag-03/retrieval): funde os rankings denso e BM25 com Reciprocal Rank Fusion
exp(rag-03/rrf): mede o efeito do k do RRF em 20, 60 e 200
docs(rag-03/hld): registra a decisao de busca hibrida com reranking
```

## Antes do primeiro `git add`

O `.gitignore` da raiz já cobre `.env`, `.venv/` e `*/pdfs/*`. **Confira antes de
qualquer commit**:

```bash
git status --porcelain | grep -E '\.env$' && echo "PARE: .env prestes a ser commitado"
```

Chave da OpenAI em repositório público é detectada e explorada em minutos (erro nº 9 do
guia).

Este projeto acrescenta um segundo cuidado: o `sentence-transformers` baixa ~500 MB de
modelo na primeira execução. Confira que o cache dele (`~/.cache/huggingface/`, fora do
repositório por padrão) não foi parar na árvore de trabalho antes de commitar.

## Rastreabilidade

Todo `feat/*` referencia o FDD que o originou, no corpo do commit de merge:

```
Ref: rag-03-hybrid-rerank/docs/domains/rag/features/<feature>-fdd.md
```
