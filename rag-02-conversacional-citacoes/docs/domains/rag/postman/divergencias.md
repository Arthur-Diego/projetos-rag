# Divergências entre o FDD e o contrato publicado

Gerado em 2026-07-27, commit `030bd87`.

- **FDD:** `rag-02-conversacional-citacoes/docs/domains/rag/features/consulta-ciente-do-historico-fdd.md`
- **Contrato:** `docs/contracts/rag-api.yaml` — OpenAPI 3.1.0, `info.version: 1.1.0`
  (único arquivo encontrado na busca; não há bundle com `$ref` resolvido, e o documento
  usa apenas `$ref` internos, então a comparação não sofre de referência não resolvida)

Nenhuma rota do contrato relacionada ao domínio está ausente do FDD: `/health`,
`/capabilities`, `/ask` e `/ingest` são exatamente as quatro declaradas na seção 5.
Todas as divergências abaixo são de **status** ou de **schema**.

## ALTA

| # | O que o FDD diz | O que o contrato diz | Onde |
|---|---|---|---|
| 1 | `POST /ask` devolve `422` para parâmetro inválido (`k < 1`, `k > 20`, `history_window < 0`) e para turno malformado em `options.history`. É a espinha de quatro dos onze critérios de aceite. | `paths./ask.post.responses` declara apenas `200`, `409` e `503`. **Não existe `422` em `/ask`.** | FDD seção 5, linha 186; seção 6, linhas 364, 365 e 366 · contrato linhas 159 a 174 |

Consequência prática: o tratamento de erro especificado no FDD não tem respaldo no
contrato compartilhado. Um cliente gerado a partir do `rag-api.yaml` (inclusive o frontend
genérico do workspace) não sabe interpretar o 422 de `/ask` e cairá no ramo de erro
inesperado. Os quatro requests de 422 em `erros/` testam comportamento que **só o FDD
sustenta**.

Correção mínima e retrocompatível: acrescentar a resposta `422` com `$ref` para `Problem`
em `/ask` no `rag-api.yaml`. Isso não altera nenhum campo `required` e portanto não
contraria o ADR-005 nem quebra o `rag-01` — acrescentar resposta de erro é adição
opcional, e o `rag-01` simplesmente nunca a emite. **Esta é a única alteração de contrato
que a feature realmente precisa, e ela não estava prevista no FDD.**

## MEDIA

| # | O que o FDD diz | O que o contrato diz | Onde |
|---|---|---|---|
| 2 | `OPENAI_API_KEY` ausente → `500` (`InvalidConfigurationException`). | Nenhuma rota declara `500`. | FDD seção 6, linha 359 · contrato, todas as rotas |
| 3 | Qdrant fora do ar → `503` em qualquer caminho que o toque, e `/ingest` escreve no Qdrant. | `/ingest` declara só `200` e `422`. `503` só existe em `/health` e `/ask`. | FDD seção 6, linha 360 · contrato linhas 194 a 204 |
| 4 | Invariante 2: `rewritten_question` está presente em **100 por cento** das respostas de `/ask`, nunca omitida por ser igual à original. | `Answer.required = [text, hits, refused, timings]`; `rewritten_question` é opcional. | FDD seção 2, linha 57; seção 6, linha 386 · contrato linhas 289 a 312 |
| 5 | Invariante 3: `timings.rewrite_s` está presente **sempre**, e vale `0.0` exatamente quando não houve chamada de LLM de reescrita. | Nenhuma propriedade de `timings` é `required`; `rewrite_s` é descrito como "opcional, desde 1.1.0". | FDD seção 2, linha 68; seção 6, linha 387 · contrato linhas 313 a 324 |
| 6 | `/health` reporta `collection`, `indexed_chunks`, `embedding_model` e `embedding_dimensions`, e o critério de aceite confere os seis campos. | `required: [status, project]`. Os outros quatro são opcionais. | FDD seção 5, linhas 271 a 274 · contrato linhas 53 a 61 |
| 7 | `reason` tem **conjunto fechado** de seis valores em snake_case: `primeiro_turno`, `historico_presente`, `pergunta_curta`, `marcador_anaforico`, `pergunta_autossuficiente`, `reescrita_falhou`. É a condição para o critério 5 ser agregável. | `reason` é `string` livre, sem `enum`, e os exemplos da descrição são prosa em formato diferente: "primeiro turno, sem histórico", "pergunta já autossuficiente", "pronome não resolvido". | FDD seção 5, linhas 296 a 305 · contrato linhas 283 a 287 |
| 8 | Contrato exige `question` com `minLength: 1`, mas a matriz de erros do FDD **não tem linha para pergunta vazia ou ausente**: o status é indefinido. | `required: [question]`, `question.minLength: 1`, sem status de erro associado. | FDD seção 6, linhas 357 a 371 (ausência) · contrato linhas 126 a 128 |

Os itens 4, 5 e 6 são efeito colateral consciente da regra de evolução do contrato
(seção 8, linha 451: "nenhum campo novo entra em `required`", ADR-005). São divergências
reais mesmo assim: quem lê só o contrato não pode confiar em campos dos quais o FDD depende
como invariante. A coleção afirma a versão do FDD, que é a mais forte.

O item 7 é o mais provável de virar defeito silencioso: um implementador que siga os
exemplos do contrato emite `reason` em prosa e reprova os critérios de aceite da seção 9
sem que nada no contrato o denuncie.

O item 2 ficou em MEDIA, e não em ALTA, porque a própria coluna "Tratamento" do FDD diz que
a falha ocorre na construção de `RagProperties`, antes de qualquer chamada — o processo não
sobe e nenhuma resposta HTTP é emitida. Se a configuração passar a ser construída por
requisição via `Depends`, vira um `500` real e sobe para ALTA.

## Ambiguidades do FDD (MEDIA)

Registradas aqui porque a coleção teve que decidir alguma coisa para gerar o request.

| # | Ponto ambíguo | O que a coleção assumiu |
|---|---|---|
| 9 | Precedência entre `pergunta_curta` e `marcador_anaforico` quando os dois gatilhos disparam. `E se eu vender dez?` tem menos de 8 palavras **e** contém o marcador `e se`; a seção 5 (linha 133) diz "reescreve com `reason = pergunta_curta` ou `marcador_anaforico`" sem dizer qual vence. | O request de `pergunta_curta` usa uma pergunta que dispara **só** o gatilho de comprimento (`Quantos dias de férias eu tenho?`: 6 palavras, sem marcador, sem conjunção inicial). Nenhum request fixa o valor no caso ambíguo. |
| 10 | `k > 20`: a seção 5 (linha 186) lista como inválido apenas `k < 1`; a seção 6 (linha 364) diz `k < 1` **ou** `k > 20`. | Seguiu a seção 6, que é coerente com `maximum: 20` do descritor de `/capabilities` (linha 260). O request de `k = 21` espera 422. |
| 11 | `history_window = 0` com `history` preenchido: qual `reason`? A seção 4 aplica a janela no passo 4, antes da decisão do passo 5, o que implicaria conversa vazia e `primeiro_turno`; o FDD não afirma isso em lugar nenhum. | O teste exige apenas que `reason` pertença ao conjunto fechado e que a invariante 3 valha, sem fixar o valor. |

## BAIXA

| # | O que o FDD diz | O que o contrato diz | Onde |
|---|---|---|---|
| 12 | `meta.unresolved_labels` carrega os rótulos `[n]` não resolvíveis, e a invariante 4 depende dele. | `meta` é `object` com `additionalProperties: true`, sem declarar `unresolved_labels`. Conforme, mas indescobrível pelo contrato. | FDD seção 4, linha 158; seção 6, linhas 371 e 389 · contrato linhas 325 a 328 |
| 13 | Todos os exemplos de `Citation` trazem `page` e `excerpt`. | `Citation.required = [label, source]`; `page` e `excerpt` opcionais. | FDD seção 5, linhas 219 a 222 · contrato linhas 251 a 266 |
