# rag-04-multimodal-docs

Projeto 4 da trilha de estudo de RAG: **documentos multimodais** — extrair tabelas e
imagens de PDFs complexos com `unstructured` (`hi_res`) e o padrão **multi-vector
retriever**: indexar o **resumo** em linguagem natural (que embeda bem) e devolver ao
LLM o **original** inteiro (tabela em HTML, imagem descrita). Ataca a limitação vista
nos projetos anteriores: o `PyPDFLoader` transforma tabela em sopa de números e ignora
imagens — metade da informação de um relatório real nunca chega ao índice.

O guia da trilha inteira está em `../README.md`, seção "Projeto 4".

> **Estado: pipeline completo e medido (tasks 01 a 06 do PRD `pipeline-multimodal`, 02/08/2026).**
> Pipeline de ponta a ponta no ar: ingestão multimodal com cache e idempotência,
> consulta com resolução de originais, `POST /ask`, `POST /ingest`, `GET /health`
> (com dessincronia) e `GET /capabilities`; `ingest.py`, `ask.py`, `reset.py` e
> `serve.py`. Corpus real ingerido (50 unidades, 9 tabelas). mypy limpo, 104 testes
> verdes. O frontend genérico (`../frontend/`) consome a 1.3.0: tabela real
> sanitizada, selo de `kind` e `elements` no relatório (20 testes, `npm test`).
> Rodada de revisão 001 remediada; ADR-007 e ADR-008 nasceram dela.
> Medição publicada em `docs/operations/README.md`: tabela 1/5 com `k=8` e
> **5/5 com `k=20`**, sempre pelo `content_html` — o gargalo é o ranking dos
> resumos, não a indexação.

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
| 007 | Idempotência reconciliada pelos DOIS armazéns: retomada de falha parcial re-indexa do docstore sem repagar enriquecimento |
| 008 | `content_html` só com HTML estrutural: tabela detectada e não estruturada degrada para `excerpt` |

## Setup

Comandos do setup, na ordem. Executados em 02/08/2026, exceto onde marcado.

```bash
# 1. Dependencias nativas do hi_res.  Executado; hi_res detectou 9 tabelas no corpus.
sudo apt install -y poppler-utils tesseract-ocr tesseract-ocr-por

# 2. venv + stack fixada (nao existe pip fora do venv)
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt

# 3. Chroma das representacoes, porta 8002
docker compose up -d chroma
curl localhost:8002/api/v2/heartbeat      # {"nanosecond heartbeat": ...}

# 4. Qualidade (ambos rodam sem argumento; a configuracao vive no pyproject.toml)
.venv/bin/python -m mypy
.venv/bin/python -m pytest
```

O passo 1 rodou, e o `hi_res` funciona: a partição do corpus detectou **9
tabelas** e extraiu 5 imagens. Sem ele, `PARTITION_STRATEGY=hi_res` falharia — o
`hi_res` precisa do poppler para rasterizar a página e do tesseract para o OCR —
e a contingência do risco 2 do FDD é `PARTITION_STRATEGY=fast` no `.env`, que
sobe o pipeline sem detectar tabela nenhuma.

O smoke test de partição (`tests/test_smoke_partition.py`) continua rodando com
`strategy="fast"`, de propósito: ele prova que a biblioteca importa e que o PDF é
legível, **não** que o `hi_res` funciona. `hi_res` de verdade é caro demais para
uma suíte.

Verificação das nativas, antes de confiar no `hi_res`:

```bash
pdftoppm -v && tesseract --list-langs | grep por
```

## Rodar

```bash
.venv/bin/uvicorn serve:app --host 127.0.0.1 --port 8080   # as 4 rotas da 1.3.0
.venv/bin/python ingest.py                                 # idempotente: nao repaga
.venv/bin/python ask.py "Qual foi a receita de vendas da Petrobras no 3T24?" --k 8
.venv/bin/python reset.py                                  # zera os DOIS armazens
```

**`reset.py` custa dinheiro depois.** Ele preserva o cache de partição (ADR-005),
então o `hi_res` não é repago, mas desfaz a idempotência do ADR-003: a próxima
ingestão paga de novo um resumo por tabela e uma descrição por imagem.

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
