# Task Memory: task_04.md

Keep only task-local execution context here. Do not duplicate facts that are obvious from the repository, task file, PRD documents, or git history.

## Objective Snapshot

Lado da leitura entregue e VALIDADO CONTRA O CORPUS REAL: `POST /ask`,
`GET /health` (com dessincronia), `GET /capabilities`, `RetrievalService`,
`PromptBuilder`, `GenerationService`, `QueryFacade`, `ResetFacade`, presenters,
`ask.py` e `reset.py`. mypy limpo, 76 testes verdes, Postman `meta/ingest/ask`
com 37 asserções verdes.

## Important Decisions

- **`SearchHit` já carrega o original**, então não existe um par
  `(hit, unit)` circulando: para texto e imagem original e representação
  coincidem (ADR-002), e só a tabela tem os dois campos (`excerpt` = resumo,
  `content_html` = HTML). `format_context` deriva o original do próprio hit.
  Sem isso, a prova "o HTML chegou ao prompt" dependeria de inspecionar o
  docstore de novo.
- **`IndexMatch` (doc_id + distância) é o que o `VectorRepository.search`
  devolve**, nunca conteúdo. `include=["distances"]` e mais nada: trazer o
  documento do índice convidaria alguém a montar o prompt com o resumo.
- **`score = 1 - distância`**, convertido num lugar só (`RetrievalService._to_hit`).
  O domínio não tem campo `distance` (fixado na task_01), e o contrato declara
  as duas escalas com sentidos opostos.
- **Armazéns vazios são `ok` no `/health`, não `degraded`.** A seção 5 do FDD
  reserva `degraded` para incompatibilidade entre os armazéns ou docstore
  inacessível; índice vazio é 409 do `/ask`. Diverge do rag-03, que reportava
  `degraded` para índice vazio.
- **`degraded_reason`** carrega a evidência e a receita, que MUDA de lado:
  índice na frente pede `reset.py`; docstore na frente pede `ingest.py`.
- **Reset apaga índice ANTES do docstore**, inverso exato da gravação: entre as
  duas chamadas existe "nada buscável", nunca "índice sem originais".
- **`reset.py` na raiz** (não em `docs/operations/`): é entrypoint de primeira
  classe como `ingest.py`, e entrou na lista de `files` do mypy.
- **`timings` publica `search_s`, `dense_s`, `docstore_s`, `generation_s`.**
  `docstore_s` é extra do projeto (o contrato permite): sem ele o custo do
  estágio novo — resolver originais — não seria atribuível.
- **Porta `IngestionLog` reusada na consulta**, como a memória compartilhada
  mandava. O nome ficou estreito para o que ela faz hoje; não foi renomeada
  para não espalhar a mudança por dez arquivos.

## Learnings

- **A pergunta-critério do guia na forma nua não recupera a tabela.** "Qual foi
  a receita no 3T24?" põe a tabela da p.5 em 7º lugar com `k=10`, atrás de dez
  trechos de texto, e a resposta é recusa. Com "receita de vendas ... Petrobras
  ... em milhões de reais" e `k=8` a tabela sobe para 3º e a resposta sai
  correta (R$ 129.582 milhões, valor literal da célula). É a EC-3 da US-006 e o
  risco 3 do FDD — medida de RECUPERAÇÃO, não defeito do pipeline. Quantificar
  é da task_06.
- Os resumos de tabela gerados começam todos com a mesma prosa genérica ("A
  tabela apresenta dados financeiros da empresa..."), o que explica o drift: o
  prefixo comum dilui o sinal específico no embedding.
- `TestClient.app` é tipado como app ASGI cru: `dependency_overrides` nele não
  passa no mypy. Separar `_app() -> FastAPI` de `_client() -> TestClient` no
  teste resolve sem `type: ignore`.
- `# type: ignore[no-untyped-def]` precisa ficar na linha do `def`; numa
  assinatura multilinha ele vai para o lugar errado e o mypy acusa
  `unused-ignore`. Anotar de verdade (`tmp_path: Path`) é mais barato.

## Files / Surfaces

- Novos em `rag/`: `service/retrieval/{__init__,retrieval_service}.py`,
  `service/{prompt_builder,generation_service,health_checker}.py`,
  `facade/{query_facade,reset_facade}.py`, `api/descriptor.py`,
  `api/routes/{ask,meta}.py`.
- Estendidos: `domain/models.py` (`IndexMatch`, `RetrievalResult`,
  `ResetReport`), `repository/vector_repository.py` (`search`, `reset`),
  `repository/docstore_repository.py` (`reset`), `api/{app,dependencies,
  schemas}.py` (`read_int`, `HealthyProperties`, `Generation`, `AskRequest`),
  `presenter/{json_presenter,console_reporter}.py`, `composition.py`.
- Raiz: `ask.py` preenchido, `reset.py` novo, `pyproject.toml` (mypy files).
- Testes novos: `test_prompt_builder.py`, `test_retrieval.py`,
  `test_json_presenter.py`, `test_api_ask.py`, `test_health.py`,
  `test_reset.py`; `tests/fakes.py` e `tests/conftest.py` estendidos.
- Docs: `docs/domains/rag/postman/README.md` (execução registrada) e as
  variáveis da coleção preenchidas.

## Errors / Corrections

- **Incidente de custo, e a correção mais importante desta task.** O `.env` do
  autor passou a existir (02/08 16:24). O teste da task_03
  `test_configuracao_ausente_e_500_e_nao_503` apagava `OPENAI_API_KEY` do
  ambiente, mas `config.load()` chama `load_dotenv`, que PREENCHE variável
  ausente: a chave voltou do arquivo, a rota seguiu e um `pytest` sem argumento
  rodou a ingestão REAL do corpus — `hi_res` completo e ~207 mil tokens de
  resumo e visão, contra os armazéns de produção do projeto. Corrigido com
  fixture autouse em `conftest.py` que neutraliza `load_dotenv` para a suíte
  inteira. Sintoma colateral que denuncia a regressão se ela voltar: a suíte
  passou de 115 s para 12 s.
- Primeira versão do `FakeVectors.count()` devolvia `len(matches) or
  len(units)`, o que fazia o índice "existir" só por haver resultado de busca
  preparado. Corrigido para `len(units)`; os testes de consulta populam os dois.

## Ready for Next Run

- **O corpus está ingerido de verdade** nos dois armazéns (50 unidades: 36
  textos, 9 tabelas, 5 imagens) e o Chroma da 8002 está no ar. **Não rode
  `reset.py`** sem intenção: reingerir custa o `hi_res` (o cache cobre) e uma
  chamada paga por tabela e por imagem (o cache NÃO cobre).
- `reset.py` não foi executado contra os armazéns reais, justamente por isso.
  Está coberto por T4.7 com dublês.
- Da pasta `erros/` da coleção, faltam provocar 409 (exige reset), 500 (exige
  subir sem chave) e os três 503 (exigem derrubar o Chroma). Todos têm
  cobertura equivalente no pytest.
- Pendência menor registrada no README da coleção: apertar os dois testes
  frouxos do `/health` para o nome exato `docstore_originals`.
