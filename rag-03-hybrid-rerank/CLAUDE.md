# rag-03-hybrid-rerank

Projeto 3 da trilha de estudo de RAG: **busca híbrida (BM25 + densa) com fusão RRF** e
**reranking com cross-encoder**. Ataca a limitação medida no Projeto 2 — cerca de um terço
das perguntas factuais recebia recusa mesmo havendo passagem que as sustentava, porque com
`k=4` e busca puramente densa o trecho certo não entrava nos quatro.

O guia da trilha inteira está em `../README.md`, seção "Projeto 3".

> **Estado: funil implementado e medido contra Elasticsearch real.** 107 testes, mypy
> limpo. A tabela de medição existe e está em `docs/operations/README.md`, junto com as
> quatro pendências de validação. Leia-a antes de tirar conclusões sobre busca híbrida:
> **neste corpus a densa pura ainda ganha**, e o motivo está documentado.

## Documentação

Todo o contexto deste projeto vive em `docs/`. Não há contexto em `contexts/`,
`.agents/contexts/` ou `rules/`.

- Gitflow: `docs/gitflow.md` (obrigatório antes de qualquer commit)
- Configuração do fluxo DD: `docs/dd.md` (sem Trello; **e sem `docs/prd.md`** — ver lá o
  porquê da diferença em relação aos projetos 1 e 2)
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
- Projetos anteriores, para comparação: `../rag-01-fundamentos-pdf/` e
  `../rag-02-conversacional-citacoes/`
- Fluxo de trabalho: use `/dd` como porta de entrada

### ADRs deste projeto

| ADR | Decisão |
|---|---|
| 001 | Elasticsearch como armazém único: denso e BM25 no mesmo índice e no mesmo documento |
| 002 | RRF implementado em Python, não delegado ao retriever `rrf` nativo do Elasticsearch |
| 003 | `FusionService` como componente próprio e `SearchHit` com procedência |
| 004 | Cross-encoder local atrás de `Protocol`, com Cohere prevista como segunda implementação |
| 005 | Contrato compartilhado evoluído para 1.2.0, aditivo, com `distance` depreciado |
| 006 | Buscas densa e BM25 em sequência, com paralelismo como decisão pendente |
| 007 | `RetrievalService` devolve resultado com métrica; a facade para de cronometrar o interior do estágio |
| 008 | O funil mora em `rag/service/retrieval/`, pacote próprio dentro de `service/` |
| 009 | Cada caminho de busca tem service próprio, mesmo delegando ao repositório |

Os ADRs do `rag-01-fundamentos-pdf` e do `rag-02-conversacional-citacoes` são **precedente
conceitual, não vínculo**: valem para aqueles diretórios. Decisão herdada precisa de ADR
próprio aqui.

## Convenções deste repositório

- **`rag/` é organizado em camadas**, conforme `../docs/guidelines/arquitetura-em-camadas.md`:
  `facade/`, `service/`, `repository/`, `presenter/`, `domain/`, `api/`, mais `config.py` e
  `exceptions.py` na raiz. **Código em inglês, mensagens ao usuário e documentação em
  português.**
- O grafo é estritamente descendente: entrypoint → facade → service → repository → domain.
  Nenhuma camada chama `sys.exit()` nem escreve em stdout.
- **A `QueryFacade` não muda em ORQUESTRAÇÃO** (ADR-007). Ela continua chamando os mesmos
  estágios na mesma ordem e não sabe que a recuperação virou funil. O que muda nela é
  transporte de métrica: deixa de cronometrar o INTERIOR da busca, porque o `RetrievalService` passou a
  medir por dentro. Se a facade ganhar responsabilidade nova de orquestração, aí sim alguma
  coisa foi parar no lugar errado.
- **O cross-encoder custa segundos, não centésimos** (ADR-001 da feature). BEIR mede 6,1 s
  para top-100 em CPU; extrapolado, 1,2 a 3,0 s para 20–50 candidatos. Ele fica **ligado por
  padrão em todos os caminhos** e a latência vira coluna da tabela. Cuidado: o provedor do
  reranker precisa de escopo de processo, senão o modelo carrega a cada `/ask`.
- **Reranking pode PIORAR o resultado em alguns corpora.** No BEIR a variância vai de −26%
  a +47%. As três configurações da tabela existem para isolar isso; se piorar, é resultado
  válido do projeto, não defeito a esconder.
- **O funil vive em `rag/service/retrieval/`** (ADR-008), e não solto em `service/`.
  Ele é a única coisa que muda de projeto para projeto na trilha, então agrupá-lo faz
  "o que este projeto tem de diferente" caber num diretório. **`query_rewrite_service`
  fica FORA**, apesar do sufixo: é o estágio da pergunta, não o da recuperação, e o
  funil recebe uma query já resolvida. Os repositórios também ficam fora: a fronteira
  deles é de camada, não de assunto.
- **`DenseSearchService` e `KeywordSearchService` são REPASSE hoje** (ADR-009), e isso
  foi decidido de olhos abertos: a guideline chama delegação pura de camada vazia, e ela
  está certa enquanto não houver política de caminho. Existem para o pacote mostrar as
  quatro etapas do funil como pares. **Não os apague achando que passaram despercebidos**;
  o gatilho que os torna necessários está no ADR-009.
- **O `RetrievalService` fala com services, nunca com repositórios** (ADR-009).
- **O `RetrievalService` orquestra e não calcula** (ADR-003). Ele é dono de `candidates`,
  `rrf_k` e `top_n`, dispara os dois repositórios, entrega os rankings à fusão e passa o
  resultado ao rerank. A matemática do RRF mora no `FusionService`.
- **`FusionService` é função pura, sem dependência nenhuma** (ADR-003). É o componente que a
  guideline manda testar, e é assim que ele fica barato de testar. Injetar repositório nele
  é o sinal de que a responsabilidade escorregou.
- **O mapping do índice é explícito no código, nunca inferido** (ADR-001). Se o campo de
  texto virar `keyword` em vez de `text` analisado, o BM25 degrada **em silêncio**: metade do
  funil para de funcionar sem erro nenhum, e a conclusão vira "a híbrida não ajudou" quando a
  híbrida nunca rodou. É o risco mais sério do projeto.
- **Um motor de busca por projeto** (ADR-001). `rank-bm25` não entra, apesar de estar no
  `pip install` do guia: seria um segundo BM25 in-process competindo com o do Elasticsearch.
- **Nada do vocabulário do Elasticsearch atravessa os repositórios** (ADR-001). `_id`,
  `_source` e `hits.hits` ficam nos adaptadores. Agora são **dois** repositórios adaptando o
  mesmo motor, então a superfície de vazamento dobrou.
- **`SearchHit` carrega procedência** (ADR-003), porque com dois caminhos "score" perde
  significado único (BM25 devolve ~14.7, densa ~0.83, RRF ~0.03, cross-encoder outra escala).
  Não é enfeite de diagnóstico: é o dado bruto da tabela de medição.
- **O reranker é `Protocol`** (ADR-004) para a API da Cohere entrar como segunda
  implementação, que é o exercício 2 do guia. O modelo carrega uma vez por processo, nunca
  por consulta.
- **`pdfs/` guarda os PDFs de entrada**, não `docs/`. Aqui `docs/` é design doc.
- **`pdfs/fora-do-corpus/` nunca é indexado.** É o corpus de controle do teste negativo de
  grounding, herdado do Projeto 2. O glob é `pdfs/*.pdf`, não `**/*.pdf`; trocar por
  recursivo mata o teste negativo em silêncio.
- **O harness de medição é agnóstico de corpus.** As 10 perguntas vivem em arquivo de dados,
  não embutidas no script, porque a troca de corpus é pendência declarada (ver abaixo).
- O índice vive em volume Docker, não no repositório. É descartável:
  `docker compose down -v` + reindexação reconstrói.
- `.env` nunca é commitado. Use `.env.example` como modelo.

## Notas de ambiente

O que já se sabe do guia e dos projetos anteriores:

- Python 3.12.3. **Não existe `pip` no sistema** (nem binário, nem `python3 -m pip`) — ele
  só aparece dentro do venv: `python3 -m venv .venv && source .venv/bin/activate`.
- Docker Desktop com integração WSL. Se o `docker` responder *"could not be found in this
  WSL 2 distro"*, o Docker Desktop está fechado ou com a integração desativada.
- O `sentence-transformers` baixa ~500 MB de modelo (torch) na primeira execução. O
  reranker roda **local, na CPU** — não gasta API.
- Portas já ocupadas pelos projetos anteriores: 8000 (Chroma do Projeto 1), 8001 (Chroma
  sob profile `experimento` do Projeto 2), 6333 (Qdrant do Projeto 2). O Elasticsearch
  deste projeto usa a **9200**.
- **Healthcheck no compose é obrigatório**, não enfeite: o Elasticsearch leva ~30 s até
  aceitar conexão, e sem healthcheck o script conecta antes e você depura um erro de rede
  que é de tempo.
- **Suba um serviço por vez.** A guideline já recomendava; aqui vira obrigação. O
  Elasticsearch sozinho pede 1–2 GB de RAM e a máquina já hospeda o Qdrant do Projeto 2 e
  dois Chroma. Derrube os containers dos projetos anteriores antes de trabalhar neste.

## Estado da validação

**Os 15 critérios de aceite atendidos, e a hipótese do projeto CONFIRMADA.**
Evidência comando a comando na seção 9.1 do FDD; as duas rodadas de medição e as
pendências em `docs/operations/README.md`.

Corpus: **Manual de Orientação do Contribuinte da NF-e** (CONFAZ), 153 páginas,
553 chunks. Acerto medido por **âncora textual no trecho**, não por página.

| | só densa | híbrida | híbrida+rerank |
|---|---|---|---|
| Conceituais (5) | 2/5 | 2/5 | 2/5 |
| **Identificadores (5)** | **0/5** | 2/5 | **5/5** |
| Total (10) | 2/10 | 4/10 | **7/10** |
| Recusas (10) | 9/10 | 8/10 | **6/10** |

**A busca densa acertou ZERO das cinco perguntas de identificador.** Não é
"acertou menos": é falha total, e é a falha estrutural que o projeto existe para
demonstrar. Um embedding não distingue `229` de `234`, e as descrições que os
acompanham diferem por uma palavra.

**O achado fino: a fusão sozinha não basta.** A progressão é 0/5 → 2/5 → 5/5. O
BM25 traz o trecho certo para o conjunto de candidatos, mas a fusão por posição
nem sempre o promove ao top-4, porque ele disputa com 19 candidatos densos que
estão errados e bem colocados. **É o cross-encoder que reconhece qual dos ~30
responde.** Os dois estágios são necessários; nenhum é suficiente.

Três coisas que a validação encontrou pelo caminho:

1. **O corpus anterior não servia**, e isso estava previsto desde o PRD. Ficção
   dá nomes próprios semanticamente densos, e a busca densa ia bem neles. A
   primeira rodada está em `docs/operations/README.md` como contraste.
2. **A anotação por página superestimava o sucesso.** Enquanto ela valeu, acerto
   e recusa discordavam. Com âncora por trecho as duas andam juntas.
3. **O reordenador do guia da trilha é treinado em inglês** e derrubava três
   acertos em dez sobre corpus português. Ver a revisão do ADR-004.

**O que continua fraco:** as conceituais ficam em 2/5 nas três configurações. A
explicação provável é que este documento é uma tabela de regras que **lista** o
que rejeita, e não um texto que **ensina** como funciona. Registrado como
pendência.

Scripts que produziram a evidência estão em `docs/operations/` e podem ser
rodados de novo. Eles gastam chamadas pagas.
