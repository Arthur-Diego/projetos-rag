# Gitflow

Projeto de estudo, com um único autor, dentro do repositório `projetos-rag`. O fluxo é
deliberadamente enxuto — o objetivo é rastreabilidade do aprendizado, não cerimônia de
time. Mesmo fluxo dos projetos 1 a 3.

## Branches

| Branch | Papel |
|---|---|
| `main` | Estado que funciona. Todo commit em `main` roda ponta a ponta. |
| `feat/<slug>` | Uma feature do FDD. Nasce de `main`, volta para `main`. |
| `exp/<slug>` | Experimento de parâmetro (estratégia do `unstructured`, prompt de resumo, o que indexar por elemento). Pode ser descartado. |

## Commits

Formato convencional, em português. Como o repositório abriga os dez projetos, o escopo
carrega o número do projeto quando a mudança não é óbvia:

```
feat(rag-04/ingestao): particiona o PDF com unstructured hi_res e separa tabelas de texto
exp(rag-04/resumo): compara resumo descritivo com perguntas hipoteticas na indexacao
docs(rag-04/hld): registra a decisao do multi-vector retriever
```

## Antes do primeiro `git add`

O `.gitignore` da raiz já cobre `.env`, `.venv/`, `*/pdfs/*` e `data/` — este último
importa mais aqui do que nos anteriores: as figuras extraídas pelo `unstructured` vão
para `data/figures/` e não entram no repositório. **Confira antes de qualquer commit**:

```bash
git status --porcelain | grep -E '\.env$' && echo "PARE: .env prestes a ser commitado"
```

Chave da OpenAI em repositório público é detectada e explorada em minutos (erro nº 9 do
guia).

Cuidado específico deste projeto: o `unstructured` com `strategy="hi_res"` baixa modelos
de layout pesados na primeira execução. O cache fica fora do repositório por padrão
(`~/.cache/`); confira que nada dele foi parar na árvore de trabalho antes de commitar.

## Rastreabilidade

Todo `feat/*` referencia o FDD que o originou, no corpo do commit de merge:

```
Ref: rag-04-multimodal-docs/docs/domains/rag/features/<feature>-fdd.md
```
