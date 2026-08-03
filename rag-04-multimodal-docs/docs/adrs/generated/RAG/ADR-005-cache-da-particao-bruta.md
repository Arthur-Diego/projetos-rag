# ADR-005: Cache da partição bruta como fronteira entre o estágio local e o estágio pago

- **Status:** aceito
- **Data:** 2026-08-01
- **Domínio:** RAG
- **Decisores:** arthu

## Contexto

A ingestão deste projeto tem duas metades de natureza diferente. A partição (`hi_res`)
é local e gratuita, mas custa minutos de CPU por PDF: modelo de layout, reconstrução de
estrutura de tabela e OCR. O enriquecimento (resumos e descrições) é rápido de disparar
mas custa chamadas pagas. Durante o desenvolvimento, o que mais se itera é justamente a
segunda metade: o prompt de resumo, o que indexar por elemento, o roteamento por
categoria. Sem uma fronteira entre as metades, cada ajuste de prompt repagaria os
minutos do `hi_res` para chegar aos mesmos elementos de sempre.

## Decisão

**O resultado bruto da partição é persistido em `data/partition/`** (fora do git, como
todo `data/`), chaveado pelo PDF de origem. O `PartitionService` consulta o cache antes
de rodar o `hi_res`; acerto de cache pula direto ao roteamento por categoria.

A fronteira separa exatamente o estágio local do estágio pago:

- Iterar no prompt de resumo, no roteamento ou na indexação: **não** roda `hi_res` de
  novo (cache) e **não** repaga o que não mudou (idempotência do
  [[ADR-003-doc-id-deterministico]]).
- Trocar o PDF, a estratégia de partição ou o modelo de layout: invalida o cache
  daquele documento, e só dele.

O cache economiza **tempo**; a idempotência por `doc_id` economiza **dinheiro**. As
duas peças fecham o ciclo de iteração barata sobre uma ingestão cara.

## Alternativas consideradas

### Pipeline sempre de ponta a ponta, sem cache

Rejeitada. É mais simples e sempre correta, mas transforma cada iteração de prompt numa
espera de minutos para reproduzir um resultado que já existia byte a byte. O guia
declara a ingestão deste projeto como a mais cara da trilha; atrito de iteração sobre
ela é custo de desenvolvimento real, não conveniência.

### Cachear depois do enriquecimento (resumos prontos)

Rejeitada como cache primário. O ponto de iteração dominante é o próprio
enriquecimento; cachear depois dele congelaria exatamente o que se quer variar. A
economia dos resumos já é entregue pela idempotência do `doc_id`, que invalida por
conteúdo em vez de por estágio.

## Consequências

**Positivas**

- Iterar na metade pedagogicamente interessante do pipeline custa segundos, não minutos.
- O cache é descartável e reconstruível (`data/` inteiro é): apagar nunca é perda, só
  custo de recomputar.
- O formato persistido documenta de graça o que o `hi_res` devolve, útil para a
  inspeção pós-partição exigida pelo risco 1 do HLD.

**Negativas**

- Um estado intermediário a mais para raciocinar: partição desatualizada em relação a
  um PDF trocado no lugar, com o mesmo nome, serviria elementos velhos. Mitigação: a
  chave do cache inclui hash do arquivo PDF, não só o nome.
- Serialização dos elementos do `unstructured` vira dependência de formato interno da
  biblioteca; versão nova pode invalidar o cache. Aceito: invalidar cache é barato por
  definição.

## Referências

- `docs/domains/rag/hld.md`, "Riscos arquiteturais", risco 6
- [[ADR-003-doc-id-deterministico]]
