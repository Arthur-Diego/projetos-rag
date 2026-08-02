# Coleção HTTP — pipeline multimodal de ponta a ponta

Gerada em **2026-08-02**, a partir do commit **`7d8a0e0`**
(`docs(rag-04/adrs): seis decisoes estruturais do pipeline multimodal`).

Origem: `docs/domains/rag/features/pipeline-multimodal-fdd.md` — seção 5 (contratos
públicos, linhas 160–266), seção 4 (ordem dos fluxos, linhas 94–156), seção 6 (matriz de
erros e invariantes, linhas 269–299) e seção 9 (critérios de aceite).

Contrato cruzado: `../../../../../docs/contracts/rag-api.yaml`, versão **1.2.0**. O FDD
especifica **1.3.0** (ADR-004: `kind`, `content_html`, `elements`, nota de idempotência
no `/ingest`), que ainda não foi publicada — é a **etapa 2 do Build Order** (seção 11,
linha 449), a ser feita antes do consumidor. As 8 divergências estão em
`divergencias.md`, **nenhuma ALTA** (rotas, verbos e status do FDD existem todos na
1.2.0; o delta é de campos opcionais), e aquele arquivo é a checklist daquela etapa.

| Arquivo | O que é |
|---|---|
| `pipeline-multimodal.postman_collection.json` | 16 requests em 4 pastas: `meta/` (2), `ingest/` (3), `ask/` (2), `erros/` (9) |
| `pipeline-multimodal.postman_environment.json` | `baseUrl`, `accessToken` (não usado), `chromaUrl` (referência para provocar os estados de erro) |
| `divergencias.md` | FDD × `rag-api.yaml` 1.2.0, item a item |

## Estado: o serviço ainda não existe

O projeto é terreno documentado, **sem uma linha de Python**. Não há nada escutando em
`http://127.0.0.1:8080` e a coleção **não foi executada**. O `newman` está instalado
nesta máquina (6.2.2), e mesmo assim não foi rodado: sem serviço, toda execução seria
uma parede de `ECONNREFUSED`, que não é informação sobre nada. Nada foi instalado, nada
foi subido.

A coleção é artefato válido do mesmo jeito — importável no Postman, Insomnia ou Bruno —
e a execução acontece na **validação (Passo 7)**, depois da **etapa 9 do Build Order**
(camada HTTP: `rag/api/`, `serve.py`, `GET /health`, `GET /capabilities`). A checagem
contra o schema 1.3.0 depende da **etapa 2** (evolução do yaml).

## Como importar

Postman: *Import* → arraste os dois arquivos JSON → selecione o environment **rag-04
local** no canto superior direito.

### `accessToken`

**Não precisa preencher.** Nenhuma rota é autenticada: o `rag-api.yaml` não declara
`securitySchemes` e a seção 5 do FDD não cita header de autorização. A coleção **não tem
bloco `auth`** e não envia esse valor em lugar nenhum; a variável existe só como espaço
reservado.

O que precisa estar configurado é o ambiente do **serviço**, não o da coleção:

1. `OPENAI_API_KEY` no `.env` do projeto (única credencial, FDD seção 8, linha 344).
   Nunca entra neste diretório.
2. Chroma 1.5.9 no ar na **porta 8002**: `docker compose up -d` com healthcheck (seção
   8, linha 342). Derrube os containers dos projetos anteriores antes — um serviço por
   vez no workspace (linha 353).
3. Corpus em `pdfs/` (Petrobras 3T24) e o PDF de controle do BCB em
   `pdfs/fora-do-corpus/`, que **nunca** é indexado (seção 4, linhas 98 e 99).
4. Setup nativo do `unstructured[pdf]`: poppler e tesseract via apt (seção 8, linha
   343). A primeira ingestão roda o `hi_res` em CPU e leva **minutos** — não está
   travada.

### Variável a preencher antes de rodar

`perguntaForaDoCorpus` (variável **de coleção**) nasce vazia porque o FDD não declara o
texto exato: preencha com uma pergunta cuja resposta só exista no PDF do BCB (seção 9,
linha 369). Com ela vazia, o request de controle negativo produz o 422 de pergunta
vazia, não o teste de recusa.

## Como rodar

```bash
newman run docs/domains/rag/postman/pipeline-multimodal.postman_collection.json \
  -e docs/domains/rag/postman/pipeline-multimodal.postman_environment.json \
  --reporters cli --suppress-exit-code \
  --timeout-request 900000
```

O `--timeout-request 900000` (15 min) existe por causa da primeira ingestão: o FDD
documenta esse teto para o `POST /ingest` síncrono (seção 5, linhas 219–222). Execuções
com cache de partição concluem em segundos.

**Não rode a coleção inteira de uma vez.** A pasta `erros/` exige estados incompatíveis
entre si e com `ingest/` e `ask/`. Para o fluxo feliz:

```bash
newman run ... --folder meta --folder ingest --folder ask
```

### Ordem

1. `meta/` — sem efeito colateral e sem chamada paga; primeiro sinal de que a camada
   HTTP subiu.
2. `ingest/` — caro na primeira execução (`hi_res` em CPU), **não destrutivo**
   (idempotente-incremental; reset só por script CLI). Os três requests rodam em
   sequência na mesma sessão: o primeiro grava as contagens do relatório em variáveis
   de coleção e o segundo (reingestão) as compara — é o único encadeamento de valores
   da coleção. O terceiro é a variante `descrever_imagens=false`.
3. `ask/` — a pergunta de célula de tabela (critérios 1 e 2 da seção 9) e o controle
   negativo de recusa.

### Como provocar cada erro da pasta `erros/`

| Request | Estado exigido |
|---|---|
| `422 pergunta vazia` | Nenhum, nem Chroma. Bom primeiro request depois de subir o `serve.py` |
| `422 k fora de faixa` | Nenhum. Determinístico |
| `422 parametro invalido` (`/ingest`) | Nenhum. Determinístico (`descrever_imagens` não-boolean) |
| `409 indice vazio` | Chroma no ar, índice vazio: rodar o **script CLI de reset** e **não** rodar `/ingest` |
| `500 OPENAI_API_KEY ausente` | Subir o `serve.py` sem a chave no `.env`. Se a implementação falhar na construção das propriedades antes de o processo subir (precedente rag-03), não há resposta HTTP e o request não se aplica |
| `503 Chroma fora do ar` (`/ask`, `/ingest`, `/health`) | `docker compose stop` no container do Chroma (8002), com a API de pé |
| `200 degraded apos dessincronia` (`/health`) | Corpus ingerido, depois remover manualmente um original de `data/docstore/` (critério da seção 9, linhas 370 e 371). Reset + reingestão volta a `ok` |

## O que os testes afirmam

Além do status declarado no FDD, cada request confere as invariantes HTTP-testáveis da
seção 6 (linhas 293–299):

| Invariante | Onde é afirmada |
|---|---|
| `content_html` presente **se e somente se** `kind=tabela` (linha 297) | todo hit do `/ask` feliz |
| HTML nunca dentro de `excerpt` (linha 297) | regex `<table\|<tr\|<td\|<th` sobre todo `excerpt` |
| Opcional ausente é **omitido, nunca `null`** (linhas 180, 181 e 298) | hits do `/ask` e corpo do `IngestionReport` |
| `provenance` ausente: só caminho denso (linhas 180 e 181) | todo hit do `/ask` feliz |
| `kind` no enum `texto\|tabela\|imagem` (linha 177) | todo hit do `/ask` feliz |
| Reingestão não recria nada (seção 2, linhas 48–50) | contagens do segundo `/ingest` iguais às do primeiro, e `seconds < 60` (cache) |
| A pergunta de célula traz hit de tabela (seção 9, linhas 361 e 362) | `some(kind === 'tabela')` no `/ask` feliz |
| Recusa preservada (seção 9, linha 369) | `refused === true` no controle negativo |
| `/capabilities` publica exatamente os dois botões (seção 5, linhas 256–258) | valor a valor: `k` (integer, 4, 1–20, ask) e `descrever_imagens` (boolean, true, ingest); `features` sem `history` e sem `stream` |
| Saúde reporta estado, não falha por causa dele | `degraded` é **200**, nunca erro; Chroma fora do ar é **503** |

Dois testes são deliberadamente frouxos, com falha que lista as chaves recebidas em vez
de exigir um nome: a **contagem do docstore** no `/health` (o FDD não nomeia o campo,
linha 249 — divergência 5) — são lembretes para apertar quando a etapa 2 ou a etapa 9
fixarem o nome.

## Casos da seção 6 **não** cobertos por HTTP

Estas linhas da matriz de erros **não viraram request**, ou viraram request cujo estado
se monta fora do HTTP. A coleção não testa nada disto — está aqui para ninguém supor o
contrário.

| Condição | HTTP esperado | Por que não vira request |
|---|---|---|
| OpenAI indisponível ou rate limit persistente (linha 278) | 503 | Falha externa não determinística, após retries com backoff. Nenhuma requisição a provoca |
| Falha da OpenAI **no meio** do enriquecimento (linhas 138, 139 e 282) | 503 no `/ingest` | Idem: exige a API cair no meio do lote. A **retomada** idempotente, que é a promessa, é coberta pela pasta `ingest/` |
| PDF ausente no `ingest.py` (linha 280) | — | Entrypoint CLI: erro no console antes de custo, sem HTTP |
| Cache de partição corrompido (linhas 136, 137 e 281) | — | Autocorreção com log (`descarta, refaz, regrava`); nenhum status HTTP muda |
| Hit com `doc_id` órfão descartado com warning (linhas 140–142 e 283) | 200 | O descarte é log do servidor; o `/ask` segue com os demais hits e **nunca** responde 500 por isso. O que o HTTP enxerga é o `/health` `degraded`, coberto em `erros/` |
| Tabela maior que o limite de contexto (linha 284) | 200 | Truncamento por tabela, logado — evidência de log, não de resposta |
| `Chroma fora do ar`, `409 índice vazio`, `500 sem chave`, `degraded` | 503/409/500/200 | Os requests **existem** em `erros/`, mas provocar cada estado é `docker compose stop`, script de reset, `.env` sem chave ou remoção manual no docstore — não uma requisição diferente |

Também fora do alcance de HTTP, por natureza (seções 2, 7 e 9):

- **HTML íntegro no prompt** (objetivo 1, critério 1): evidência de **log** do servidor
  (`format_context`), não da resposta. A coleção só afirma a consequência visível
  (`content_html` no hit).
- **`novos=0, reaproveitados=N`** e **acerto de cache de partição**: log de ingestão; a
  coleção afirma as consequências (contagens inalteradas, `seconds` baixo).
- **Zero chamadas de enriquecimento na reingestão**: verificável por log/custo, não por
  resposta.
- **Renderização sanitizada no frontend, selo de `kind`, `elements` na UI** (etapa 10):
  outro consumidor, outro artefato.
- **Reset e inspeção de tabelas**: scripts CLI, sem rota HTTP (a v1 não tem rota de
  mídia nem de administração — ADR-004).
- **Medição por classe de alvo, mypy, pytest** (critérios finais): harness e toolchain,
  não contrato HTTP.

## Divergências que afetam a execução

Os testes desta coleção afirmam o comportamento **1.3.0** que só o FDD e o ADR-004
sustentam hoje. Contra uma implementação fiel ao `rag-api.yaml` 1.2.0 publicado,
falhariam: `kind` e `content_html` ausentes nos hits e `elements` ausente no relatório.
A falha é do contrato ainda não evoluído, não da coleção — a etapa 2 do Build Order
(editar o yaml **antes** do consumidor) resolve, e `divergencias.md` é a checklist.
