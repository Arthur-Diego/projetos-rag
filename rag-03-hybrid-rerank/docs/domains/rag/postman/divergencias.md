# Divergências: FDD × contrato publicado

> ## ESTADO: RESOLVIDAS (28/07/2026)
>
> Este arquivo foi gerado no **Passo 5.5** do ciclo, quando o contrato ainda estava
> em 1.1.0 e o FDD já especificava 1.2.0. A **etapa 10 do Build Order foi
> executada** e o contrato subiu. O corpo abaixo é o registro original, mantido
> porque a análise item a item continua sendo o melhor mapa do que mudou e por quê.
>
> **Duas divergências terminaram diferente do que a análise previa, e são as que
> valem reler:**
>
> - **A1** (`distance` obrigatório) foi resolvida **tirando `distance` de
>   `required`**, o que **não é aditivo**. O ADR-005 prometia "aditivo puro" e
>   ganhou seção de Revisão por causa disto. O campo continua sendo emitido sempre
>   que o trecho passou pelo caminho denso; só falta no trecho achado exclusivamente
>   por BM25, onde nunca teve valor. `rag-01` e `rag-02` emitem em 100 por cento dos
>   hits e seguem válidos, verificado rodando a suíte do rag-02.
> - **A2** (`/health` sem 409) foi resolvida **ao contrário do previsto**. O 409
>   chegou a ser publicado no contrato e depois foi **removido**: `/health` responde
>   200 com `status: degraded`, porque saúde REPORTA estado. Quem devolve 409 é o
>   `POST /ask`. O critério de aceite 10 foi reescrito para nomear a rota.
>
> **Duas continuam abertas, por decisão e não por esquecimento:**
>
> - **M4**, parâmetros do funil fora do schema de `options`. `options` é
>   `additionalProperties: true` desde 1.0.0 e o `k` também está fora desde então.
>   Publicar a faixa em `/capabilities` e impô-la no construtor do serviço é o
>   mecanismo do projeto; duplicá-la no schema criaria dois lugares para manter.
> - **M7**, `POST /ingest` fora da seção 5 do FDD. A rota não muda de contrato; o
>   que mudou foi o comportamento interno da ingestão, que é assunto da seção 4.
>
> **M8** foi resolvida **em favor do código**: cluster amarelo é aceito, porque nó
> único nunca fica verde. Só vermelho dá 503. Corrigimos o FDD e o diagrama, não o
> código.
>
> As demais foram atendidas na subida para 1.2.0.


**FDD:** `docs/domains/rag/features/funil-recuperacao-hibrido-fdd.md`, versão 1.0, de
2026-07-28. Declara depender do contrato compartilhado **1.2.0** (seção 5, linha 176).

**Contrato publicado:** `../../../../../docs/contracts/rag-api.yaml`
(`/home/arthu/code/projetos-rag/docs/contracts/rag-api.yaml`), OpenAPI 3.1.0,
`info.version: 1.1.0` (linha 5). Único arquivo `openapi*.{yaml,yml,json}` do workspace: não
há bundle, não há cópia em `dist/`, não há contrato vindo por pacote.

**O 1.2.0 não existe ainda, e isso é esperado.** Elevá-lo é a **etapa 10 do Build Order**
(seção 11, linha 540), que depende da etapa 9. Este arquivo é a lista do que aquela etapa
precisa fazer, item a item. Nenhuma linha abaixo é defeito de implementação: é dívida de
contrato já agendada.

São **14 divergências: 3 ALTAS, 9 MÉDIAS e 2 BAIXAS.**

## Resumo

| # | Severidade | O que | Onde fica no contrato |
|---|---|---|---|
| A1 | **ALTA** | `distance` é obrigatório em `SearchHit`, e a configuração padrão não o emite | `components.schemas.SearchHit.required`, linha 263 |
| A2 | **ALTA** | `/health` não declara **409**, que o critério 10 exige | `paths./health.get.responses`, linhas 55 a 74 |
| A3 | **ALTA** | `score` não existe, e o contrato tem uma nota que **proíbe o nome** | `components.schemas.SearchHit`, linhas 264 a 266 |
| M1 | MÉDIA | `hits[].provenance` e o schema `Provenance` não existem | `components.schemas` |
| M2 | MÉDIA | Os quatro `timings` novos não existem, nem a regra "ausente, nunca zero" | `Answer.timings`, linhas 367 a 378 |
| M3 | MÉDIA | `search_s` não diz que é o **total** que os quatro decompõem | `Answer.timings.search_s`, linha 377 |
| M4 | MÉDIA | `hibrida`, `rerank`, `candidates` e `rrf_k` não estão no schema de `options` | `paths./ask.post.requestBody`, linhas 144 a 159 |
| M5 | MÉDIA | O 409 de `/ask` passa a ter **dois** significados e o contrato descreve um | `paths./ask.post.responses.409`, linhas 173 a 177 |
| M6 | MÉDIA | `/health` não tem campo para o estado do mapping — e o FDD não o nomeia | `paths./health.get.responses.200`, linhas 60 a 69 |
| M7 | MÉDIA | `POST /ingest` não está na seção 5 do FDD, e a feature muda o que ele faz | lacuna do FDD, não do contrato |
| M8 | MÉDIA | Cluster degradado: `200` com `status: degraded` no contrato, `503` no FDD | `/health` 200, linha 64 |
| M9 | MÉDIA | Ambiguidade: `distance` "válido apenas quando…" não diz se fica **ausente** | FDD linha 208 |
| B1 | BAIXA | O exemplo de `/capabilities` ainda é o do `rag-01` | linhas 104 a 123 |
| B2 | BAIXA | `info.version` e a seção de changelog do 1.2.0 | linhas 5 e 19 a 42 |

---

## A1 — `distance` é obrigatório, e a configuração padrão não o emite

**Severidade: ALTA.** É a única divergência que quebra em runtime qualquer validador ou
cliente gerado a partir do contrato.

- **O contrato diz** (linha 263): `SearchHit.required: [source, distance]`. Todo trecho
  retornado tem que trazer `distance`.
- **O FDD diz** (linhas 207 e 208): `distance` "é mantido e depreciado, documentado como
  válido apenas quando `hibrida` e `rerank` estão desligados". E o padrão do sistema é
  `hibrida: true` e `rerank: true` (linhas 182 e 183).
- **O próprio exemplo de resposta do FDD** (linhas 232 a 263) mostra um hit **sem**
  `distance`, com `score` e `provenance` no lugar.

Ou seja: na configuração padrão, **toda resposta de `/ask` deste projeto é inválida contra
o contrato 1.1.0.**

**O que a etapa 10 precisa fazer:** `required: [source]`.

**E precisa fazer com os olhos abertos, porque não é aditivo.** O FDD afirma (linha 400)
que o 1.2.0 é "aditivo puro: todo campo novo é opcional e nenhum existente muda de
significado". Tirar um campo de `required` não é acrescentar campo opcional — é relaxar
obrigação, e o próprio contrato tem uma regra contra isso (linha 15: "acrescente campos
opcionais, nunca altere os obrigatórios"). Um cliente de 1.1.0 que leia `hit.distance` sem
checar existência quebra. Os Projetos 1 e 2 continuam **emitindo** `distance` e por isso
seguem conformes, mas um consumidor genérico escrito contra 1.1.0 não segue.

Duas saídas, e a etapa 10 tem que escolher uma explicitamente:

1. tirar de `required` e registrar na nota do 1.2.0 que esta é a **única** quebra de
   compatibilidade da versão, com a justificativa; ou
2. manter `required` e emitir `distance` sempre — o que reintroduz exatamente a colisão de
   escala descrita no risco da seção 10 do FDD (linhas 502 a 513), porque o
   `ConsoleReporter` imprime o mínimo como "melhor".

A opção 2 é pior, e o FDD já decidiu contra ela. A escolha é a 1; o que falta é registrá-la.

## A2 — `/health` não declara 409

**Severidade: ALTA.** Status especificado no FDD sem respaldo no contrato.

- **O contrato diz** (linhas 55 a 74): `/health` responde **200** ou **503**. Só.
- **O FDD diz** (critério 10, seção 9, linha 432): "Motor fora do ar devolve 503; motor no
  ar com índice ausente devolve **409**; cluster degradado não é aprovado como saudável."

O 409 de `/health` não existe no contrato. É a única rota da feature em que um status
especificado simplesmente não tem entrada no documento publicado — em `/ask`, os quatro
status do FDD (200, 409, 422, 503) e o 500 da matriz de erros já estão todos declarados.

**O que a etapa 10 precisa fazer:** acrescentar `"409"` em `paths./health.get.responses`,
com `$ref: "#/components/schemas/Problem"` e descrição distinguindo-o do 503 — índice
ausente é estado do dado, motor fora do ar é estado da dependência.

## A3 — `score` não existe, e o contrato tem uma nota que proíbe o nome

**Severidade: ALTA.** Não é ausência de campo: é contradição normativa deixada por escrito.

- **O contrato diz** (linhas 264 a 266, na descrição de `SearchHit`): "`distance` é
  DISTÂNCIA: menor é mais próximo. **Chamar de score inverteria a leitura na interface.**"
- **O FDD diz** (linha 203): "`hits[].score`: valor final de ordenação, **maior é
  melhor**. É o valor do rerank quando ele rodou, e o da fusão quando não rodou." E na
  linha 210: "`score` e `distance` nunca compartilham campo, porque têm sentidos opostos."

As duas frases não se contradizem de fato — o FDD faz exatamente o que o contrato pedia,
que é **não** reaproveitar `distance` para um valor de sentido oposto. O problema é que o
leitor do contrato encontra uma nota dizendo "não chame de score" enquanto o backend emite
um campo chamado `score`, e não tem como saber que são grandezas diferentes em campos
diferentes.

**O que a etapa 10 precisa fazer, e nesta ordem:**

1. acrescentar `score: { type: number, format: float }` em `SearchHit`, com descrição
   dizendo **maior é melhor** e que é o valor do rerank quando ele rodou e o da fusão
   quando não rodou;
2. **reescrever a nota da linha 265**, que hoje lê como proibição. O texto novo precisa
   dizer que `score` e `distance` coexistem como campos separados, com sentidos opostos, e
   que é justamente por isso que nenhum dos dois pode ocupar o campo do outro;
3. marcar `distance` com `deprecated: true` e documentar a condição de validade (ver M9).

Sem o item 2, o contrato 1.2.0 fica prescrevendo e proibindo a mesma coisa em dois
parágrafos, e quem resolver a contradição sozinho vai resolver errado.

## M1 — `provenance` e o schema `Provenance` não existem

- **O contrato diz:** `SearchHit` tem `source`, `page`, `distance` e `excerpt`. Nada mais.
- **O FDD diz** (linhas 204 a 206): `hits[].provenance` é um objeto com `paths` (lista
  contendo `densa`, `bm25` ou ambos), `dense_rank`, `keyword_rank`, `rrf_score` e
  `rerank_score`. "Ranks são 1-based; campos de caminho não executado ficam ausentes."

Não é enfeite de diagnóstico: o ADR-003 e a seção 7 (linhas 360 e 361) fazem dele o dado
bruto da tabela de medição, e a seção 12 do frontend (linha 542) o renderiza por trecho.

**O que a etapa 10 precisa fazer:** schema `Provenance` novo, com `paths` como array de
enum `[densa, bm25]`, os dois ranks como inteiros com `minimum: 1`, e os dois scores como
number. Nenhum campo em `required`, porque "caminho não executado fica ausente" é a regra.
`SearchHit.provenance` opcional apontando para ele.

## M2 — Os quatro `timings` novos não existem, nem a regra "ausente, nunca zero"

- **O contrato diz** (linhas 367 a 378): `timings` tem `rewrite_s`, `search_s` e
  `generation_s`.
- **O FDD diz** (linhas 196 a 201): entram `dense_s`, `keyword_s`, `fusion_s` e `rerank_s`.
  São quatro, e não os três do ADR-005, porque com `search_s` significando o total o
  caminho denso ficaria sem campo próprio.

O schema não fecha `additionalProperties`, então emitir os quatro não viola nada — mas um
cliente gerado a partir de 1.1.0 os descarta em silêncio, e a tabela de medição sai vazia
sem erro nenhum.

**A parte que o schema não expressa, e que precisa ir na descrição:** estágio que não
executou aparece **ausente**, nunca zerado (FDD linhas 69, 153, 154, 350 e critério 6,
linhas 421 a 423). É a diferença entre "a busca léxica levou 0 s" e "a busca léxica não
rodou", e sobre ela repousa a leitura inteira da tabela das três configurações. JSON Schema
não tem como exigir isso; a descrição tem que dizê-lo com todas as letras.

## M3 — `search_s` não diz que é o total que os quatro decompõem

- **O contrato diz** (linha 377): `search_s: { type: number, format: float }`. Sem
  descrição.
- **O FDD diz** (linhas 196 a 198): "`timings.search_s` existente **mantém o significado**:
  tempo total do estágio de recuperação. Os quatro campos novos o decompõem."

Sem essa frase no contrato, quem somar os cinco para achar o custo do turno conta o estágio
de recuperação duas vezes. É divergência de descrição, mas com consequência aritmética.

**O que a etapa 10 precisa fazer:** descrição em `search_s` declarando o todo e a parte.

## M4 — Os quatro parâmetros novos não estão no schema de `options`

- **O contrato diz** (linhas 139 a 159): `options` tem `additionalProperties: true` e
  declara nominalmente só `history`. O texto é explícito: "O backend **ignora chaves
  desconhecidas** em vez de falhar."
- **O FDD diz** (linha 180): `hibrida` (boolean, padrão `true`), `rerank` (boolean, padrão
  `true`), `candidates` (integer, 1 a 50, padrão 20), `rrf_k` (integer, 1 a 1000, padrão
  60).

**Não quebra em runtime** — `additionalProperties: true` os aceita, e o descobrimento de
parâmetro é feito por `/capabilities`, não pelo schema. Fica em MÉDIA porque as faixas (1 a
50, 1 a 1000) passam a existir só no FDD e no descritor, e um validador de contrato não tem
como reprovar `candidates: 51`.

**Precedente que vale considerar antes de mexer:** `k` também não está declarado no schema
de `options`, desde 1.0.0, e ninguém sentiu falta. A etapa 10 deve decidir **uma vez** para
os dois casos: ou `/capabilities` é a única fonte de parâmetro (e nada entra no schema), ou
o schema passa a espelhá-lo (e `k` entra junto). O que não pode é `k` fora e `candidates`
dentro, sem motivo.

## M5 — O 409 de `/ask` passa a ter dois significados

- **O contrato diz** (linhas 173 a 177): 409 é "Índice vazio; rode a ingestão".
- **O FDD diz** (linhas 269 e 270): 409 é "índice vazio ou inexistente (`EMPTY_INDEX`), ou
  índice mal mapeado (`INVALID_INDEX_MAPPING`, e apenas quando `hibrida` está ligado)".

O status existe; o segundo significado, não. `Problem.code` é string livre (linha 411, com
`SERVICE_UNAVAILABLE` como exemplo), então nada impede emitir `INVALID_INDEX_MAPPING` — mas
o frontend não tem como saber que precisa mostrar "reindexe com mapping explícito" em vez
de "rode a ingestão". São receitas diferentes para o mesmo status.

**O que a etapa 10 precisa fazer:** descrever os dois códigos na resposta 409 de `/ask`,
incluindo a condicionalidade (`INVALID_INDEX_MAPPING` só ocorre com `hibrida` ligado, FDD
linha 322). Enumerar `Problem.code` seria melhor ainda, mas é mudança maior e afeta os
Projetos 1 e 2.

## M6 — `/health` não tem campo para o estado do mapping, e o FDD não o nomeia

- **O contrato diz** (linhas 60 a 69): `status`, `project`, `collection`,
  `indexed_chunks`, `embedding_model`, `embedding_dimensions`.
- **O FDD diz** (linha 283): "Passa a reportar o estado do mapping do campo de texto, além
  da dimensão do vetor."

**A lacuna é dupla, e a metade do FDD é a que importa.** O contrato não tem o campo porque
ninguém o especificou: o FDD não diz o **nome**, o **tipo** nem os **valores** desse
estado. Booleano `text_field_analyzed`? Enum `mapping_status: [ok, inferido, ausente]`? O
nome do analisador?

A coleção testa isso da única forma que dá para sustentar: aceita qualquer chave cujo nome
contenha `mapping`, `analyz`, `text_field` ou `analisad`, e falha listando o que recebeu. É
um lembrete, não uma especificação — e é por isso que esta linha está aqui.

**O que a etapa 10 precisa fazer:** exigir a definição antes de escrever o schema. O
critério 9 (linha 429) e o risco mais sério do projeto (linhas 451 a 462) dependem deste
campo ser legível por quem opera.

## M7 — `POST /ingest` não está na seção 5 do FDD

**Divergência no sentido inverso: rota do contrato ausente do FDD.**

- **O contrato diz:** `POST /ingest` existe desde 1.0.0, com `IngestionReport`.
- **O FDD diz:** a seção 5 declara `POST /ask` (5.1), `GET /capabilities` (5.2) e
  `GET /health` (5.3). **`/ingest` não aparece.** Mas a seção 3 (linhas 82 e 83) e a seção 4
  (linhas 136 a 148) mudam o que a ingestão faz: mapping explícito com `dense_vector` e
  campo de texto analisado em português, criado pelo sistema e nunca inferido pelo motor.

A feature muda o comportamento da rota sem publicar o contrato dela. Na prática o schema
não precisa mudar — o `IngestionReport` 1.1.0 já tem todos os campos que a seção 7 (linhas
362 e 363) exige do relatório, inclusive `previous_chunks` e os parâmetros de divisão. Fica
em MÉDIA como lacuna de escopo do FDD, não de schema.

A coleção inclui `POST /ingest` mesmo assim, porque sem ele nenhum request de `ask/` tem
índice contra o que rodar. O request vai **sem corpo**, porque a seção 5 do FDD não declara
parâmetro de ingestão nenhum e inventar `chunk_size` no corpo seria inventar contrato.

## M8 — Cluster degradado: 200 no contrato, 503 no FDD

- **O contrato diz** (linha 64): `status: { type: string, enum: [ok, degraded] }` numa
  resposta **200**. Existe um estado "degradado" que é reportado com sucesso HTTP.
- **O FDD diz** (linha 320): "Cluster respondendo mas degradado → `ServiceUnavailableException`
  → **503**". E o critério 10 (linha 433): "cluster degradado não é aprovado como saudável".

Não é contradição formal — o contrato permite 503 e o projeto pode simplesmente nunca
emitir `degraded`. Mas um frontend genérico que trate `status === 'degraded'` como "operante
com ressalva" e um que trate 503 como "fora do ar" se comportam de forma diferente diante
do mesmo cluster amarelo.

**O que a etapa 10 precisa fazer:** dizer no contrato quando `degraded` é emitido, ou
registrar que este projeto não o emite e usa 503 no lugar. A coleção falha o teste se
receber `degraded` num 200, com a mensagem apontando para esta linha.

## M9 — Ambiguidade: `distance` "válido apenas quando…" não diz se fica ausente

**Ambiguidade da seção 5 do FDD**, registrada conforme a regra de gerar o request com o que
dá para sustentar e anotar aqui.

O FDD (linha 208) diz que `distance` é "mantido e depreciado, documentado como válido
apenas quando `hibrida` e `rerank` estão desligados". Isso admite duas leituras
incompatíveis:

1. nas outras configurações `distance` fica **ausente**; ou
2. `distance` continua presente, mas o valor não deve ser lido.

**A coleção assume a leitura 1** e afirma `to.not.have.property('distance')` nos requests
de híbrida e de híbrida mais rerank. O motivo é o próprio risco da seção 10 (linhas 502 a
513): o `ConsoleReporter` imprime o mínimo de `distance` como "melhor" e existe teste
herdado que afirma `distance > 0.9`. Um `distance` presente e inválido é lido como válido
por três lugares ao mesmo tempo, sem erro — que é exatamente o defeito que a separação de
campos existe para impedir. A leitura 2 mantém a bomba armada.

**O que a etapa 10 precisa fazer:** escolher a leitura 1 e escrevê-la no contrato — algo
como "presente apenas quando `hibrida` e `rerank` são ambos `false`". Se a decisão for a
leitura 2, os três testes da coleção mudam, e a decisão precisa de justificativa contra a
seção 10 do FDD.

## B1 — O exemplo de `/capabilities` ainda é o do `rag-01`

O contrato (linhas 104 a 123) traz um `example` com `project: rag-01-fundamentos-pdf` e
apenas `k` e `chunk_size`. Não é normativo, mas é o único lugar do documento que mostra
como um descritor de parâmetro se parece — e o mecanismo de desacoplamento inteiro depende
de as pessoas entenderem esse formato.

Vale acrescentar `hibrida` e `candidates` ao exemplo: um `type: boolean` e um parâmetro com
`applies_to: [ask]` e faixa. `ParameterSpec` já aceita ambos sem nenhuma mudança (o enum de
`type` na linha 246 inclui `boolean`, e o de `applies_to` na linha 259 inclui `ask`), então
é só exemplo.

## B2 — `info.version` e a seção de changelog

`info.version` passa de `1.1.0` para `1.2.0` (linha 5), e `info.description` ganha uma
seção `## 1.2.0 — busca híbrida e reordenação` no formato da seção `## 1.1.0 — conversa e
procedência` (linhas 19 a 42), com origem em
`rag-03-hybrid-rerank/docs/adrs/generated/RAG/ADR-005`.

A seção nova é o lugar natural para registrar a decisão de A1, que é a única não aditiva da
versão.

---

## O que **não** é divergência

Registrado para a etapa 10 não gastar tempo com isto:

- **`422`, `409`, `500` e `503` em `POST /ask`** já estão todos declarados no contrato
  1.1.0 (linhas 173 a 196). Os quatro status da seção 5 do FDD (linhas 268 a 273) e o 500 da
  matriz de erros (linha 323) têm respaldo. A rota `/ask` não precisa de status novo.
- **`ParameterSpec` já aceita os quatro parâmetros novos** sem mudança: `type` inclui
  `boolean` (linha 246), `applies_to` inclui `ask` (linha 259), e `minimum`/`maximum`/
  `default` já existem.
- **`options` com `additionalProperties: true`** (linha 143) permite enviar `hibrida`,
  `rerank`, `candidates` e `rrf_k` hoje, sem alterar o contrato. Ver M4.
- **`citations` e a invariante da recusa** já estão no contrato desde 1.1.0 (linhas 358 a
  363), com a frase "uma resposta com `refused: true` tem `citations` vazia" — que é
  exatamente a invariante da linha 345 do FDD. Nada a fazer.
- **`IngestionReport`** já tem `previous_chunks`, `discarded_pages`, `chunk_size` e
  `chunk_overlap` (linhas 390 a 400), que cobrem o relatório da seção 7 do FDD.
- **`servers: http://localhost:8080`** (linha 45) versus a porta local deste projeto: o
  contrato diz em texto que "cada projeto pode usar outra porta". Não é divergência.
- **`Problem.code` como string livre** (linha 411): permite `EMPTY_INDEX`,
  `INVALID_INDEX_MAPPING` e o que mais vier. Ver M5 — o problema é de descrição, não de
  tipo.
