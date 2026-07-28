# Guidelines

As guidelines que valem para este projeto vivem no workspace, porque são transversais aos
dez projetos e cópia diverge na primeira alteração:

- `../../../docs/guidelines/python-development-guidelines.md` — convenções de Python
- `../../../docs/guidelines/arquitetura-em-camadas.md` — estrutura em camadas. A seção 5
  diz explicitamente o que o Projeto 3 acrescenta: `KeywordRepository` (BM25) em
  `repository/` e `RerankService` em `service/`

Guideline **específica deste projeto** — se um dia existir — entra aqui.

## Stack confirmada

Confirmada com o autor em 28/07/2026 e revalidada contra o PyPI na mesma data. As versões
do guia (`../../../README.md`) continuam sendo as correntes, com uma exceção anotada
abaixo.

| Papel | Pacote | Versão | Nota |
|---|---|---|---|
| Framework RAG | `langchain` | 1.3.14 | |
| LLM + embeddings | `langchain-openai` | 1.4.1 | `gpt-4o-mini` + `text-embedding-3-small` |
| Chunking | `langchain-text-splitters` | 1.1.2 | |
| Integrações | `langchain-community` | 0.4.2 | |
| Busca densa **e** BM25 | `langchain-elasticsearch` | 1.0.0 | Elasticsearch em container |
| Reranking | `sentence-transformers` | 5.6.1 | Cross-encoder local **multilíngue**, CPU |
| Leitura de PDF | `pypdf` | 6.14.2 | |
| Configuração | `python-dotenv` | 1.2.2 | |
| API HTTP | `fastapi` | **0.140.9** | O guia fixa 0.140.0 e o Projeto 2 usa 0.140.1; há patch novo |
| Servidor ASGI | `uvicorn` | 0.51.0 | |
| Tipos | `mypy` | 2.3.0 | Obrigatório: os `Protocol` não são verificados em runtime |
| Testes | `pytest` | 9.1.1 | Escopo restrito — ver abaixo |

### As duas decisões que o autor confirmou

**Elasticsearch único, com o RRF escrito à mão.** O ES faz kNN denso *e* BM25 sobre o
mesmo índice, então existe **um** armazém e nenhuma sincronização entre dois. A fusão
Reciprocal Rank Fusion é escrita em Python, e não delegada ao retriever `rrf` nativo do
ES: fundir à mão é o entregável pedagógico do projeto, e mantém a fusão independente do
motor — trocar o armazém não deveria custar a estratégia de fusão. Vira ADR.

**Cross-encoder local, atrás de um `Protocol`.** O modelo confirmado inicialmente foi o
`cross-encoder/ms-marco-MiniLM-L-6-v2` do guia, e a validação o **substituiu por medição**
pelo multilíngue `cross-encoder/mmarco-mMiniLMv2-L12-H384-v1`: o modelo inglês, sobre corpus
em português, derrubava três acertos em dez. Ver a revisão do ADR-004 e
`docs/operations/README.md`. Roda na CPU e não gasta API. O `RerankService` é `Protocol` (a guideline do workspace já o
nomeia assim), de modo que a API de rerank da Cohere entre depois como **segunda
implementação**, sem reescrita — é exatamente o exercício 2 do guia, comparar qualidade
contra latência e custo. Vira ADR.

O guia lista `rank-bm25==0.2.2` no `pip install`, mas ele **não entra**: seria um segundo
mecanismo de BM25, in-process e sem persistência, competindo com o do Elasticsearch. Um
motor de busca por projeto.

## Testes: escopo deliberadamente estreito

Segue a decisão do Projeto 2 — pytest com dublês, nada tocando a API paga nem o
Elasticsearch real. O que muda é o alvo:

- **A fusão RRF.** É função pura, determinística, com saída exata e conferível à mão. O
  exercício 1 do guia manda variar o `k` (padrão 60), e variar parâmetro sem teste é como
  se regride a ordenação sem ninguém notar.
- **O funil de reranking.** Que a ordem final venha do score do cross-encoder e não da
  ordem de entrada, e que `top_n` corte de verdade.
- **A deduplicação de candidatos.** Documento que aparece nos dois rankings tem que somar
  os dois `1/(k+rank+1)`, não aparecer duas vezes.

O resto das camadas fica sem teste, como nos Projetos 1 e 2 — é estudo, não produção.
