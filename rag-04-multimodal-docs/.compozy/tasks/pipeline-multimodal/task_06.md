---
status: pending
title: Medição e runbook de operações
type: test
complexity: medium
---

# Task 6: Medição e runbook de operações

## Overview

Entrega a prova de valor do projeto: o golden set separado por classe de alvo
(texto, tabela, imagem), o script de medição no padrão do rag-03 e o runbook de
`docs/operations/`. É o que transforma "parece que funciona" em números
publicáveis, incluindo a pergunta-critério do guia com evidência de HTML no prompt.

<critical>
- ALWAYS READ the PRD, the TechSpec, and their catalogs (`_user_stories.md`, `_tests.md`) before starting
- REFERENCE TECHSPEC for implementation details — do not duplicate here
- FOCUS ON "WHAT" — describe what needs to be accomplished, not how
- MINIMIZE CODE — show code only to illustrate current structure or problem areas
- TESTS REQUIRED — implement every test case assigned in ## Tests
</critical>

<requirements>
- MUST criar `docs/operations/perguntas.json` com o golden set classificado por alvo (`texto`, `tabela`, `imagem`), incluindo a pergunta-critério do guia ("qual foi a receita no 3T24?") e ao menos: 4+ perguntas de tabela, 3+ de texto, 2+ de imagem (qualitativas), mais 2+ de controle negativo (respostas que só existem no PDF do BCB).
- MUST extrair as âncoras de acerto por caminho INDEPENDENTE do pipeline (pypdf ou leitura manual do PDF, nunca o `unstructured` do próprio sistema): regra de anticircularidade herdada do rag-03; âncora é trecho literal, não página.
- MUST implementar o script de medição no padrão `tabela-medicao.py` do rag-03: cabeçalho avisando custo, `argparse` com `--sem-geracao` e `--k`, constrói a facade via composição, reporta acerto de recuperação e taxa de recusa POR CLASSE de alvo, e para perguntas de tabela reporta também se `content_html` chegou no hit (evidência do critério do guia).
- MUST registrar para perguntas de imagem o resultado qualitativo (a resposta reflete a descrição?) sem exigir valor exato (adr-003 da sessão).
- MUST escrever `docs/operations/README.md` no formato do rag-03: pré-requisitos copiáveis, aviso de custo por script, seção de resultados datados com tabela e análise; resultado negativo é resultado válido e publicável.
- SHOULD documentar no README o uso do script de inspeção de tabelas (task_03) e do reset (task_04) como parte do fluxo operacional.
</requirements>

## Subtasks

- [ ] 6.1 Extrair âncoras do PDF por caminho independente (pypdf) e montar `perguntas.json`
- [ ] 6.2 Script de medição com `--sem-geracao`, métricas por classe e evidência de `content_html`
- [ ] 6.3 Rodar a medição real e registrar a primeira rodada datada no README
- [ ] 6.4 README de operations completo (pré-requisitos, custo, inspeção, reset)

## Implementation Details

Molde: `../rag-03-hybrid-rerank/docs/operations/tabela-medicao.py` (242 linhas,
argparse, facade construída N vezes), `perguntas.json` de lá (âncora desceu de
página para trecho; documentado no próprio arquivo) e o `README.md` de operações
(estrutura de resultados datados, duas métricas que se checam: acerto x recusa).
Critério de acerto: âncora literal normalizada contida em algum hit recuperado; para
tabela, buscar a âncora também no `content_html` do hit.

### Relevant Files

- `../rag-03-hybrid-rerank/docs/operations/tabela-medicao.py` — molde do script
- `../rag-03-hybrid-rerank/docs/operations/perguntas.json` — molde do golden set e da regra de âncora
- `../rag-03-hybrid-rerank/docs/operations/README.md` — molde do runbook e do registro de rodadas
- `pdfs/petrobras-desempenho-3t24.pdf` — fonte das âncoras (via pypdf, fora do pipeline)

### Dependent Files

- `docs/operations/perguntas.json`, `docs/operations/tabela-medicao.py` (ou nome análogo), `docs/operations/README.md` — criados aqui

### Related ADRs

- [adr-003 da sessão: evidência de imagem qualitativa](adrs/adr-003.md) — medição por classe separada é exigência desta decisão

## Deliverables

- Golden set anticircular por classe de alvo
- Script de medição reexecutável com modo sem custo de geração
- Primeira rodada de resultados datada e analisada no README
- Every test case assigned in `## Tests` implemented and passing **(REQUIRED)**

## Tests

Sem `_tests.md`; casos inline:

- [ ] T6.1 — `perguntas.json` valida contra a estrutura esperada (toda pergunta tem classe, âncora não vazia para classes factuais, controle negativo marcado).
- [ ] T6.2 — Normalização de âncora: função de normalização casa âncora com variações de caixa/acentuação/espaço (unitário, sem rede).
- [ ] T6.3 — `--sem-geracao` executa a medição de recuperação sem nenhuma chamada ao gerador (fake/flag conta chamadas) e imprime a tabela por classe.

## Success Criteria

- Every assigned test case implemented and passing
- Rodada real registrada: acerto por classe + taxa de recusa + evidência de `content_html` nas perguntas de tabela
- Pergunta-critério do guia medida e documentada
