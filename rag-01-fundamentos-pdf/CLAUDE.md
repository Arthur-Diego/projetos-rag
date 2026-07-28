# rag-01-fundamentos-pdf

Projeto 1 da trilha de estudo de RAG: o pipeline completo na forma mais simples —
carregar PDF → chunk → embed → armazenar → recuperar → responder. Chroma em container
(ADR-001, divergindo do guia). O guia da trilha inteira está em `../README.md`.

## Documentação

Todo o contexto deste projeto vive em `docs/`. Não há contexto em `contexts/`,
`.agents/contexts/` ou `rules/`.

- Gitflow: `docs/gitflow.md` (obrigatório antes de qualquer commit)
- PRD: `docs/prd.md`
- Guidelines: `../docs/guidelines/python-development-guidelines.md` (workspace, seguir
  sempre). Ver `docs/guidelines/README.md` — a guideline foi promovida ao workspace em
  27/07/2026, quando o Projeto 2 passou a precisar dela.
- Domínios: `docs/domains/rag/hld.md` (ler antes de mexer no domínio)
- FDDs: `docs/domains/rag/features/` (fonte de verdade de comportamento)
- Diagramas: `docs/domains/rag/diagrams/{mermaid,c4}/`
- Coleções HTTP: `docs/domains/rag/postman/`
- ADRs: `docs/adrs/generated/` (não contrariar sem novo ADR). **ADR-003 está superado
  pelo ADR-005** (o código é segregado, não são dois scripts autocontidos), e o
  **ADR-005 foi emendado pelo ADR-006** (camadas, código em inglês) **e pelo ADR-007**
  (facade de caso de uso).
- Relatório de diagramas: `docs/domains/rag/diagrams/README.md`
- Pesquisas: `docs/research/`
- Runbooks: `docs/operations/`
- Relatórios de análise: `docs/agents/`
- Contrato HTTP: `../docs/contracts/rag-api.yaml` (workspace)
- Arquitetura (fonte de verdade dos 10 projetos): `../docs/guidelines/arquitetura-em-camadas.md`
- Fluxo de trabalho: use `/dd` como porta de entrada

## Convenções deste repositório

- **`rag/` é organizado em camadas** (ADR-005 + 006 + 007): `facade/`, `service/`,
  `repository/`, `presenter/`, `domain/`, mais `config.py` e `exceptions.py` na raiz. **Código em inglês,
  mensagens ao usuário e documentação em português.**
- Nenhuma camada chama `sys.exit()` nem escreve em stdout: elas levantam `RagException`,
  e só o `ConsoleReporter` escreve. `ingest.py` e `ask.py` são composition roots.
- O grafo é estritamente descendente: entrypoint → facade → service → repository → domain.
- **As facades não conhecem terminal**: nada de `print`, `argparse` ou `sys.stderr`
  dentro de `rag/facade/`. Elas devolvem `Answer` e `IngestionReport`; só o
  `ConsoleReporter` e o `JsonPresenter` escrevem. Quebrar isso anula o ADR-007.
- **Três entrypoints, mesma lógica**: `ingest.py` e `ask.py` (CLI) e `serve.py`
  (HTTP, ADR-008). Todos usam as mesmas facades. Lógica de RAG na camada HTTP é
  sinal de que algo foi para o lugar errado.
- **A camada HTTP vive em `rag/api/`** (ADR-009), com `routes/` por recurso.
  `serve.py` só publica o app. Rota nova = arquivo em `routes/` + linha em `app.py`.
- **Dois modelos de injeção convivem**: manual nas CLIs, `Depends` no HTTP.
  Regra: container para o estável, construção explícita para o que vem do corpo
  da requisição.

- **`pdfs/` guarda os PDFs de entrada**, não `docs/`. O guia em `../README.md` usa
  `docs/` para isso; aqui `docs/` é design doc. O `ingest.py` lê de `pdfs/`.
- **`pdfs/fora-do-corpus/` nunca é indexado.** É o corpus de controle do teste negativo
  de grounding (critério 4 do PRD). O glob do `ingest.py` é `pdfs/*.pdf`, não recursivo —
  se alguém trocar por `**/*.pdf`, o teste negativo morre em silêncio.
- O índice vive no volume Docker `chroma_data`, não no repositório. É descartável:
  `docker compose down -v` + `python ingest.py` reconstrói.
- `.env` nunca é commitado. Use `.env.example` como modelo.

## Notas de ambiente

- Python 3.12.3. **Não existe `pip` no sistema** (nem binário, nem `python3 -m pip`) —
  ele só aparece dentro do venv: `python3 -m venv .venv && source .venv/bin/activate`.
- Docker funcionando: client 28.5.2, Docker Desktop 4.51.0, Compose v2.40.3. A seção 3.4
  do `../README.md` diz que o daemon não responde no WSL; essa informação está
  desatualizada.
- Chroma roda **em container**, não embarcado (ver ADR-001). Suba antes de usar os
  scripts: `docker compose up -d chroma`. Saúde: `curl localhost:8000/api/v2/heartbeat`.
  A API v1 do Chroma responde `410 Gone` — tutorial que use `/api/v1/` está desatualizado.
