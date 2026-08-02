# Guidelines

As guidelines que valem para este projeto vivem no workspace, porque são transversais aos
dez projetos e cópia diverge na primeira alteração:

- `../../../docs/guidelines/python-development-guidelines.md` — convenções de Python
- `../../../docs/guidelines/arquitetura-em-camadas.md` — estrutura em camadas

Guideline **específica deste projeto** — se um dia existir — entra aqui.

## Stack confirmada

Confirmada com o autor em 01/08/2026 e revalidada contra o PyPI na mesma data. Regra
adotada: **versões do guia + patches seguros** — o `unstructured` fica na versão fixada
pelo guia (0.25.0 saiu depois da conferência de julho/2026 e é a dependência mais frágil
dos dez projetos); FastAPI e uvicorn sobem para o patch corrente, como o rag-03 fez.

| Papel | Pacote | Versão | Nota |
|---|---|---|---|
| Framework RAG | `langchain` | 1.3.14 | |
| LLM + embeddings + visão | `langchain-openai` | 1.4.1 | `gpt-4o-mini` (texto **e** visão) + `text-embedding-3-small` |
| Vector store | `langchain-chroma` | 1.1.0 | Chroma **em container** (`chromadb/chroma:1.5.9`, porta 8002), via `HttpClient` |
| Integrações | `langchain-community` | 0.4.2 | |
| Multi-vector retriever | `langchain-classic` | 1.0.8 | `MultiVectorRetriever` e stores de documentos moram aqui |
| Particionamento de PDF | `unstructured[pdf]` | **0.24.1** | Fixado pelo guia; `hi_res` + `infer_table_structure` |
| Configuração | `python-dotenv` | 1.2.2 | |
| API HTTP | `fastapi` | 0.141.1 | Patch corrente sobre a linha do guia |
| Servidor ASGI | `uvicorn` | 0.52.1 | |
| Tipos | `mypy` | 2.3.0 | Obrigatório, como nos projetos anteriores |
| Testes | `pytest` | 9.1.1 | Escopo restrito — ver abaixo |

Dependências nativas via apt: `poppler-utils`, `tesseract-ocr`, `tesseract-ocr-por`.
O guia avisa que este é o setup mais pesado dos dez (o `hi_res` usa modelo de layout e
leva minutos por PDF).

### Decisões de escopo confirmadas junto com a stack

**API HTTP mantida.** O rag-04 segue o padrão dos projetos 1–3: FastAPI servindo o
contrato compartilhado `../../../docs/contracts/rag-api.yaml`, consumível pelo frontend
genérico. Se a resposta multimodal pedir campos novos, o contrato evolui de forma
aditiva, como o rag-03 fez ao criar a 1.2.0.

**Chroma em container, não embarcado.** O guia sugere o Chroma embarcado neste projeto,
mas o autor decidiu (01/08/2026) manter o padrão dos projetos 1 a 3: vector store em
container com healthcheck e volume, `docker-compose.yml` próprio. Mesma imagem já
validada na trilha (`chromadb/chroma:1.5.9`), porta **8002** — 8000 e 8001 pertencem aos
projetos 1 e 2. O docstore dos originais (e sua persistência) é decisão de HLD/ADR, não
de stack.

## Testes: escopo deliberadamente estreito

Segue a decisão dos projetos anteriores — pytest com dublês, nada tocando a API paga nem
o particionamento `hi_res` real (lento demais para suíte). Os alvos exatos saem do HLD e
do FDD da primeira feature; os candidatos naturais são a lógica determinística do padrão
multi-vector: o roteamento de elementos por categoria (Table / NarrativeText / Image) e
a correspondência resumo→original via `doc_id` (achar o resumo tem que devolver o
original certo). O resto das camadas fica sem teste, como nos projetos 1 a 3 — é estudo,
não produção.
