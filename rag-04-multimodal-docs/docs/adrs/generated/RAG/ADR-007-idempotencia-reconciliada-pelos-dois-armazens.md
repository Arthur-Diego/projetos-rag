# ADR-007: Idempotência reconciliada pelos DOIS armazéns

## Status

Aceito (2026-08-02, pós-implementação; estende ADR-001 e ADR-003)

## Contexto

O ADR-003 fixou a idempotência por `doc_id` determinístico e o ADR-001 fixou a
ordem de gravação (original no docstore antes da representação no índice). A
combinação dos dois cria um estado alcançável que a decisão original não
cobria: falha entre as duas gravações (embeddings fora do ar, processo morto)
deixa original pago no docstore e nada no índice. Com a idempotência decidida
apenas pelo docstore, a reexecução via `known()` pulava essas unidades para
sempre: o `/ask` respondia 409 eternamente e a receita do `/health` ("rode
`ingest.py` de novo") não consertava — só o reset, repagando todo o
enriquecimento, contra o próprio ADR-003. A rodada de revisão 001 (issue 001)
encontrou o defeito; a promessa do FDD (seção 4, "a reexecução retoma do que
falta") existia sem implementação.

## Decisão

A idempotência da ingestão consulta os DOIS armazéns:

1. `doc_id` ausente no docstore: unidade nova — enriquece, grava nos dois
   (comportamento do ADR-003).
2. `doc_id` presente no docstore E no índice: reaproveitada — não paga nada.
3. `doc_id` presente no docstore e AUSENTE no índice: retomada de falha
   parcial — re-indexa a partir do original persistido (a `representation`
   enriquecida vive no docstore), repagando apenas o embedding, nunca o
   enriquecimento.

Para isso o `VectorRepository` ganha `known(doc_ids) -> set[str]`, a metade
vetorial da pergunta que o docstore já respondia.

## Alternativas consideradas

### Manter a decisão só pelo docstore e consertar via reset

- Rejeitada: transforma toda falha parcial em reingestão paga integral,
  contrariando a economia que o ADR-003 existe para garantir, e faz a receita
  publicada pelo `/health` mentir.

### Gravação transacional entre os dois armazéns

- Rejeitada: não existe transação entre Chroma e filesystem; simular com
  compensação adicionaria complexidade permanente para tratar um estado que a
  reconciliação resolve com uma consulta em lote por execução.

## Consequências

- Positivas: a receita do `/health` volta a ser verdadeira; falha parcial custa
  um embedding em lote, não o corpus; o cenário tem teste dedicado
  (`tests/test_ingestion_resume.py`).
- Negativas: uma consulta em lote a mais ao índice por ingestão (barata; só
  para os ids já conhecidos no docstore).

## Referências

- FDD `docs/domains/rag/features/pipeline-multimodal-fdd.md`, seção 4
- `rag/facade/ingestion_facade.py` (reconciliação), `rag/repository/vector_repository.py` (`known`)
- Rodada de revisão `.compozy/tasks/pipeline-multimodal/reviews-001/issue_001.md`
