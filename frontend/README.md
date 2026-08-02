# Cliente RAG — frontend genérico

Um frontend para os dez projetos da trilha. Ele **não conhece nenhum deles**: fala o
contrato em `../docs/contracts/rag-api.yaml` e se adapta ao que o backend declarar.

## Rodar

```bash
# terminal 1 — um backend qualquer que implemente o contrato
cd ../rag-01-fundamentos-pdf
docker compose up -d chroma
source .venv/bin/activate
uvicorn serve:app --port 8080

# terminal 2 — o frontend
cd ../frontend
npm install     # uma vez
npm run dev     # abre em http://localhost:5173
```

O campo **Backend** no topo aponta para qualquer URL. Trocar de projeto é trocar a porta.

## Como ele é genérico

Três mecanismos, e nenhum deles envolve `if projeto === ...`:

**1. Os controles vêm do backend.** `GET /capabilities` devolve um JSON Schema reduzido
dos parâmetros aceitos, com tipo, limites, default e rótulo. `Parametros.jsx` desenha a
partir disso.

```json
"k": { "type":"integer", "label":"Chunks recuperados",
       "default":4, "minimum":1, "maximum":20, "applies_to":["ask"] }
```

O Projeto 3 acrescenta `rerank_top_n`, o Projeto 7 acrescenta `max_hops`. Nenhuma linha
deste repositório muda.

**2. As abas somem sozinhas.** Se `features` não incluir `ingest`, a aba de indexação não
existe. Um backend só de leitura funciona sem alteração.

**3. A recusa é um booleano, não uma string.** O campo `refused` vem do backend, que
compara com a própria frase de escape. Se o frontend comparasse texto, ficaria acoplado
ao idioma e à redação de cada projeto.

**4. Campo novo é campo opcional.** O contrato só cresce de forma aditiva, e cada campo
novo é renderizado sob um guard: `kind` ausente não desenha selo, `content_html` ausente
cai no excerpt como texto, `elements` ausente não acrescenta linha ao relatório. O
markup de um payload 1.2.0 (projetos 1 a 3) é idêntico ao de antes do 1.3.0, byte por
byte.

## HTML de documento nunca entra cru

Desde o 1.3.0, um hit com `kind=tabela` traz a tabela ORIGINAL em `content_html` —
HTML extraído de um PDF de terceiro. Ele passa **sempre** por `sanitiza.js`, e é o
resultado da sanitização, nunca o campo cru, que chega ao único
`dangerouslySetInnerHTML` do cliente (`Trecho.jsx`). A lista lá é de permissão: sobrevive
o que uma tabela precisa, e nada mais. A auditoria da regra é um grep:

```bash
grep -rn dangerouslySetInnerHTML src/     # uma ocorrência, sobre sanitizaHtml
```

## Estrutura

```
src/
├── api.js           única camada que conhece HTTP. Traduz falha em ErroDaApi
├── Parametros.jsx   desenha controles a partir do descritor  ← o desacoplamento
├── App.jsx          estado, abas e exibição de resposta
├── Trecho.jsx       um hit: fonte, selo de kind, procedência, texto ou tabela
├── Relatorio.jsx    relatório de ingestão
├── sanitiza.js      único caminho de HTML para o DOM  ← a regra de segurança
└── App.css          tema claro e escuro
```

`npm test` roda a suíte (vitest + jsdom): sanitização, renderização do trecho e
aditividade do relatório.

**Regra**: se um dia aparecer `if (nome === "k")` em `Parametros.jsx`, o desacoplamento
acabou. Parâmetro novo se resolve no `/capabilities` do backend, nunca aqui.

## O que ele mostra e por quê

A resposta vem acompanhada de **origem, página e distância** de cada trecho, e das
latências de busca e geração separadas. Isso não é enfeite: é o que permite olhar uma
resposta errada e dizer se a falha foi da recuperação ou da geração, que é o objetivo
declarado do Projeto 1.

`distância: menor é mais próximo`. A legenda existe porque a intuição é o contrário.

## Implementar o contrato num projeto novo

Ver `serve.py` do `rag-01-fundamentos-pdf` como referência: quatro rotas, um presenter
JSON e um tradutor de exceção para status HTTP. A lógica de RAG fica nas facades; o
`serve.py` é só superfície.
