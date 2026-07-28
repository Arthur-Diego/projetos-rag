# Guidelines

As guidelines que valem para este projeto vivem no workspace, porque são transversais aos
dez projetos e cópia diverge na primeira alteração:

- `../../../docs/guidelines/python-development-guidelines.md` — convenções de Python
- `../../../docs/guidelines/arquitetura-em-camadas.md` — estrutura em camadas, seções 1 a
  6; a seção 5 diz explicitamente o que o Projeto 2 acrescenta (`ConversationMemory`,
  `QueryRewriteService`) e onde

Guideline **específica deste projeto** — se um dia existir — entra aqui.

## Stack confirmada

Confirmada com o autor em 27/07/2026 e revalidada contra o PyPI na mesma data. As versões
do guia (`../../../README.md`, conferidas em 25/07/2026) continuam sendo as correntes,
com uma exceção anotada abaixo.

| Papel | Pacote | Versão | Nota |
|---|---|---|---|
| Framework RAG | `langchain` | 1.3.14 | |
| LLM + embeddings | `langchain-openai` | 1.4.1 | `gpt-4o-mini` + `text-embedding-3-small` |
| Chunking | `langchain-text-splitters` | 1.1.2 | |
| Integrações | `langchain-community` | 0.4.2 | |
| Vector store | `langchain-qdrant` | 1.1.0 | Qdrant em container |
| Leitura de PDF | `pypdf` | 6.14.2 | |
| Configuração | `python-dotenv` | 1.2.2 | |
| API HTTP | `fastapi` | **0.140.1** | O guia fixa 0.140.0; há patch novo no PyPI |
| Servidor ASGI | `uvicorn` | 0.51.0 | |
| Tipos | `mypy` | 2.3.0 | Obrigatório: os `Protocol` não são verificados em runtime |
| Testes | `pytest` | 9.1.1 | Escopo restrito — ver abaixo |

`langchain-chroma` 1.1.0 entra como dependência de desenvolvimento para o exercício 3
(troca de vector store, critério 7 do PRD). `qdrant-client` 1.18.0 vem transitivamente
por `langchain-qdrant`; fixe-o só se houver conflito.

## Testes: escopo deliberadamente estreito

Decidido com o autor: pytest cobre **a matriz de recusa e a reescrita**, com dublês
(`FakeLLM`, `FakeVectorRepository`) — nada toca a API paga.

O motivo é o critério 4 do PRD: a recusa precisa sobreviver ao follow-up, o que é uma
matriz de casos (turnos 1/2/3 × com e sem reescrita × dentro e fora do corpus). Conferir
isso à mão a cada mudança cansa, e o que cansa deixa de ser conferido. O resto das
camadas fica sem teste, como no Projeto 1 — é estudo, não produção.
