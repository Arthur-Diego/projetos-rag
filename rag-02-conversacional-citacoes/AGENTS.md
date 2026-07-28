# rag-02-conversacional-citacoes

Projeto 2 da trilha de estudo de RAG: o pipeline do projeto 1 acrescido das duas coisas
que todo RAG de produção precisa — **memória de conversa** (reescrita da pergunta usando
o histórico antes de buscar) e **citação verificável** (`[n]` rastreável até a página).
Qdrant em container, no lugar do Chroma (ADR-001). O guia da trilha inteira está em
`../README.md`, seção "Projeto 2".

## Documentação

Todo o contexto deste projeto vive em `docs/`. Não há contexto em `contexts/`,
`.agents/contexts/` ou `rules/`.

- Gitflow: `docs/gitflow.md` (obrigatório antes de qualquer commit)
- PRD: `docs/prd.md`
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
- Contrato HTTP: `../docs/contracts/rag-api.yaml`, **versão 1.1.0** (evoluída por este
  projeto, ADR-005)
- Projeto anterior, para comparação: `../rag-01-fundamentos-pdf/`
- Fluxo de trabalho: use `/dd` como porta de entrada

### ADRs deste projeto

| ADR | Decisão |
|---|---|
| 001 | Qdrant como armazém vetorial, em container |
| 002 | A conversa vive no cliente; o backend não guarda sessão |
| 003 | `Conversation` é objeto de valor em `domain`, sem `ConversationMemory` |
| 004 | Citação resolvida por referência explícita, não pela posição em `hits` |
| 005 | Contrato compartilhado evoluído para 1.1.0 com três campos opcionais |
| 006 | `chat.py` como quarto entrypoint, preservando `ask.py` de turno único |
| 007 | O estágio de resposta recebe a pergunta resolvida, com a literal ao lado |

Os ADR-001 a 009 do `rag-01-fundamentos-pdf` são precedente conceitual, **não** vínculo:
valem para aquele repositório.

## Convenções deste repositório

- **`rag/` é organizado em camadas**, conforme `../docs/guidelines/arquitetura-em-camadas.md`:
  `facade/`, `service/`, `repository/`, `presenter/`, `domain/`, `api/`, mais `config.py`
  e `exceptions.py` na raiz. **Código em inglês, mensagens ao usuário e documentação em
  português.**
- O grafo é estritamente descendente: entrypoint → facade → service → repository → domain.
  Nenhuma camada chama `sys.exit()` nem escreve em stdout: elas levantam `RagException`, e
  só o `ConsoleReporter` escreve.
- **O backend não guarda conversa** (ADR-002). Se aparecer um dicionário de sessão, um
  cache de conversa ou um `conversation_id` no servidor, o ADR-002 foi quebrado. A
  transcrição chega em `options.history` e vai embora com a resposta.
- **Não existe `ConversationMemory`** (ADR-003), apesar de a seção 5 da guideline do
  workspace prevê-lo. `Conversation` é `NamedTuple` em `domain/models.py`, e a janela de
  histórico é método dela.
- **`[n]` nunca é índice de `hits`** (ADR-004). A resolução passa por `citations`
  explícitas. Recusa (`refused: true`) tem `citations` vazia; recusa com citação é defeito.
- **Quatro entrypoints, mesmas facades** (ADR-006): `ingest.py`, `ask.py` (turno único),
  `chat.py` (REPL) e `serve.py` (HTTP). `ask.py` existe para a matriz de recusa ser
  scriptável — não o transforme em REPL. A montagem compartilhada entre `ask.py` e
  `chat.py` vive em `composition.py`, no nível dos entrypoints: **não é camada**, e mover
  para `rag/` reintroduziria a indireção que o ADR-007 do Projeto 1 alertou.
- **O prompt de resposta recebe a `RewriteDecision`, não a pergunta** (ADR-007). Passar a
  pergunta original faz o modelo recusar apesar de contexto correto, porque o pronome que
  a reescrita acabou de resolver volta a ficar sem antecedente. Foi defeito real,
  diagnosticado na validação.
- **`domain/` não importa LangChain.** `Page`, `Chunk` e `SearchHit` são tipos próprios; a
  conversão para `Document` acontece no adaptador. É o que permite a página virar 1-based
  em um lugar só.
- **A camada HTTP vive em `rag/api/`**, com `routes/` por recurso. `serve.py` só publica o
  app. Rota nova = arquivo em `routes/` + linha em `app.py`.
- **Dois modelos de injeção convivem**: manual nas CLIs, `Depends` no HTTP. Container para
  o estável, construção explícita para o que vem do corpo da requisição.
- **Nada do vocabulário do Qdrant atravessa o `VectorRepository`** (ADR-001): `payload`,
  `point_id` e `ScoredPoint` ficam no adaptador. O critério 7 do PRD cobra isso trocando
  Qdrant por Chroma numa linha.
- **`pdfs/` guarda os PDFs de entrada**, não `docs/`. Aqui `docs/` é design doc. O
  `ingest.py` lê `pdfs/*.pdf`.
- **`pdfs/fora-do-corpus/` nunca é indexado.** É o corpus de controle do teste negativo de
  grounding (critério 4 do PRD). O glob é `pdfs/*.pdf`, não recursivo — trocar por
  `**/*.pdf` mata o teste negativo em silêncio. Neste projeto o teste é mais exigente que
  no projeto 1: a recusa tem que **sobreviver ao follow-up**.
- O índice vive em volume Docker, não no repositório. É descartável:
  `docker compose down -v` + reindexação reconstrói.
- `.env` nunca é commitado. Use `.env.example` como modelo.

## Notas de ambiente

- Python 3.12.3. **Não existe `pip` no sistema** (nem binário, nem `python3 -m pip`) — ele
  só aparece dentro do venv: `python3 -m venv .venv && source .venv/bin/activate`.
- Docker Desktop 4.51.0, client 28.5.2, Compose v2.40.3, com integração WSL. Se o `docker`
  responder *"could not be found in this WSL 2 distro"*, o Docker Desktop está fechado ou
  com a integração desativada: abra e confira antes do primeiro `docker compose up`.
- Qdrant **v1.18.1** em container (ADR-001). Suba antes de usar os scripts:
  `docker compose up -d qdrant`. Painel em `http://localhost:6333/dashboard`.
  **A versão da imagem casa com o `qdrant-client` 1.18.0** que o `langchain-qdrant` traz;
  desalinhar volta a emitir aviso de incompatibilidade a cada conexão.
- O Chroma do `docker-compose.yml` está sob o profile `experimento` e escuta na **8001**,
  não na 8000: a 8000 é do container do Projeto 1, e os dois convivem. Só é necessário
  para o critério de aceite 7.
- Custo real do projeto até aqui: abaixo de US$ 0,50, incluindo três ingestões completas
  (617 chunks cada) e a validação com LLM. A reescrita acrescenta uma chamada por turno,
  que é o motivo do critério 5 do PRD.

## Estado da validação

Os onze critérios de aceite e sua evidência estão na **seção 9.1 do FDD**. Resumo: dez
atendidos, um parcial (conferência visual do frontend no navegador). Suíte: 63 testes,
mypy limpo em 38 arquivos, `newman` 86/91 asserções.

Scripts que produziram a evidência estão em `docs/operations/` e podem ser rodados de
novo. Eles gastam chamadas pagas.

**Limitação medida, e ela é o motivo de o Projeto 3 existir:** cerca de um terço das
perguntas factuais recebe recusa mesmo havendo passagem que as sustenta. Com `k=4` e busca
puramente densa sobre 617 chunks, o trecho certo frequentemente não entra nos quatro.
Busca híbrida e reranking resolvem isso no próximo projeto.
