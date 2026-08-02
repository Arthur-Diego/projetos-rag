# Divergências — FDD × `rag-api.yaml` 1.2.0

FDD: `docs/domains/rag/features/pipeline-multimodal-fdd.md` (v1.0, 2026-08-02).
Contrato publicado: `../../../../../docs/contracts/rag-api.yaml`, OpenAPI 3.1.0,
`info.version: 1.2.0` (linha 5).

**Contexto que muda a leitura:** o FDD especifica a versão **1.3.0**, decidida no
ADR-004 (`docs/adrs/generated/RAG/ADR-004-contrato-compartilhado-1-3-0.md`) como
evolução **estritamente aditiva** — e a publicação dela é a **etapa 2 do Build Order**
(FDD seção 11, linha 449), a ser feita antes do consumidor. Todas as rotas, verbos e
status que o FDD usa **já existem na 1.2.0**; o delta é de campos opcionais. Por isso
**nenhuma divergência é ALTA**: nada aqui faz a implementação bater em rota ou status
inexistente. Esta tabela é a checklist da etapa 2.

| # | Severidade | O que o FDD diz | O que o contrato 1.2.0 diz | Fontes |
|---|---|---|---|---|
| 1 | MEDIA | Contrato compartilhado na versão **1.3.0** (seção 5, linhas 162 e 163) | `info.version: 1.2.0` | FDD linha 162; yaml linha 5 |
| 2 | MEDIA | `SearchHit.kind` (`texto\|tabela\|imagem`) em cada hit do `/ask` (seção 5, linha 177; exemplo linha 199) | `SearchHit` não tem `kind`; propriedades param em `source`, `page`, `distance`, `score`, `provenance`, `excerpt` | FDD linhas 177–181; yaml linhas 305–343 |
| 3 | MEDIA | `SearchHit.content_html` com o HTML original quando `kind=tabela` (seção 5, linhas 178–180; exemplo linha 202) | Campo inexistente em `SearchHit` | FDD linhas 178–180; yaml linhas 305–343 |
| 4 | MEDIA | `elements` (`textos`, `tabelas`, `imagens`) no `IngestionReport` (seção 5, linhas 216–218; exemplo linha 236) | `IngestionReport` não tem `elements` | FDD linhas 216–218; yaml linhas 518–528 |
| 5 | MEDIA (ambiguidade) | `/health` reporta a contagem do docstore "em campo informativo do projeto", **sem nomear o campo** (seção 5, linha 249) | Nenhum campo de docstore no schema do `/health` (schema aberto: campo extra não viola) | FDD linha 249; yaml linhas 96–113 |
| 6 | MEDIA (ambiguidade) | `/ingest` responde 422 para "parâmetro inválido" sem exemplificar o parâmetro (seção 5, linha 214) | 422 declarado com exemplo de outro domínio ("overlap maior que size") | FDD linha 214; yaml linhas 266–270 |
| 7 | BAIXA | `/ingest` é idempotente-incremental: reconcilia em vez de recriar, não apaga o índice ao reingerir (seção 1, linhas 38 e 39; seção 5, linhas 216–218) | Descrição diz "Operação cara e **destrutiva**: apaga o índice anterior. O frontend deve confirmar antes de chamar" | FDD linhas 38–39, 216–218; yaml linhas 243–247 |
| 8 | BAIXA | Base URL local `http://127.0.0.1:8080` (seção 5, linhas 163 e 164) | `servers` declara `http://localhost:8080`, com a ressalva "cada projeto pode usar outra porta" | FDD linha 164; yaml linhas 80–82 |

## Notas por item

- **1–4** são exatamente os três acréscimos do ADR-004 mais o degrau de versão. A
  coleção testa o comportamento 1.3.0 (`kind` presente e no enum, `content_html` sse
  `kind=tabela`, `elements` no relatório): contra uma implementação fiel à 1.2.0
  publicada esses testes **falham**, e a falha é do contrato ainda não evoluído, não da
  coleção. Depois da etapa 2, os itens 1 a 4 desaparecem.
- **5** — o teste do `GET /health` (em `meta/` e em `erros/`) aceita qualquer chave cujo
  nome contenha `docstore` e falha listando as chaves recebidas. É lembrete, não
  especificação: quando a etapa 2 (ou a implementação da etapa 9) fixar o nome, o teste
  deve ser apertado.
- **6** — o único parâmetro de ingestão que o FDD declara é `descrever_imagens`
  (boolean, seção 5, linhas 257 e 258); o request `POST /ingest — 422 parametro
  invalido` usa um valor não-boolean por ser o único 422 determinístico sustentável.
- **7** — divergência só de descrição, mas com efeito de UX: o contrato 1.2.0 orienta o
  frontend a **confirmar antes de chamar** por ser destrutivo, e no rag-04 não é. A
  "nota de semântica idempotente" prevista no FDD (linhas 217 e 218) para a 1.3.0
  resolve exatamente isto.
- **8** — mesmo loopback e mesma porta; o próprio contrato admite variação por projeto.
  Registrada por completude.
