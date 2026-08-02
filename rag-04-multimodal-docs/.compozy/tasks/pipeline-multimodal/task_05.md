---
status: pending
title: Frontend 1.3.0
type: frontend
complexity: medium
---

# Task 5: Frontend 1.3.0

## Overview

Evolui o frontend genérico da trilha para consumir os campos 1.3.0: a fonte com
`kind=tabela` renderiza a tabela de verdade (HTML sanitizado), cada fonte ganha selo
de tipo e o relatório de ingestão mostra as contagens por elemento. Torna o critério
de sucesso do guia demonstrável na interface, preservando a aditividade com os
projetos 1 a 3.

<critical>
- ALWAYS READ the PRD, the TechSpec, and their catalogs (`_user_stories.md`, `_tests.md`) before starting
- REFERENCE TECHSPEC for implementation details — do not duplicate here
- FOCUS ON "WHAT" — describe what needs to be accomplished, not how
- MINIMIZE CODE — show code only to illustrate current structure or problem areas
- TESTS REQUIRED — implement every test case assigned in ## Tests
</critical>

<requirements>
- MUST renderizar `content_html` como tabela real quando `kind=tabela`, SEMPRE após sanitização (hipótese do FDD: DOMPurify; qualquer alternativa precisa remover script/handlers/atributos perigosos); `dangerouslySetInnerHTML` somente sobre o resultado sanitizado (US-010.AC-1/AC-2).
- MUST exibir selo de `kind` (texto, tabela, imagem) no cabeçalho do hit, no molde exato da `Procedencia`: campo ausente ou desconhecido não renderiza nada e nada quebra (US-010.AC-3/AC-4).
- MUST tratar `kind=tabela` sem `content_html` degradando para o excerpt como texto, sem erro na UI (US-010.EC-3).
- MUST dar rolagem horizontal própria ao contêiner da tabela; a página nunca ganha rolagem lateral (US-010.EC-2).
- MUST exibir as contagens `elements` (textos, tabelas, imagens) no relatório de ingestão apenas quando presentes na resposta; relatórios sem `elements` mantêm as linhas atuais (US-011).
- MUST aplicar a renderização de tabela nos pontos onde a lista de hits existe; como ela está duplicada em `App.jsx` e `Conversa.jsx`, SHOULD extrair um componente compartilhado de trecho para aplicar uma vez só (o rag-04 usa pergunta única, mas o componente é o mesmo para os projetos 2 e 3 no modo conversa).
- MUST manter compatibilidade com os projetos 1 a 3: nenhuma mudança de comportamento quando os campos novos estão ausentes.
- MUST seguir o padrão de código existente do frontend (React + Vite, componentes funcionais, guards `!= null`).
</requirements>

## Subtasks

- [ ] 5.1 Adicionar a dependência de sanitização e o utilitário de sanitização
- [ ] 5.2 Componente de selo de `kind` no molde da `Procedencia`
- [ ] 5.3 Renderização da tabela sanitizada com contêiner de rolagem própria
- [ ] 5.4 Extrair componente compartilhado de trecho e aplicar em `App.jsx` e `Conversa.jsx`
- [ ] 5.5 Contagens `elements` no relatório de ingestão
- [ ] 5.6 Verificação manual de aditividade contra um projeto anterior

## Implementation Details

Diretório: `/home/arthu/code/projetos-rag/frontend/`. Pontos de mudança mapeados:
lista de hits em `src/App.jsx:259-272` e `src/Conversa.jsx:159-179` (excerpt em
`<p className="trecho-texto">`); molde de campo opcional em `src/Procedencia.jsx`
(guards e ausência silenciosa); relatório fixo de 7 linhas em `src/App.jsx:280-289`;
`src/api.js` é transporte puro e não muda. Contrato: `../docs/contracts/rag-api.yaml`
já em 1.3.0 (task_02).

### Relevant Files

- `../frontend/src/App.jsx` — lista de hits e relatório de ingestão
- `../frontend/src/Conversa.jsx` — segunda cópia da lista de hits
- `../frontend/src/Procedencia.jsx` — molde de campo opcional aditivo
- `../docs/contracts/rag-api.yaml` — os campos publicados que esta task consome

### Dependent Files

- `../frontend/package.json` — nova dependência de sanitização
- `../frontend/src/` — novo componente de trecho compartilhado e selo de kind

### Related ADRs

- [adr-001 da sessão: frontend na mesma entrega](adrs/adr-001.md) — a decisão que esta task executa, incluindo a regra de sanitização
- [ADR-004 do projeto](../../../docs/adrs/generated/RAG/ADR-004-contrato-compartilhado-1-3-0.md) — semântica dos campos consumidos

## Deliverables

- Frontend renderizando tabela real, selo de `kind` e `elements`
- Componente de trecho compartilhado (fim da duplicação App/Conversa)
- Compatibilidade com projetos 1 a 3 verificada
- Every test case assigned in `## Tests` implemented and passing **(REQUIRED)**

## Tests

Sem `_tests.md`; casos inline (na infra de teste que o frontend tiver; na ausência de
harness, testes do utilitário de sanitização + verificação manual documentada):

- [ ] T5.1 — Sanitização: entrada com `<script>` e handlers `on*` sai limpa; `<table><tr><td>` sobrevive intacta.
- [ ] T5.2 — Hit `kind=tabela` com `content_html` renderiza elemento `<table>` real; sem `content_html`, cai para o excerpt texto.
- [ ] T5.3 — Hit sem `kind` (payload dos projetos 1 a 3) renderiza exatamente como hoje, sem selo.
- [ ] T5.4 — Relatório sem `elements` não mostra as linhas novas; com `elements`, mostra as três contagens.

## Success Criteria

- Every assigned test case implemented and passing
- Nenhum `dangerouslySetInnerHTML` sobre conteúdo não sanitizado (audite por grep)
- Página sem rolagem horizontal com tabela larga
