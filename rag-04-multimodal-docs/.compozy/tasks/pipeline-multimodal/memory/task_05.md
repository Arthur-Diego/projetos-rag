# Task Memory: task_05.md

Keep only task-local execution context here. Do not duplicate facts that are obvious from the repository, task file, PRD documents, or git history.

## Objective Snapshot

Frontend genérico (`../frontend/`) passa a consumir os campos 1.3.0: tabela real a
partir de `content_html` sanitizado, selo de `kind`, contagens `elements` no relatório,
e o fim da duplicação da lista de hits entre `App.jsx` e `Conversa.jsx`.

## Important Decisions

- **Sanitização com `dompurify` 3.4.12 e lista de PERMISSÃO** (tags de tabela +
  `colspan/rowspan/scope/headers/abbr`), não lista de bloqueio. `style`, `href`, `src` e
  todo `on*` caem por não estarem na lista.
- **`sanitizaHtml` falha FECHADO**: sem DOM (`DOMPurify.isSupported === false`) devolve
  `""` em vez da entrada. O DOMPurify sem `window` devolveria o HTML intacto, e um
  sanitizador que devolve o que recebeu é pior que nenhum.
- **Sem invólucro no cabeçalho do hit.** A primeira versão agrupava selo + procedência
  num `<span class="trecho-marcas">`; isso acrescentava um `<span>` ao markup de TODO
  hit dos projetos 1 a 3. Trocado por `margin-left: auto` no `.selo-kind`: mesma
  posição visual, markup 1.2.0 byte a byte idêntico ao anterior (provado, ver Learnings).
- **`Relatorio` saiu do `App.jsx` para `src/Relatorio.jsx`** — era função privada e
  intestável; T5.4 exige assertar sobre ela.
- **Harness de teste novo**: `vitest` + `jsdom` (`npm test`), config em `vite.config.js`.
  jsdom não é preferência: o DOMPurify precisa de DOM de verdade. Componentes montam com
  `createRoot` + `act` (React 19), sem `@testing-library` — a pergunta dos testes é se a
  tabela vira ELEMENTO ou tag escapada, e `querySelector` responde isso sozinho.
- Com `content_html` presente, a tabela SUBSTITUI o excerpt (o resumo não aparece junto):
  é a leitura direta do "degrada para o excerpt" da EC-3.

## Learnings

- **Aditividade provada, não argumentada**: teste descartável comparou
  `renderToStaticMarkup` do trecho ANTIGO (extraído de `git show HEAD:frontend/src/App.jsx`,
  linhas 259-272) com o `Trecho` novo, sobre payload 1.2.0 com e sem `provenance` — saída
  idêntica byte a byte. Foi esse diff que denunciou o invólucro `trecho-marcas`.
- **Renderização validada com tabela REAL do corpus** (`data/docstore/2545695...`, a
  Petrobras 3T24): 18 `<tr>`, 9 `<th>`, 153 `<td>`, 0 `<script>`, selo `tabela`, excerpt
  ausente. O docstore é fonte gratuita de `content_html` real — não precisa de `/ask`
  pago para exercitar o frontend.
- `/capabilities` do rag-04 não declara `history`: o frontend cai na `Resposta` de
  pergunta única. A cópia da lista em `Conversa.jsx` continua sem exercício real aqui,
  mas foi migrada para o mesmo componente.
- `oxlint` não conhece `react/no-danger`; um `eslint-disable` para essa regra seria
  comentário morto.

## Files / Surfaces

Todos em `../frontend/` (fora do rag-04, mas no MESMO repositório git do workspace):

- novos: `src/sanitiza.js`, `src/Trecho.jsx`, `src/Relatorio.jsx` + 3 arquivos `*.test.*`
- alterados: `src/App.jsx` (lista de hits → `Trecho`, `Relatorio` extraído),
  `src/Conversa.jsx` (mesma lista), `src/App.css` (selo e `.trecho-tabela` com
  `overflow-x`), `vite.config.js` (bloco `test`), `package.json` (`dompurify`,
  `vitest`, `jsdom`, script `test`), `README.md`
- backend do rag-04 intocado (mypy limpo em 65 arquivos)

## Errors / Corrections

- Nenhuma correção de terceiros. A única reversão foi o invólucro `trecho-marcas`,
  desfeito pelo próprio diff de aditividade.

## Ready for Next Run

- **Pendência declarada: US-010.EC-2 não foi verificada em navegador.** Não há navegador
  headless neste ambiente (sem chromium, sem playwright/puppeteer). A garantia hoje é o
  CSS (`.trecho-tabela { max-width:100%; overflow-x:auto }` dentro de `.app` com
  `max-width:1000px` e `box-sizing:border-box`). Checagem do autor: `npm run dev`, apontar
  para o rag-04 em :8080, perguntar
  "receita de vendas da Petrobras em milhões de reais no 3T24" com `k=8` (a formulação
  que recupera a tabela, risco 3 do FDD) e confirmar que só a tabela rola de lado.
- 5.6 (aditividade contra projeto anterior) foi fechada pelo diff de markup, não
  apontando o frontend para um backend 1 a 3 no ar — subir aquele stack exigiria os
  containers dos projetos anteriores, contra a regra "um serviço por vez".
- task_06 (medição) não depende de nada daqui.
