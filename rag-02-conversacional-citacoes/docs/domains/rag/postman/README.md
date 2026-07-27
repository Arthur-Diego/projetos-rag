# Coleção HTTP — consulta ciente do histórico com citação resolvida

Gerada em **2026-07-27**, a partir do commit **`030bd87`** (`feat: projeto 1 de RAG,
contrato compartilhado e frontend generico`).

Origem: `docs/domains/rag/features/consulta-ciente-do-historico-fdd.md`, seção 5
(contratos públicos), seção 4 (ordem e encadeamento dos requests), seção 6 (matriz de
erros) e seção 9 (critérios de aceite).

Contrato cruzado: `../../../../../docs/contracts/rag-api.yaml`, versão 1.1.0. As
divergências encontradas estão em `divergencias.md`, **uma delas de severidade ALTA**.

Arquivos:

| Arquivo | O que é |
|---|---|
| `consulta-ciente-do-historico.postman_collection.json` | 18 requests em 4 pastas: `meta/` (2), `ask/` (8), `ingest/` (1), `erros/` (7) |
| `consulta-ciente-do-historico.postman_environment.json` | `baseUrl`, `accessToken` (não usado), `qdrantUrl` |
| `divergencias.md` | FDD × `rag-api.yaml` |

## Estado: o serviço ainda não existe

Este repositório é greenfield — zero código Python em 2026-07-27. A coleção **não foi
executada** e não podia ser: não há nada escutando em `http://localhost:8080`, e o
`newman` não está instalado (`command -v newman` não devolve nada). Nada foi instalado.

Ela é o artefato executável do **critério de aceite 10 da seção 9** ("a coleção Postman
roda contra o serviço no ar"), a ser rodado depois da **etapa 11 do build order** (camada
HTTP: `rag/api/`, `serve.py`).

## Como importar

Postman: *Import* → arraste os dois arquivos → selecione o environment **rag-02 local** no
canto superior direito. Insomnia e Bruno importam o mesmo formato v2.1.

## `accessToken`

**Não precisa preencher.** Nenhuma rota desta feature é autenticada: o `rag-api.yaml`
1.1.0 não declara `securitySchemes` e a seção 5 do FDD não cita header de autorização. A
variável existe no environment só como espaço reservado, e a coleção não a envia em lugar
nenhum. Se um dia a API ganhar autenticação, ligue o `auth: bearer` na coleção.

O que **precisa** estar configurado é o ambiente do serviço, não da coleção:

1. `OPENAI_API_KEY` no `.env`, com limite de gasto mensal na conta (seção 8, linha 466).
   Ela nunca entra neste diretório.
2. Qdrant no ar: `docker compose up -d qdrant` (painel em `http://localhost:6333/dashboard`).
3. Corpus normativo em `pdfs/` e corpus de controle em `pdfs/fora-do-corpus/` — hoje ambos
   só têm `.gitkeep` (pré-requisitos bloqueantes 1 e 2 da seção 8).

## Como rodar

```bash
newman run docs/domains/rag/postman/consulta-ciente-do-historico.postman_collection.json \
  -e docs/domains/rag/postman/consulta-ciente-do-historico.postman_environment.json \
  --reporters cli --suppress-exit-code
```

`newman` não está instalado neste ambiente. Instale-o quando for validar
(`npm i -g newman`), ou rode pelo Runner do Postman — a coleção é o mesmo artefato.

### Ordem, e por que ela importa

O fluxo principal da seção 4 é encadeado: **`ask/` na ordem em que está**. O turno 1
grava a própria resposta na variável de coleção `respostaTurno1`, e os turnos 2 e 3 a
devolvem em `options.history` — que é como o ADR-002 funciona: o backend não guarda
conversa, o cliente é dono dela. Rodar o turno 2 isolado ainda funciona, com o valor de
exemplo do FDD como default.

Rode `ingest/` antes de `ask/`: `POST /ingest` é caro e destrutivo, recria a coleção.

**Três requests de `erros/` exigem estado oposto ao dos demais e devem ser rodados
isolados, não no fluxo completo:**

- `POST /ask — indice vazio (409)`: precisa do índice vazio (`docker compose down -v`,
  sem ingestão). Com o índice populado devolve 200 e o teste falha.
- `POST /ingest — corpus vazio (422)`: precisa de `pdfs/` sem nenhum PDF na raiz — que é
  o estado de hoje, então é o mais fácil de validar cedo.
- Os demais 422 são deterministas e podem rodar em qualquer momento.

Os requests de `ask/` **gastam chamada paga de LLM**: cada um é 1 ou 2 chamadas à OpenAI,
conforme o `reason`. A matriz de recusa completa do critério 4 é pytest com `FakeLLM` e
`FakeVectorRepository`, sem chamada paga — não é esta coleção.

## O que os testes afirmam

Além do status code, cada request confere as invariantes da seção 6 do FDD:

| Invariante | Onde é afirmada |
|---|---|
| 1. `refused == true` implica `citations == []` | em toda resposta 200 de `/ask`; explicitamente nos dois requests de recusa |
| 2. `rewritten_question` presente em toda resposta de `/ask` | em todos os requests de `ask/` |
| 3. `timings.rewrite_s == 0.0` se e somente se `reason` for `primeiro_turno` ou `pergunta_autossuficiente` | turno 1 (`== 0`), turno 2 e turno 3 (`> 0`), pergunta autossuficiente (`== 0`), `history_window 0` (bicondicional completa) |
| 4. Todo rótulo `[n]` do texto está em `citations` ou em `meta.unresolved_labels` | turnos 1 e 2 |
| 5. `hits` não é reordenado entre a numeração e a resolução | **não verificável por HTTP** — pytest (seção 10, linha 531) |
| 6. `pdfs/fora-do-corpus/` nunca é alcançado pelo glob | **não verificável por HTTP** — `grep`, seção 9 item 8 |
| 7. Nenhuma camada abaixo do entrypoint escreve em stdout ou chama `sys.exit()` | **não verificável por HTTP** — `grep`, seção 9 item 8 |

Mais: `reason` sempre conferido contra o conjunto fechado de seis valores da seção 5;
`text` da recusa comparado **literalmente** com a `ESCAPE_PHRASE` do contrato 8; os cinco
parâmetros e seus limites conferidos em `/capabilities`; `features` contendo `history`,
que é o gatilho da interface de conversa no frontend genérico.

## Casos da seção 6 não cobertos por HTTP

Estas linhas da matriz de erros **não viraram request**. A coleção não testa nada disso —
está aqui para ninguém supor o contrário.

| Condição | HTTP esperado | Por que não vira request |
|---|---|---|
| `OPENAI_API_KEY` ausente (linha 359) | 500 | Falha na construção de `RagProperties`, antes de qualquer chamada: o processo não sobe, não há resposta HTTP para provocar. |
| Qdrant não responde (linha 360) | 503 | Falha de transporte. Exige derrubar o container, não enviar uma requisição diferente. |
| OpenAI não responde na geração (linha 361) | 503 | Falha de transporte externa, não provocável por requisição. |
| OpenAI não responde na **reescrita** (linha 362) | 200 com `reason = reescrita_falhou` | Fallback dependente de falha externa não determinística. Os testes só aceitam `reescrita_falhou` como valor válido do conjunto fechado; nenhum request o provoca. |
| Dimensão do embedding difere da coleção (linha 370) | 503 no `/health` | Exige uma coleção construída com outro modelo de embedding. Estado provocado, fora do alcance de um request. |
| PDF sem texto extraível (linha 369) | 422 | Exige um PDF preparado (imagem sem camada de texto) no corpus. Não há corpus ainda; `discarded_pages` cobre o caso parcial e não é erro. |
| Rótulo `[n]` fora de `1..k` (linha 371) | 200 com `meta.unresolved_labels` | Depende da saída do LLM. A invariante 4 é verificada **se** ocorrer, mas nenhum request consegue forçá-la. |

Também fora do alcance de HTTP, por decisão do próprio FDD: a matriz de recusa completa do
critério 4 (turnos 1, 2 e 3 × dentro/fora do corpus × reescrita ligada/desligada) é pytest
com dublês e **nenhuma chamada à API paga** (seção 9, linha 485); a comparação de custo do
critério 5; a conferência manual de citação do critério 3; e os critérios 6, 7, 9 e 11.

## Divergência que afeta a execução

`divergencias.md` registra uma divergência **ALTA**: o `rag-api.yaml` 1.1.0 **não declara
`422` em `POST /ask`**, mas o FDD especifica 422 para `k` inválido, `history_window`
negativo e turno malformado. Os quatro requests de 422 em `erros/` testam comportamento
que só o FDD sustenta. Se a implementação seguir o contrato ao pé da letra, eles falham —
e a falha é do contrato, não da coleção.
