### HLD: domínio `rag` (rag-01-fundamentos-pdf)

Versão: 1.0
Data: 2026-07-25
Responsável: arthu (autor do projeto)

Documento técnico. A narrativa de produto está em `docs/prd.md` e não se repete aqui.

---

### Objetivo técnico

Executar o pipeline canônico de RAG (load, split, embed, store, retrieve, generate) sobre
um corpus local de PDFs, em processo único de linha de comando, de forma que cada etapa
seja observável isoladamente. O sistema precisa permitir responder, diante de uma resposta
errada, se a falha foi da recuperação ou da geração. Essa capacidade de diagnóstico é o
requisito funcional central, acima da qualidade da resposta em si.

Restrição estruturante: o corpus indexado é conhecido do modelo de linguagem a partir dos
dados de treino. O desenho precisa produzir evidência de que a resposta veio da
recuperação e não da memória do modelo, sob pena de o sistema parecer funcionar sem
funcionar.

Dependências com outros sistemas
- API da OpenAI: endpoint de embeddings (`text-embedding-3-small`) e de chat completions
  (`gpt-4o-mini`). Única dependência externa, e única fonte de custo.
- Sistema de arquivos local: leitura em `pdfs/`.
- Serviço Chroma em container, na porta 8000 do host. Precisa estar no ar antes de
  qualquer script rodar.
- Sem fila, sem banco relacional, sem outro serviço.

---

### Arquitetura geral

Dois programas cliente independentes contra um serviço de armazenamento vetorial, sem
comunicação entre si. A separação entre eles corresponde à separação temporal do
pipeline: a ingestão roda uma vez por corpus e é cara; a consulta roda muitas vezes e é
barata.

```
                offline, uma vez                      online, muitas vezes
  pdfs/*.pdf ──> ingest.py ──┐                  ┌───── ask.py <── pergunta
                             v   HTTP :8000     v                    │
                        ┌────────────────────────────┐               v
                        │  chromadb/chroma:1.5.9     │      resposta + chunks
                        │  volume chroma_data:/data  │        + distancias
                        └────────────────────────────┘
  pdfs/fora-do-corpus/  (nunca indexado, ausente do serviço por construção)
```

Ambiente de implantação
- On-premises, máquina única (WSL 2 sobre Windows), Docker Desktop 4.51.0.
- Clientes Python efêmeros; um único serviço residente (Chroma) na porta 8000.
- Persistência no volume nomeado `chroma_data`, montado em `/data` dentro do container.
  O caminho vem do `/config.yaml` da própria imagem (`persist_path: "/data"`), verificado
  na imagem, não presumido.

Tecnologias principais
- Python 3.12.3
- LangChain 1.3.14 (composição por LCEL, estilo v1)
- langchain-chroma 1.1.0, que exige `chromadb` completo no cliente (`>=1.3.5,<2.0.0`)
  independentemente do modo de execução do servidor
- Chroma servidor `chromadb/chroma:1.5.9`, API v2 (`/api/v2/heartbeat`). A API v1 foi
  removida e responde `410 Gone`
- OpenAI `text-embedding-3-small` (1536 dimensões) e `gpt-4o-mini` (temperatura 0)
- pypdf 6.14.2 via `PyPDFLoader`

Padrões adotados
- Separação ingestão/consulta (write path e read path desacoplados pelo índice).
- Pipeline por composição funcional (LCEL): a saída de cada etapa é a entrada da seguinte.
- Índice como artefato derivado e descartável. A fonte de verdade é o PDF.
- Segregação por responsabilidade com inversão de dependência (ADR-005), nomeada em
  camadas (ADR-006): `Protocol` para repositórios, chunking e geração; implementações
  concretas injetadas pelos composition roots.
- Exceções de domínio em vez de `sys.exit()` nas camadas, o que os torna testáveis e
  reutilizáveis. A tradução para código de saída acontece só nos entrypoints.

---

### Componentes e responsabilidades

Estrutura definida pelo ADR-005 e nomeada em camadas pelo ADR-006. Convenção: código em
inglês, mensagens ao usuário e documentação em português. Diagrama C4 nível 3 em
`docs/domains/rag/diagrams/c4/componente.puml`.

| Camada | Componente | Responsabilidades |
| --- | --- | --- |
| entrypoint | `ingest.py` | Controller (argparse) e composition root. Não orquestra: delega à facade |
| entrypoint | `ask.py` | Idem, mais o laço do REPL |
| facade | `IngestionFacade` | Caso de uso da ingestão. Devolve `IngestionReport`. Não conhece terminal |
| facade | `QueryFacade` | Caso de uso da consulta. Devolve `Answer`. Não conhece terminal |
| service | `HealthChecker` | Heartbeat do Chroma antes da primeira chamada paga |
| service | `ChunkingService` / `RecursiveChunkingService` | `Document` para chunks, 1000/150, herdando metadados |
| service | `RetrievalService` | Quanto trazer e sob que critério. Sem limiar (HLD) |
| service | `PromptBuilder` | Montagem do prompt. Dono da `ESCAPE_PHRASE`, contrato literal |
| service | `GenerationService` / `OpenAiGenerationService` | Chamada ao LLM e fábrica de embeddings |
| repository | `DocumentReader` / `PdfDocumentReader` | Arquivos para `Document`. Glob não recursivo (ADR-004) |
| repository | `VectorRepository` / `ChromaVectorRepository` | Persiste e consulta vetores por HTTP |
| presenter | `ConsoleReporter` | Único ponto que escreve: stdout resultado, stderr diagnóstico |
| base | `domain.models` | `SearchHit`, `Answer`, `IngestionReport`. Objetos de valor, folha do grafo |
| base | `config` | `RagProperties`, validada na construção |
| base | `exceptions` | `RagException` e subclasses. Camadas levantam, entrypoints encerram |
| infra | Serviço Chroma | Persiste no volume `chroma_data`, responde na porta 8000 |
| infra | Corpus de controle | `pdfs/fora-do-corpus/`, nunca lido pela ingestão |

Duas invariantes estruturais, verificáveis por inspeção:

- **Nenhum módulo de `rag/` chama `sys.exit()` nem escreve em stdout.** Encerrar o
  processo é decisão dos entrypoints; escrever é responsabilidade exclusiva do
  `ConsoleReporter`.
- **O grafo é estritamente descendente:** `facade -> service -> repository -> domain`.
  Nenhuma camada importa outra acima dela. Extraído por AST e desenhado em
  `docs/domains/rag/diagrams/mermaid/componentes.mmd`.

---

### Fluxo de requisições e de dados

**Fluxo de ingestão** (`python ingest.py`)
- Carregar `.env` e validar a presença de `OPENAI_API_KEY`, falhando de imediato se ausente.
- Varrer `pdfs/*.pdf` com glob não recursivo. `pdfs/fora-do-corpus/` fica fora por construção.
- Para cada PDF, extrair uma página por `Document`, preservando `source` e `page` nos metadados.
- Validar que houve texto extraído. Documento vazio indica PDF escaneado e deve falhar com
  mensagem explícita, não seguir em silêncio.
- Dividir em chunks de 1000 caracteres com 150 de sobreposição, herdando os metadados.
- Enviar os chunks em lote ao endpoint de embeddings. Esta é a única etapa cara.
- Gravar vetores, textos e metadados na coleção do serviço Chroma, via HTTP.
- Reportar o total de páginas de entrada e de chunks de saída.

**Fluxo de consulta** (`python ask.py` ou `python ask.py "pergunta"`)
- Carregar `.env`, abrir o índice existente e informar quantos chunks contém.
- Ler a pergunta do laço interativo ou do argumento de linha de comando.
- Gerar o embedding da pergunta e recuperar os `k=4` chunks mais próximos, com distância.
- Montar o prompt: instrução de fundamentação, instrução de escape, contexto concatenado,
  pergunta.
- Chamar o modelo com temperatura 0.
- Exibir a resposta, seguida dos chunks recuperados com fonte, página, distância e latência de
  cada estágio.
- No modo REPL, aguardar a próxima pergunta reutilizando índice e cliente já abertos.

**Fluxo de dados**
- PDF (disco) → texto por página (memória) → chunks com metadados (memória) → vetores de
  1536 dimensões (API OpenAI) → índice Chroma (disco).
- Pergunta (stdin ou argv) → vetor (API) → k chunks (índice) → prompt (memória) → resposta
  (API) → stdout.
- Logs e diagnóstico vão para stderr, mantendo stdout limpo para redirecionamento.

---

### Modelo de dados (alto nível)

Entidades principais
- **Documento**: um PDF de `pdfs/`. Identificado pelo caminho.
- **Página**: unidade natural de extração do `PyPDFLoader`. Atributos `source` e `page`.
- **Chunk**: unidade de indexação e recuperação. Texto mais metadados herdados da página.
- **Embedding**: vetor de 1536 dimensões associado a exatamente um chunk.

Relações
- Documento 1 : N Página
- Página 1 : N Chunk (com sobreposição de 150 caracteres entre chunks vizinhos)
- Chunk 1 : 1 Embedding

Fonte de verdade
- Os arquivos em `pdfs/`. A coleção no volume `chroma_data` é integralmente derivada e
  pode ser apagada e reconstruída sem perda de informação, ao custo de novas chamadas de
  embedding.

Versionamento e retenção
- Sem versionamento de índice. Mudança de parâmetro de chunking ou de modelo de embedding
  exige reconstrução total, não migração. Não existe migração de embeddings entre modelos
  de dimensões diferentes.
- `data/` é ignorado pelo git. `pdfs/` também, exceto o `.gitkeep`.

---

### Interfaces públicas

| Nome | Tipo | Protocolo | Exposição | SLAs/Limites |
| ---- | ---- | ---------- | --------- | ------------- |
| `ingest.py` | CLI | argv, stdout/stderr | Local | Sem meta. Custo dominado pela API de embeddings |
| `ask.py` | CLI | argv e stdin (REPL), stdout/stderr | Local | Sem meta formal. Latência esperada de 2 a 4 s por pergunta, dominada pela geração |

O sistema não expõe interface de rede. Não há API HTTP, fila, stream nem SDK. Toda
interação é local e síncrona, por um único usuário.

---

### Considerações de escalabilidade e disponibilidade

Abordagem geral
- Não se aplicam metas de escalabilidade ou disponibilidade. O sistema tem um usuário, é
  executado sob demanda e não atende requisições de terceiros. Registrado aqui por
  completude do formato, e para deixar explícito que a ausência é decisão, não omissão.

Limites reais que existem
- **Rate limit da OpenAI** na ingestão em lote. Mitigado enviando os chunks em lotes e
  reduzindo a concorrência ao primeiro `429`.
- **Custo por reindexação.** Reindexar as 274 páginas a cada tentativa de chunking é o
  consumo de crédito mais provável. Mitigação: experimentar em uma amostra do corpus.
- **Memória.** Cerca de 800 chunks e seus vetores cabem folgadamente em memória. O limite
  prático seria alcançado em corpus uma ordem de grandeza maior.

Meta de disponibilidade
- Não aplicável. Processo local sob demanda.

---

### Segurança

Autenticação
- Não aplicável entre usuário e sistema. Existe apenas autenticação do sistema perante a
  OpenAI, por chave de API.

Autorização
- Não aplicável. Usuário único, sem papéis, sem multi-tenancy.

Proteção de dados
- Criptografia em trânsito por TLS nas chamadas à OpenAI, garantida pelo cliente oficial.
- Sem criptografia em repouso. O índice contém trechos dos PDFs em texto claro no disco
  local, o que é aceitável para o conteúdo em questão.
- Sem PII no corpus atual (obra literária e texto bíblico). Caso um corpus futuro contenha
  dados pessoais, a decisão precisa ser reavaliada: o conteúdo dos chunks é enviado à API
  a cada consulta.

Gestão de segredos
- `OPENAI_API_KEY` exclusivamente em `.env`, carregado por `python-dotenv`.
- `.env` listado no `.gitignore` desde antes do primeiro `git add`, condição verificada no
  `docs/gitflow.md`.
- `.env.example` versionado como modelo, sem valor real.
- O script falha de imediato, com mensagem explícita, se a chave estiver ausente. Falhar na
  primeira linha é preferível a falhar na chamada de API depois de processar 274 páginas.

---

### Observabilidade

Logs
- Diagnóstico em stderr, resposta em stdout. A separação permite `python ask.py "..." >
  resposta.txt` sem contaminar o arquivo.
- Sem arquivo de log persistente. O terminal é o destino.

Métricas
- Ingestão: páginas de entrada, chunks de saída, tempo total.
- Consulta: latência de busca, latência de geração, quantidade de chunks recuperados e
  distância de cada um.
- A exibição dos chunks recuperados é requisito funcional, não recurso de depuração. Sem
  ela, é impossível separar falha de recuperação de falha de geração, que é o objetivo
  declarado do projeto.

Tracing
- Não há tracing distribuído, por não haver sistema distribuído. LangSmith fica disponível
  como opção futura via variáveis de ambiente, sem alteração de código, e passa a valer a
  pena a partir do Projeto 5, quando surgem grafos com ciclos.

Dashboards e alertas
- Nenhum. O painel de custo da própria OpenAI cobre a única métrica que importa monitorar,
  e um limite de gasto mensal configurado na conta substitui qualquer alerta que se
  pudesse construir aqui.

---

### Riscos arquiteturais e mitigação

#### Grounding falso: o modelo responde de memória, não do índice

- **Probabilidade:** alta
- **Impacto:** crítico. O sistema aparenta funcionar perfeitamente enquanto a recuperação
  está quebrada, e o projeto inteiro perde o valor de aprendizado.
- **Mitigação:**
  - Manter `pdfs/fora-do-corpus/53_1Cor.pdf` permanentemente fora do índice, como corpus de
    controle. Toda pergunta sobre ele deve retornar a frase de escape.
  - Formular as perguntas de verificação positiva sobre a edição em PDF (página, sumário,
    grafia da tradução), nunca sobre o enredo.
  - Exibir sempre os chunks recuperados, permitindo verificar se a resposta se apoia neles.
- **Plano de contingência:** trocar o corpus por documento seguramente ausente do treino,
  como manual de equipamento doméstico ou norma técnica recente.

#### Similaridade alta confundida com relevância

- **Probabilidade:** alta
- **Impacto:** médio. O índice sempre devolve os k mais próximos, mesmo quando todos são
  ruins, e o modelo responde em cima deles com aparente confiança.
- **Mitigação:**
  - Exibir a distância de cada chunk, tornando o fenômeno visível em vez de silencioso.
  - Manter a instrução de escape explícita no prompt.
- **Plano de contingência:** introduzir limiar de similaridade. Decidido não fazê-lo agora:
  sentir o problema sem a proteção é o que dá sentido ao grading do Projeto 5.

#### Incompatibilidade de dimensão ao trocar o modelo de embedding

- **Probabilidade:** média
- **Impacto:** alto. A troca para um modelo de dimensão diferente (por exemplo
  `nomic-embed-text`, de 768) pode não gerar erro e passar a retornar resultados sem
  sentido de forma silenciosa.
- **Mitigação:**
  - Registrar o modelo e a dimensão em ADR, tornando a decisão explícita e rastreável.
  - Reconstruir o índice do zero em qualquer troca de modelo. Nunca tentar migrar.
- **Plano de contingência:** `docker compose down -v` e reindexar. Custo inferior a
  US$ 0,05.

#### Falha de infraestrutura confundida com falha do pipeline

- **Probabilidade:** média
- **Impacto:** médio. Serviço parado, porta ocupada ou versão incompatível de cliente e
  servidor produzem erro de conexão que, para quem está aprendendo RAG, é indistinguível
  de erro de código. Este risco não existiria com Chroma embarcado e foi aceito
  conscientemente no ADR-001.
- **Mitigação:**
  - Verificar o serviço antes de qualquer diagnóstico:
    `curl localhost:8000/api/v2/heartbeat`.
  - Manter cliente e servidor na mesma linha de versão (`chromadb` 1.5.x nos dois lados).
  - Healthcheck declarado no `docker-compose.yml`, com `docker compose ps` mostrando
    `healthy`.
  - Falhar cedo no script, com mensagem que aponte para o serviço e não para o código.
- **Plano de contingência:** `docker compose up -d chroma` e conferir
  `docker compose logs chroma`.

#### Vazamento da chave da OpenAI

- **Probabilidade:** baixa
- **Impacto:** alto. Chave em repositório público é detectada por varredores automáticos e
  explorada em minutos.
- **Mitigação:**
  - `.gitignore` com `.env` criado antes do primeiro `git add`.
  - Verificação de segredos no checklist de pré-commit da guideline.
  - Limite de gasto mensal configurado na conta da OpenAI.
- **Plano de contingência:** revogar a chave em platform.openai.com e emitir outra.
  Reescrever o histórico do git se o commit já tiver sido enviado.

#### Consumo inesperado de crédito por reindexação repetida

- **Probabilidade:** média
- **Impacto:** baixo. As 274 páginas custam poucos centavos por indexação, mas o
  experimento de chunking pede várias.
- **Mitigação:**
  - Usar uma amostra do corpus enquanto se experimentam parâmetros.
  - Reportar a contagem de chunks a cada ingestão, tornando o custo perceptível.
- **Plano de contingência:** limite de gasto mensal na conta.

---

### ADRs e próximos passos

ADRs associados
- [ADR-001](../../adrs/generated/RAG/ADR-001-chroma-como-servico-em-container.md): Chroma
  como serviço em container, não embarcado.
- [ADR-002](../../adrs/generated/RAG/ADR-002-openai-como-provedor-de-modelos.md): OpenAI
  como provedor de LLM e de embeddings.
- ~~[ADR-003](../../adrs/generated/RAG/ADR-003-scripts-independentes-sem-modulo-compartilhado.md):
  dois scripts independentes, sem módulo compartilhado.~~ **Superado pelo ADR-005. Não
  seguir.**
- [ADR-004](../../adrs/generated/RAG/ADR-004-corpus-de-controle-fora-do-indice.md): corpus
  de controle mantido fora do índice.
- [ADR-005](../../adrs/generated/RAG/ADR-005-segregacao-por-responsabilidade.md):
  segregação do pipeline em módulos por responsabilidade. **Supera o ADR-003.**
- [ADR-006](../../adrs/generated/RAG/ADR-006-nomenclatura-em-camadas.md):
  nomenclatura em camadas explícitas, código em inglês. **Emenda o ADR-005.**
- [ADR-007](../../adrs/generated/RAG/ADR-007-camada-de-caso-de-uso.md):
  camada de caso de uso (facade) separada dos entrypoints. **Emenda o ADR-006.**

Decisões deliberadamente adiadas
- Limiar de similaridade na recuperação. Adiado para sentir, sem proteção, que
  similaridade alta não é relevância. Reabrir no Projeto 5, junto com o grading.
- Harness de avaliação compartilhado entre projetos. Reabrir no Projeto 3, quando o RAGAS
  entrar e a comparação entre configurações passar a exigir método.

Próximos passos técnicos
- Registrar os quatro ADRs acima em `docs/adrs/generated/RAG/`.
- Seguir para o FDD da primeira feature pelo workflow `dd-feature`, que cobre o card de
  trabalho, os diagramas e a implementação.
- Coleção Postman não se aplica: não há contrato HTTP neste domínio.
