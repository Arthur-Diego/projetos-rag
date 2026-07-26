# ADR-009: Camada HTTP segregada, com injeção por container

- **Status:** aceito
- **Data:** 2026-07-25
- **Domínio:** RAG
- **Decisores:** arthu
- **Emenda:** [[ADR-008-api-http-do-contrato-compartilhado]]

## Contexto

O `serve.py` criado pelo ADR-008 tinha cerca de 200 linhas e seis
responsabilidades num arquivo só: descritor de capacidades, schemas de entrada,
configuração de CORS, tratamento de erro, montagem de dependências e as quatro
rotas.

Era o único ponto do projeto ainda monolítico, num repositório com vinte módulos
em camadas. A inconsistência é o argumento principal: uma pessoa que abrisse o
`rag/` esperaria a mesma separação na superfície HTTP e não encontraria.

## Decisão

Segregar a camada HTTP em `rag/api/`, seguindo a estrutura idiomática do FastAPI:

```
rag/api/
├── app.py               fábrica: middleware, error handlers, montagem de rotas
├── dependencies.py      provedores injetáveis
├── descriptor.py        o conteúdo de GET /capabilities
├── error_handlers.py    exceção de domínio -> status HTTP
├── schemas.py           DTOs de entrada
└── routes/
    ├── meta.py          /health e /capabilities
    ├── ask.py           /ask
    └── ingest.py        /ingest
```

`serve.py` fica com 32 linhas: publica `app` e sabe subir um servidor.

`/health` e `/capabilities` compartilham arquivo porque compartilham natureza:
GET sem corpo, sem efeito colateral, nenhum uso de facade. São as rotas de
introspecção.

### A parte polêmica: `Depends` é um container de DI

O ADR-007 estabeleceu que os entrypoints são **composition roots**: montam o
grafo de objetos à mão, com todas as escolhas concretas juntas e à vista. O
argumento era que Python não tem container, e portanto o lugar honesto para a
montagem é um arquivo só.

**Usar `Depends` contraria isso.** O FastAPI resolve as dependências por
anotação de tipo, e a montagem passa a ficar distribuída em provedores, não
concentrada. É, na prática, o modelo do Spring.

A escolha foi deliberada, por três razões:

1. É a forma idiomática do FastAPI. Ignorá-la produziria código que qualquer
   pessoa da comunidade leria como estranho.
2. É o mesmo modelo dos Projetos 8, 9 e 10, em Spring. Praticar aqui reduz o
   atrito lá.
3. O container ganha uma coisa que a montagem manual não tem: **dependências
   compostas que não podem ser esquecidas**. `HealthyProperties` já executou o
   `HealthChecker`; qualquer rota nova que a declare herda a verificação de
   pré-condição sem que ninguém precise lembrar.

**A montagem manual não desapareceu.** Tudo que depende do corpo da requisição
continua explícito dentro da rota: `k` e `chunk_size` chegam em `options`, então
`QueryFacade` e `IngestionFacade` são construídas ali, como nos entrypoints de
CLI. A regra que ficou: **`Depends` para o que é estável, construção explícita
para o que depende da requisição.**

Consequência aceita: o projeto passa a ter dois modelos de injeção convivendo,
manual nas CLIs e por container no HTTP. Isso é confuso se ninguém explicar, e é
por isso que este ADR existe.

## Alternativas consideradas

### Manter `serve.py` monolítico

Rejeitada. Quatro rotas cabem em 200 linhas, mas o arquivo já misturava seis
responsabilidades e cresceria a cada projeto da trilha.

### Segregar sem usar `Depends`, mantendo montagem manual

Rejeitada. Seria coerente com o ADR-007 e produziria rotas que constroem tudo
explicitamente. Descartada porque perderia a garantia do `HealthyProperties`, e
porque nadar contra a corrente do framework em código de estudo ensina o
contrário do que se quer aprender.

### Colocar a camada HTTP fora de `rag/`, em `api/` na raiz

Rejeitada. O ADR-006 estabeleceu que camadas moram dentro do pacote, e a HTTP é
uma camada. Deixá-la fora sugeriria que é outra coisa.

## Consequências

**Positivas**
- `serve.py` com 32 linhas, sem responsabilidade acumulada.
- Rota nova é um arquivo em `routes/` mais uma linha em `app.py`.
- `HealthyProperties` torna impossível esquecer a verificação de pré-condição.
- `create_app()` é fábrica, então um teste pode criar um app isolado.
- Vocabulário alinhado com os Projetos 8 a 10.

**Negativas**
- **Dois modelos de injeção no mesmo repositório**: manual nas CLIs, container
  no HTTP. Precisa ser explicado, e este ADR é a explicação.
- Dez arquivos para as quatro rotas. A razão estrutura/conteúdo, já alta desde o
  ADR-005, subiu de novo.
- `Depends` é mágica de framework: a origem de um objeto deixa de ser rastreável
  lendo o arquivo, e passa a exigir conhecer a convenção.

**Comportamento observável: inalterado.** As quatro rotas foram reexecutadas
após a segregação, incluindo `refused=true` no corpus de controle, `options` com
chave desconhecida ignorada e o 422 de parâmetro inválido.

## Referências

- `docs/contracts/rag-api.yaml`
- `docs/guidelines/arquitetura-em-camadas.md`
- [[ADR-007-camada-de-caso-de-uso]]
- [[ADR-008-api-http-do-contrato-compartilhado]]
