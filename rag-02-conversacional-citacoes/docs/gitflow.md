# Gitflow

Projeto de estudo, com um único autor, dentro do repositório `projetos-rag`. O fluxo é
deliberadamente enxuto — o objetivo é rastreabilidade do aprendizado, não cerimônia de
time. Mesmo fluxo do `rag-01-fundamentos-pdf`.

## Branches

| Branch | Papel |
|---|---|
| `main` | Estado que funciona. Todo commit em `main` roda ponta a ponta. |
| `feat/<slug>` | Uma feature do FDD. Nasce de `main`, volta para `main`. |
| `exp/<slug>` | Experimento de parâmetro (janela de histórico, condição de reescrita, top-k). Pode ser descartado. |

Branches `exp/*` existem porque este projeto **é** experimentação: medir o custo da
reescrita condicional contra a reescrita sempre-ligada é trabalho legítimo que não deve
poluir o histórico de `main` até virar conclusão.

## Commits

Formato convencional, em português. Como o repositório abriga os dez projetos, o escopo
carrega o número do projeto quando a mudança não é óbvia:

```
feat(rag-02/query): reescreve a pergunta usando o histórico antes de buscar
exp(rag-02/history): mede degradacao da reescrita com janela de 2, 6 e 20 turnos
docs(rag-02/hld): registra a decisao de memoria de conversa
```

## Antes do primeiro `git add`

O `.gitignore` da raiz já cobre `.env`, `.venv/` e `*/pdfs/*`. **Confira antes de
qualquer commit**:

```bash
git status --porcelain | grep -E '\.env$' && echo "PARE: .env prestes a ser commitado"
```

Chave da OpenAI em repositório público é detectada e explorada em minutos (erro nº 9 do
guia).

## Rastreabilidade

Todo `feat/*` referencia o FDD que o originou, no corpo do commit de merge:

```
Ref: rag-02-conversacional-citacoes/docs/domains/rag/features/<feature>-fdd.md
```
