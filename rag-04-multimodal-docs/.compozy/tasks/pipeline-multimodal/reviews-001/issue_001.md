---
provider: manual
pr:
round: 1
round_created_at: 2026-08-02T20:17:51Z
status: resolved
file: rag-04-multimodal-docs/rag/facade/ingestion_facade.py
line: 108
severity: high
author: claude-code
provider_ref:
---

# Issue 001: Retomada pos-falha parcial nunca completa o indice vetorial

## Review Comment

A secao 4 do FDD promete que a reexecucao apos falha no meio da ingestao retoma do que falta. A facade filtra unidades novas apenas por docstore.known() (linhas 108-109). No estado docstore=N / indice=0 (falha ou morte do processo entre docstore.put e vectors.add, exatamente a janela que o IndexingService descreve), a reexecucao ve tudo como known, calcula novos=[] e nunca indexa o lado vetorial. O /ask devolve 409 para sempre e a receita do /health (rode ingest.py de novo, health_checker.py:84-90) nao conserta; o unico caminho e reset.py, que repaga todo o enriquecimento, contrariando o ADR-003. A docstring do IndexingService (a reexecucao o completa sem repagar nada) afirma comportamento nao implementado. Confirmado por dois revisores independentes e por leitura direta.

Correcao sugerida: reconciliar contra os DOIS armazens - adicionar um known(ids) ao VectorRepository e re-indexar a partir do docstore (a representation esta persistida la, docstore_repository.py:73) as unidades presentes no docstore e ausentes no Chroma; so o embedding e repago, sem chamada de enriquecimento. Adicionar teste do cenario (o estado e produzivel com o fake fail_on_add de T3.7).

## Triage

- Decision: `VALID`
- Notes: Confirmado por dois revisores e leitura direta: novos filtrado so por docstore.known(); estado docstore>indice e irrecuperavel sem reset. Fix: known(ids) no VectorRepository + reconciliacao na facade + teste de retomada.
- Resolution: Corrigido: VectorRepository.known(ids) novo (Protocol + Chroma get(ids, include=[]) + fake); IngestionFacade reconcilia contra os dois armazens e re-indexa do docstore. Teste novo tests/test_ingestion_resume.py::test_reingestao_apos_falha_parcial_completa_o_indice_sem_repagar prova: indice completado, model.calls inalterado.
