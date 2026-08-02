# rag-04-multimodal-docs

Projeto 4 da trilha de estudo de RAG: **documentos multimodais** — extrair tabelas e
imagens de PDFs complexos com `unstructured` (`hi_res`) e o padrão **multi-vector
retriever**: indexar o **resumo** em linguagem natural (que embeda bem) e devolver ao
LLM o **original** inteiro (tabela em HTML, imagem descrita). Ataca a limitação vista
nos projetos anteriores: o `PyPDFLoader` transforma tabela em sopa de números e ignora
imagens — metade da informação de um relatório real nunca chega ao índice.

O guia da trilha inteira está em `../README.md`, seção "Projeto 4".

> **Estado: terreno documentado, sem código.** HLD e seis ADRs prontos (01/08/2026);
> a primeira feature entra via `dd-feature`. As convenções de código entram aqui
> quando houver código que as exercite.

## Documentação

Todo o contexto deste projeto vive em `docs/`. Não há contexto em `contexts/`,
`.agents/contexts/` ou `rules/`.

- Gitflow: `docs/gitflow.md` (obrigatório antes de qualquer commit)
- Configuração do fluxo DD: `docs/dd.md` (sem Trello e sem `docs/prd.md` — ver lá o porquê)
- Guidelines (workspace, seguir sempre):
  `../docs/guidelines/python-development-guidelines.md` e
  `../docs/guidelines/arquitetura-em-camadas.md`. Stack fixada e escopo de testes em
  `docs/guidelines/README.md`.
- Domínios: `docs/domains/rag/hld.md` (ler antes de mexer no domínio)
- FDDs: `docs/domains/rag/features/` (fonte de verdade de comportamento)
- Diagramas: `docs/domains/rag/diagrams/{mermaid,c4}/`
- Coleções HTTP: `docs/domains/rag/postman/`
- ADRs: `docs/adrs/generated/RAG/` (não contrariar sem novo ADR)
- Pesquisas: `docs/research/`
- Runbooks: `docs/operations/`
- Relatórios de análise: `docs/agents/`
- Contrato HTTP: `../docs/contracts/rag-api.yaml`
- Projetos anteriores, para comparação: `../rag-01-fundamentos-pdf/`,
  `../rag-02-conversacional-citacoes/` e `../rag-03-hybrid-rerank/`
- Fluxo de trabalho: use `/dd` como porta de entrada

Os ADRs dos projetos anteriores são **precedente conceitual, não vínculo**: valem para
aqueles diretórios. Decisão herdada precisa de ADR próprio aqui.

### ADRs deste projeto

| ADR | Decisão |
|---|---|
| 001 | Dois armazéns ligados por `doc_id`: Chroma em container (8002) + `LocalFileStore`; docstore é a fonte de verdade |
| 002 | Multi-vector seletivo: texto direto; resumo só para tabela e imagem (diverge do diagrama do guia) |
| 003 | `doc_id` determinístico por hash de conteúdo: ingestão idempotente, não repaga o que não mudou |
| 004 | Contrato compartilhado 1.3.0, aditivo: `kind`, `content_html`, `elements` |
| 005 | Cache da partição bruta em `data/partition/`: fronteira entre estágio local e estágio pago |
| 006 | Descritor de imagens atrás de `Protocol`: visão da OpenAI hoje, modelo local previsto |

## Notas de ambiente

O que já se sabe do guia e dos projetos anteriores:

- Python 3.12.3. **Não existe `pip` no sistema** (nem binário, nem `python3 -m pip`) — ele
  só aparece dentro do venv: `python3 -m venv .venv && source .venv/bin/activate`.
- Docker Desktop com integração WSL. Se o `docker` responder *"could not be found in this
  WSL 2 distro"*, o Docker Desktop está fechado ou com a integração desativada.
- Portas já ocupadas pelos projetos anteriores: 8000 (Chroma do Projeto 1), 8001 (Chroma
  sob profile `experimento` do Projeto 2), 6333 (Qdrant do Projeto 2), 9200
  (Elasticsearch do Projeto 3).
- **Suba um serviço por vez** e derrube os containers dos projetos anteriores antes de
  trabalhar neste.
- O guia avisa: este é **o setup mais chato dos dez**. `unstructured[pdf]` puxa
  dependências nativas pesadas (poppler, tesseract, detectron) e exige
  `sudo apt install -y poppler-utils tesseract-ocr tesseract-ocr-por`. O `hi_res` leva
  **minutos por PDF** — a ingestão é cara de rodar, planeje persistência de acordo.
- `pdfs/` guarda os PDFs de entrada; figuras extraídas vão para `data/figures/` (fora do
  git). `.env` nunca é commitado — use `.env.example` como modelo.
