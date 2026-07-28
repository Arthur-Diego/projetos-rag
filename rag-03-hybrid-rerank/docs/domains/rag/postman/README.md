# Coleção HTTP — funil de recuperação híbrido

Gerada em **2026-07-28**, a partir do commit **`15fbdcf`**
(`docs(rag-03/funil): FDD do funil de recuperacao hibrido`).

Origem: `docs/domains/rag/features/funil-recuperacao-hibrido-fdd.md` — seção 5 (contratos
públicos), seção 4 (ordem dos fluxos), seção 6 (matriz de erros e invariantes) e seção 9
(critérios de aceite).

Contrato cruzado: `../../../../../docs/contracts/rag-api.yaml`, versão **1.1.0**. O FDD
especifica **1.2.0**, que ainda não foi publicado — é a etapa 10 do Build Order. As 14
divergências estão em `divergencias.md`, **três delas ALTAS**, e aquele arquivo é a
checklist daquela etapa.

| Arquivo | O que é |
|---|---|
| `funil-recuperacao-hibrido.postman_collection.json` | 14 requests em 4 pastas: `meta/` (2), `ingest/` (1), `ask/` (4), `erros/` (7) |
| `funil-recuperacao-hibrido.postman_environment.json` | `baseUrl`, `accessToken` (não usado), `elasticsearchUrl`, `elasticsearchHealthPath` |
| `divergencias.md` | FDD × `rag-api.yaml` 1.1.0, item a item |

## Estado: o serviço ainda não existe

O projeto é terreno documentado, **sem uma linha de Python**. Não há nada escutando em
`http://127.0.0.1:8000` e a coleção **não foi executada**. O `newman` está instalado nesta
máquina (6.2.2), e mesmo assim não foi rodado: sem serviço, toda execução seria uma parede
de `ECONNREFUSED`, que não é informação sobre nada. Nada foi instalado, nada foi subido.

A coleção é artefato válido do mesmo jeito — importável no Postman, Insomnia ou Bruno — e é
o que se roda depois da **etapa 9 do Build Order** (camada HTTP: `rag/api/`, `serve.py`).
A conferência contra o contrato só faz sentido depois da **etapa 10**.

## Como importar

Postman: *Import* → arraste os dois arquivos JSON → selecione o environment **rag-03
local** no canto superior direito.

### `accessToken`

**Não precisa preencher.** Nenhuma rota é autenticada: o `rag-api.yaml` não declara
`securitySchemes` e a seção 5 do FDD não cita header de autorização. A coleção **não tem
bloco `auth`** e não envia esse valor em lugar nenhum; a variável existe só como espaço
reservado, para o dia em que a API ganhar autenticação.

O que precisa estar configurado é o ambiente do **serviço**, não o da coleção:

1. `OPENAI_API_KEY` no `.env` do projeto — embeddings da ingestão e da query, e a geração.
   Nunca entra neste diretório. O rerank roda local, na CPU, e não gasta API.
2. Elasticsearch no ar: `docker compose up -d elasticsearch`. Ele leva cerca de 30 s até
   aceitar conexão, e por isso o healthcheck do compose é obrigatório (FDD seção 8,
   linha 391).
3. Corpus em `pdfs/`, e o corpus de controle em `pdfs/fora-do-corpus/`, que **nunca** é
   indexado.
4. O `sentence-transformers` baixa cerca de 500 MB de modelo no primeiro uso (seção 8,
   linha 390). A primeira execução da pasta `ask/` vai parecer travada; não está.

### Sobre a porta

`baseUrl` está em `http://127.0.0.1:8000`, conforme informado na geração. **Confira antes
de rodar:** o `CLAUDE.md` do projeto registra a 8000 como já ocupada pelo container do
Chroma do Projeto 1, e recomenda derrubar os containers dos projetos anteriores antes de
trabalhar neste. Se o `serve.py` acabar em outra porta, mude a variável no environment — a
coleção inteira usa `{{baseUrl}}`.

## Como rodar

```bash
newman run docs/domains/rag/postman/funil-recuperacao-hibrido.postman_collection.json \
  -e docs/domains/rag/postman/funil-recuperacao-hibrido.postman_environment.json \
  --reporters cli --suppress-exit-code
```

**Não rode a coleção inteira de uma vez.** A pasta `erros/` exige estados do índice
incompatíveis entre si e com a pasta `ask/`. Para o fluxo feliz:

```bash
newman run ... --folder meta --folder ingest --folder ask
```

### Ordem

1. `meta/` — sem efeito colateral e sem chamada paga. `GET /capabilities` continua sem
   `Depends` (FDD linha 279) e responde com a infraestrutura fora do ar, então é o primeiro
   sinal de que a camada HTTP subiu.
2. `ingest/` — caro e destrutivo, recria o índice com mapping explícito.
3. `ask/` — as três primeiras requisições são as três colunas da tabela de medição (só
   densa, híbrida, híbrida mais rerank) e a quarta é o 422 de `k > candidates`.

Não há encadeamento de valor entre requests: a seção 4 do FDD descreve um funil **dentro
de um turno**, não uma sequência de turnos, e nenhuma variável de coleção é preenchida por
script. Cada request roda isolado.

### Como provocar cada erro da pasta `erros/`

| Request | Estado exigido |
|---|---|
| `409 EMPTY_INDEX` | Elasticsearch no ar, índice ausente ou vazio: `docker compose down -v`, subir de novo, **sem** rodar `/ingest` |
| `409 INVALID_INDEX_MAPPING` | Índice criado **sem** mapping explícito, deixando o motor inferir o campo de texto (critério 9, linha 429) |
| `200 com hibrida desligado` | O **mesmo** índice mal mapeado do request anterior. Os dois formam o par do critério 9 e se rodam em sequência |
| `422 candidates` / `422 rrf_k` | Nenhum. Determinísticos |
| `422 pergunta vazia` | Nenhum, nem Elasticsearch. Bom primeiro request depois de subir o `serve.py` |
| `503 motor fora do ar` | `docker compose stop elasticsearch`, com a API de pé |

## O que os testes afirmam

Além do status, cada request confere as invariantes da seção 6 (linhas 345 a 350) e o
critério 6 da seção 9:

| Invariante | Onde é afirmada |
|---|---|
| Estágio não executado tem tempo **ausente**, nunca zero | `keyword_s` ausente em "só densa" e em "hibrida desligado"; `rerank_s` ausente em "só densa" e em "híbrida"; os quatro presentes **e maiores que zero** em "híbrida + rerank" |
| `score` e `distance` nunca ocupam o mesmo campo | `score` sempre presente e decrescente (maior é melhor); `distance` presente e **crescente** só em "só densa" (menor é melhor), e **ausente** nas outras três configurações |
| `score` é o rerank quando ele rodou, a fusão quando não rodou | `score == provenance.rrf_score` em "só densa" e "híbrida"; `score == provenance.rerank_score` em "híbrida + rerank" |
| `refused: true` implica `citations` vazia | em toda resposta 200 de `/ask` |
| Procedência com ranks 1-based e caminho não executado ausente | `paths ⊆ [densa, bm25]` e não vazio; `dense_rank`/`keyword_rank` presentes se e somente se o caminho está em `paths`; `rerank_score` ausente com `rerank` desligado |
| O corte final é `k` | `hits.length <= k` nas três configurações |
| `search_s` é o total que os quatro decompõem | `search_s >= dense_s + keyword_s + fusion_s + rerank_s` |
| Erro nomeia parâmetro, valor e faixa (linha 324) | os três 422 conferem o `detail`, não só o status |
| Sem resultado parcial no erro (linha 163) | 422 e 503 não trazem `hits` nem `timings` |
| Deduplicação por identidade do documento | nenhum `source#page#prefixo` repetido em `hits` |

Mais: `/capabilities` confere **valor a valor** os padrões e faixas da tabela da linha 180
do FDD, porque a linha 279 diz que eles são importados de `config.py` e nunca reescritos no
descritor — divergência ali significa descritor escrito à mão. E confere que `top_n` **não**
existe (linhas 104 e 105): o `k` existente é o corte final, e um segundo nome para a mesma
grandeza seria dívida imediata.

Dois testes falham com mensagem explicando o defeito em vez de só o status:

- `409 INVALID_INDEX_MAPPING` recebendo **500** diz que a exceção caiu no tratador
  genérico e precisa vir antes dele em `error_handlers.py` (FDD linha 330).
- `rerank_s` acima de 6 s diz que o modelo provavelmente está sendo carregado por
  requisição em vez de por processo (risco da linha 464).

## Casos da seção 6 **não** cobertos por HTTP

Estas linhas da matriz de erros e destes critérios **não viraram request**. A coleção não
testa nada disso — está aqui para ninguém supor o contrário.

| Condição | HTTP esperado | Por que não vira request |
|---|---|---|
| Elasticsearch fora do ar (linha 319) | 503 | Falha de transporte. O request existe em `erros/`, mas **provocar** o estado é `docker compose stop`, não uma requisição diferente |
| Cluster respondendo mas degradado (linha 320) | 503 | Exige um cluster amarelo ou vermelho de propósito. Nenhuma requisição o produz, e a distinção mora em `/_cluster/health`, fora da API |
| Dimensão do embedding divergente (linha 323) | 500 | Exige um índice construído com outro modelo de embedding. Estado provocado |
| Falha ao carregar o cross encoder (linha 327) | 503 | Depende do modelo faltando em disco ou corrompido. **Nunca degrada em silêncio para "sem rerank"** — mas isso se verifica por teste, não por requisição |
| Falha da OpenAI ao embedar a query (linha 328) | 503 | Falha externa não determinística |
| `OPENAI_API_KEY` ausente | 500 | Falha na construção das propriedades, antes de qualquer chamada: o processo não sobe e não há resposta HTTP |
| Índice mal mapeado (linhas 322 e 429) | 409 / 200 | Os **dois** requests existem em `erros/`, mas o estado (índice sem mapping explícito) é montado fora do HTTP |
| Índice vazio (linha 321) | 409 | Idem: o request existe, o estado é `docker compose down -v` |

Também fora do alcance de HTTP, por decisão do próprio FDD — são testes de unidade com
dublês, sem infraestrutura e sem chamada paga (seção 9 e Build Order etapas 2, 5 e 6):

- **Critérios 1, 2 e 3** — fusão promove consenso, fusão ignora escala e deduplicação por
  identidade: `tests/test_fusion.py`, sobre a função pura.
- **Critério 4** — rerank manda na ordem, com dublê de reranker que inverte a pontuação. A
  coleção só consegue afirmar que a ordem final segue `rerank_score`, o que é consequência
  necessária, não prova.
- **Critério 7** — mapping explícito: exige inspecionar o índice
  (`GET {{elasticsearchUrl}}/<indice>/_mapping`), fora da API da aplicação.
- **Critério 8** — teste de fumaça do BM25, consultando o `KeywordRepository`
  **diretamente**. O FDD é categórico (linhas 158 a 160): "hibrida ligado e denso desligado
  não existe", o diagnóstico "só BM25" vem do harness e **não** de combinação de parâmetros
  públicos. Não há requisição capaz de produzi-lo — e este é o critério que impede que a
  conclusão do projeto seja falsa.
- **Critério 11** — citação conferida à mão contra a página do PDF. A coleção verifica que
  todo `[n]` do texto tem citação correspondente; que a página **está certa** é olho humano.
- **Critérios 12, 13, 14 e 15** — compatibilidade dos Projetos 1 e 2, a tabela de medição,
  o ganho demonstrado, `pytest` e `mypy`.

## Divergências que afetam a execução

Três testes desta coleção testam comportamento que **só o FDD sustenta**, e vão falhar
contra uma implementação que siga o `rag-api.yaml` 1.1.0 ao pé da letra. A falha é do
contrato, não da coleção — ver `divergencias.md`:

1. **`distance` ausente** nos requests de híbrida e híbrida mais rerank. O contrato 1.1.0
   declara `distance` como **obrigatório** em `SearchHit` (A1). Enquanto o 1.2.0 não sair, a
   configuração padrão emite hits inválidos contra o contrato publicado.
2. **`score` e `provenance` presentes.** Nenhum dos dois existe em 1.1.0 (A3 e M1), e a
   descrição de `SearchHit` no contrato ainda diz que chamar de score inverteria a leitura
   na interface.
3. **`/health` com `status: degraded`** faz o teste falhar de propósito (M8): o FDD trata
   cluster degradado como 503, o contrato o admite como 200.
