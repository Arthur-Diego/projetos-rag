# ADR-006: Buscas densa e BM25 executadas em sequência, com paralelismo como decisão pendente

- **Status:** aceito
- **Data:** 2026-07-28
- **Domínio:** RAG
- **Decisores:** arthu

## Contexto

O funil dispara duas buscas independentes sobre o mesmo índice: kNN denso e BM25. Elas não
dependem uma da outra, então poderiam correr ao mesmo tempo. A pergunta é se vale.

O turno completo tem seis estágios, com ordens de grandeza muito diferentes:

| Estágio | Natureza | Ordem de grandeza esperada |
| --- | --- | --- |
| Reescrita | chamada de LLM, rede externa | centenas de ms a segundos |
| Embedding da query | chamada paga à OpenAI, rede externa | centenas de ms |
| kNN denso | HTTP a container local | dezenas de ms |
| BM25 | HTTP a container local | dezenas de ms |
| Fusão RRF | Python puro sobre dezenas de itens | sub ms |
| Rerank | cross encoder na CPU, 20 pares | centenas de ms |
| Geração | chamada de LLM, rede externa | segundos |

As duas buscas locais são, por essa leitura, a menor parcela do turno. Mas ela é
**estimativa**, não medição, e é exatamente isso que o `timings` por estágio existe para
resolver.

## Decisão

**As duas buscas rodam em sequência**, uma depois da outra, em código síncrono direto no
`RetrievalService`. `search_s` e `keyword_s` são medidos em separado.

**O paralelismo fica registrado como decisão pendente, com critério objetivo de
reabertura**, e não como possibilidade vaga. O autor registrou, com razão, que em um cenário
produtivo duas buscas sequenciais são latência somada sem motivo. A decisão de agora vale
para o contexto de agora, que é medição local com um usuário.

**Critério de reabertura:** quando `search_s + keyword_s` medidos passarem a representar
fração relevante do tempo total do turno, ou quando o projeto deixar de ser local e de um
usuário só.

**Implementação preferida quando reaberto:** `asyncio` ou threads dentro do
`RetrievalService`, mantendo os dois repositórios ignorantes da concorrência. O
`_msearch` do Elasticsearch fica descartado mesmo nesse cenário, pelo motivo abaixo.

## Alternativas consideradas

### `_msearch` do Elasticsearch, levando as duas buscas numa requisição

Rejeitada, agora e no futuro. Cortaria uma ida e volta HTTP local de verdade, o que é ganho
real e não teórico.

Recusada porque fura a fronteira que o [[ADR-001-elasticsearch-como-armazem-unico]] acabou de
desenhar. `VectorRepository` e `KeywordRepository` são adaptadores independentes do mesmo
motor; fazer os dois compartilharem uma única chamada exige que alguém acima deles monte um
corpo de requisição no vocabulário do Elasticsearch, ou que um repositório conheça a query do
outro. Nos dois casos o vocabulário do motor sobe de camada, que é precisamente o que o
`Protocol` existe para impedir. É otimização que se paga em acoplamento.

### Threads ou `asyncio` desde já

Rejeitada por ora, e é a alternativa que o autor sinalizou como preferível em cenário
produtivo. O ganho teórico é o maior das três.

Recusada agora porque introduz concorrência num projeto cujo objetivo declarado é enxergar o
mecanismo, e porque o ganho esperado é provavelmente indistinguível do ruído diante dos três
estágios de rede externa e do cross encoder. Otimizar antes de medir é justamente o hábito
que o exercício 3 do guia existe para desencorajar. Fica como decisão pendente com o critério
acima, não como recusa definitiva.

## Consequências

**Positivas**

- Código síncrono, direto e legível, no projeto em que ler o mecanismo é o objetivo.
- `search_s` e `keyword_s` medidos em separado dão a evidência que decide a pendência. A
  decisão de paralelizar passa a ser tomada com número, não com intuição.
- Os dois repositórios permanecem ignorantes um do outro e do motor compartilhado.

**Negativas**

- Latência somada onde poderia ser latência máxima. Em produção seria a escolha errada, e
  este ADR diz isso explicitamente para não ser lido como recomendação geral.
- A pendência exige disciplina: se ninguém olhar o `timings`, o critério de reabertura nunca
  dispara. Mitigado por a medição já fazer parte do entregável do projeto, a tabela.

## Referências

- `docs/domains/rag/hld.md`, "Considerações de escalabilidade e disponibilidade" e "ADRs e
  próximos passos"
- `../README.md`, seção "Projeto 3", exercício 3
- [[ADR-001-elasticsearch-como-armazem-unico]]
- [[ADR-002-rrf-em-python]]
