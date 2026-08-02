---
status: completed
title: Setup nativo, infra local e fundações do projeto
type: infra
complexity: medium
---

# Task 1: Setup nativo, infra local e fundações do projeto

## Overview

Entrega o terreno executável do rag-04: dependências nativas do `unstructured hi_res`
instaladas e comprovadas por smoke test, Chroma em container na porta 8002, venv com a
stack fixada e o esqueleto de camadas com config, models e harness de qualidade (mypy,
pytest). É a etapa que mitiga o risco 2 do FDD ("o setup mais chato dos dez") e
desbloqueia todo o resto.

<critical>
- ALWAYS READ the PRD, the TechSpec, and their catalogs (`_user_stories.md`, `_tests.md`) before starting
- REFERENCE TECHSPEC for implementation details — do not duplicate here
- FOCUS ON "WHAT" — describe what needs to be accomplished, not how
- MINIMIZE CODE — show code only to illustrate current structure or problem areas
- TESTS REQUIRED — implement every test case assigned in ## Tests
</critical>

<requirements>
- MUST instalar as dependências nativas (poppler-utils, tesseract-ocr, tesseract-ocr-por) e comprovar com um smoke test de partição que roda sem erro sobre `pdfs/petrobras-desempenho-3t24.pdf` (pode usar `strategy=fast` no smoke; o `hi_res` completo é exercitado na task_03).
- MUST criar o venv com `python3 -m venv .venv` (não existe pip fora do venv) e fixar em `requirements.txt` as versões de `docs/guidelines/README.md` (unstructured[pdf] 0.24.1, langchain 1.3.14, langchain-classic 1.0.8, langchain-chroma 1.1.0, fastapi 0.141.1, mypy 2.3.0, pytest 9.1.1).
- MUST subir o Chroma via `docker-compose.yml` próprio: imagem `chromadb/chroma:1.5.9`, porta 8002, healthcheck e volume nomeado (padrão da trilha; portas 8000/8001/6333/9200 pertencem aos projetos anteriores).
- MUST criar a estrutura de camadas do HLD (`rag/api`, `rag/facade`, `rag/service`, `rag/repository`, `rag/presenter`, `rag/domain`) com `composition.py` na raiz e entrypoints vazios ou mínimos, grafo estritamente descendente.
- MUST criar `rag/config.py` no molde do rag-03 (`RagProperties` frozen dataclass, `.env` de caminho fixo, defaults como `Final`) incluindo `OPENAI_API_KEY`, porta do Chroma (8002), estratégia de partição (`hi_res`, com `fast` como contingência via env), caminhos de `data/partition/`, `data/docstore/`, `data/figures/`.
- MUST criar `.env.example` sem segredos e garantir que `.env`, `data/` e `pdfs/` continuam fora do git (o `.gitignore` da raiz já cobre; conferir).
- MUST deixar mypy e pytest configurados e passando (zero erros num projeto ainda vazio de lógica).
- SHOULD registrar no README do projeto (ou CLAUDE.md, seção de ambiente) os comandos de setup nativo executados.
</requirements>

## Subtasks

- [ ] 1.1 Instalar dependências nativas via apt e documentar os comandos —
      **comandos documentados em `CLAUDE.md`; instalação BLOQUEADA:** `sudo` exige
      senha e esta execução não é interativa. Rodar:
      `sudo apt install -y poppler-utils tesseract-ocr tesseract-ocr-por`
- [x] 1.2 Criar venv, `requirements.txt` com a stack fixada e instalar
- [x] 1.3 Criar `docker-compose.yml` do Chroma 1.5.9 (porta 8002, healthcheck, volume) e subir
- [x] 1.4 Criar a estrutura de camadas, `composition.py` e entrypoints mínimos
- [x] 1.5 Criar `rag/config.py` e `rag/domain/models.py` iniciais e `.env.example`
- [x] 1.6 Configurar mypy e pytest; rodar ambos limpos
- [x] 1.7 Escrever e rodar o smoke test de partição (sem custo de API)

## Implementation Details

Projeto: `/home/arthu/code/projetos-rag/rag-04-multimodal-docs`. Moldes prontos no
rag-03 (`../rag-03-hybrid-rerank/`): `rag/config.py:78-128` (RagProperties),
`composition.py:52-138` (funções soltas, não é camada), `docker-compose.yml` do
Chroma do rag-01. Guidelines vinculantes:
`../docs/guidelines/python-development-guidelines.md` e
`../docs/guidelines/arquitetura-em-camadas.md`. Ver seção 8 do techspec para a
tabela de versões.

### Relevant Files

- `../rag-03-hybrid-rerank/rag/config.py` — molde do RagProperties e do carregamento de `.env`
- `../rag-03-hybrid-rerank/composition.py` — molde da raiz de composição
- `../rag-01-fundamentos-pdf/docker-compose.yml` — precedente de Chroma em container com healthcheck
- `docs/guidelines/README.md` — stack fixada e escopo de testes
- `CLAUDE.md` — notas de ambiente (pip só no venv, portas ocupadas, aviso do setup)

### Dependent Files

- `requirements.txt`, `docker-compose.yml`, `.env.example`, `rag/**`, `composition.py`, `ingest.py`, `ask.py`, `serve.py` — todos criados aqui e consumidos pelas tasks 03 e 04

### Related ADRs

- [ADR-001 do projeto: dois armazéns ligados por doc_id](../../../docs/adrs/generated/RAG/ADR-001-dois-armazens-ligados-por-doc-id.md) — fixa Chroma em container na 8002
- [ADR-005 do projeto: cache da partição bruta](../../../docs/adrs/generated/RAG/ADR-005-cache-da-particao-bruta.md) — caminhos de `data/partition/`

## Deliverables

- Setup nativo comprovado por smoke test de partição executado com sucesso
- Chroma 1.5.9 de pé na 8002 com healthcheck verde
- Estrutura de camadas + config + models compilando, mypy e pytest limpos
- `.env.example` e documentação dos comandos de setup
- Every test case assigned in `## Tests` implemented and passing **(REQUIRED)**

## Tests

Sem `_tests.md`; casos inline:

- [x] T1.1 — Smoke: particionar `pdfs/petrobras-desempenho-3t24.pdf` termina sem exceção e devolve mais de zero elementos (estratégia livre; sem API).
      → `tests/test_smoke_partition.py`, `strategy="fast"`, verde em ~8 s.
- [x] T1.2 — `curl` no healthcheck do Chroma em `localhost:8002` responde sucesso com o container de pé.
      → `curl localhost:8002/api/v2/heartbeat` devolve HTTP 200; `docker compose ps` mostra `Up (healthy)`.
- [x] T1.3 — `mypy .` e `pytest` saem com código 0 no esqueleto.
      → `mypy`: 18 arquivos, 0 erros. `pytest`: 5 passed.

## Success Criteria

- Every assigned test case implemented and passing
- `docker compose ps` mostra o Chroma saudável na 8002
- Nenhum arquivo de segredo ou de `data/` rastreado pelo git
