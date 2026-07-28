### HLD: domínio `rag` (rag-03-hybrid-rerank)

Versão: 1.0.0
Data: 2026-07-28
Responsável: Arthur Diego (autor único)

Este projeto não tem `docs/prd.md`. O porquê foi capturado na entrevista que gerou este
documento (ver `docs/dd.md`); o porquê detalhado de cada feature vive no PRD dela, criado
dentro do `dd-feature`.

---

### Objetivo técnico

Substituir o estágio de recuperação do pipeline por um funil de quatro etapas, mantendo
intacto todo o resto do que o Projeto 2 entregou.

1. **Recuperação por dois caminhos independentes.** A mesma pergunta resolvida vai para
   uma busca kNN densa e para uma busca BM25 por palavra chave. Os dois caminhos erram
   coisas diferentes, e é essa diferença que se quer explorar: embeddings capturam
   significado e falham em token exato; BM25 acerta o token exato e falha no sinônimo.
2. **Fusão por Reciprocal Rank Fusion.** Os dois rankings são combinados por posição, não
   por valor. BM25 devolve algo como 14.7 e a busca densa 0.83, grandezas incomparáveis
   que nenhuma normalização torna comparáveis de forma honesta. O RRF ignora o valor e usa
   só a posição, e é por isso que virou padrão de fato.
3. **Reordenação por cross encoder.** Os candidatos fundidos passam por um modelo que lê a
   pergunta e o documento juntos, numa passada, em vez de comparar dois vetores gerados
   separadamente. É lento e não escala, mas é muito mais preciso, e por isso entra no fim
   do funil, sobre poucos candidatos.

O que chega à janela de contexto deixa de ser "os `k` vizinhos mais próximos no espaço
vetorial" e passa a ser "os `k` melhores segundo um modelo que comparou cada candidato
com a pergunta".

**O problema técnico que isso endereça, e ele foi medido, não suposto.** O Projeto 2
registrou que cerca de um terço das perguntas factuais recebia recusa mesmo havendo
passagem no corpus que as sustentava. Com `k=4` e busca puramente densa sobre 617 chunks,
o trecho certo frequentemente não entrava nos quatro. A recusa é honesta em relação ao que
foi recuperado, e é exatamente por isso que engana: ela se parece com ausência de
informação quando é falha de recuperação.

**Quem sofre com isso.** Qualquer pergunta cujo alvo seja um identificador: código de
erro, artigo de norma, SKU, nome próprio raro. `E-4021` e `E-4022` são quase o mesmo vetor,
porque um código não tem significado semântico para embedar.

**Fora de escopo.** Múltiplos usuários, autenticação, deploy, persistência de conversa no
servidor, e qualquer ganho de qualidade que venha de trocar o modelo de linguagem ou o
prompt de resposta. Este projeto mexe em um lugar só: o que entra na janela de contexto.

Dependências com outros sistemas

- OpenAI: `text-embedding-3-small` (embeddings) e `gpt-4o-mini` (reescrita e geração).
  Inalterado em relação ao Projeto 2.
- Elasticsearch, em container local, acessado por HTTP. Substitui o Qdrant e passa a
  atender os dois caminhos de busca.
- Cross encoder **multilíngue** `cross-encoder/mmarco-mMiniLMv2-L12-H384-v1`, executado
  localmente na CPU via `sentence-transformers`. Não é serviço externo e não gasta API.
  **Não** é o `ms-marco-MiniLM-L-6-v2` que o guia da trilha indica: aquele é treinado em
  inglês, e medido sobre este corpus em português derrubava três acertos em dez. Ver a
  revisão do ADR-004.
- Contrato HTTP compartilhado `../../../../docs/contracts/rag-api.yaml`, que este projeto
  evolui para 1.2.0 (ver Interfaces públicas).
- Frontend React genérico do workspace (`frontend/`), que renderiza controles a partir de
  `GET /capabilities`.
- Guidelines do workspace: `python-development-guidelines.md` e
  `arquitetura-em-camadas.md`, cuja seção 5 já prevê nominalmente o que este projeto
  acrescenta.

---

### Arquitetura geral

Aplicação Python única, em camadas estritamente descendentes, com quatro entrypoints sobre
as mesmas facades. Topologia herdada do Projeto 2, sem processo de fundo, fila ou
agendador.

```
entrypoint → facade → service → repository → domain
                                              ↑
                                          exceptions
```

**A mudança está inteira dentro do estágio de recuperação.** O caminho de consulta do
Projeto 2 é:

```
pergunta + histórico → QueryRewriteService → RetrievalService → PromptBuilder → geração
                                                    ↓
                                      VectorRepository (denso, k=4)
```

E passa a ser:

```
pergunta + histórico → QueryRewriteService → RetrievalService → PromptBuilder → geração
                                                    ↓
                              ┌─────────────────────┴─────────────────────┐
                        VectorRepository                          KeywordRepository
                     (kNN denso, top 20)                        (BM25, top 20)
                              └─────────────────────┬─────────────────────┘
                                                    ↓
                                       FusionService (RRF, k=60)
                                                    ↓
                                        ~30 candidatos únicos
                                                    ↓
                                  RerankService (cross encoder, top 4)
```

**Correção da versão 1.0.0 deste documento.** A primeira versão afirmava que a
`QueryFacade` não mudaria uma linha. O reconhecimento do código do Projeto 2 mostrou que
isso é incompatível com a medição por estágio exigida pelo ADR-005: a facade cronometra
ela mesma o estágio de busca, e `retrieve()` devolve uma lista sem canal para tempo. Ver
[[ADR-007-retrieval-devolve-resultado-com-metrica]].

O que vale é a afirmação mais estreita: **a `QueryFacade` não muda em orquestração.** Ela
continua chamando os mesmos estágios, na mesma ordem, sem saber que a recuperação virou
funil. O que muda nela é transporte de métrica: ela deixa de cronometrar um estágio que o
serviço passou a medir por dentro. Isso continua sendo evidência de que as camadas
aguentaram, e é uma evidência honesta em vez de uma que se escreveu antes de ler o código.

**O índice é único.** Um documento por chunk no Elasticsearch, carregando o campo
`embedding` (`dense_vector`, para o kNN) e o campo de texto analisado (para o BM25) no
mesmo documento. Três consequências que motivaram a escolha:

- A ingestão continua sendo uma passada só. Não existem dois armazéns para manter
  sincronizados, e portanto não existe o estado em que um está atualizado e o outro não.
- O `_id` do documento vira a chave natural de deduplicação do RRF. O guia da trilha usa
  `page_content[:200]` como chave, que é um atalho que quebra em dois chunks com o mesmo
  começo de texto.
- Um container em vez de dois, o que importa numa máquina que já hospeda o Qdrant do
  Projeto 2 e os Chroma dos Projetos 1 e 2.

Ambiente de implantação

- On premises, máquina do autor. Sem deploy, sem orquestrador, sem CI.
- Elasticsearch em `docker-compose.yml`, com tag de imagem fixada e **healthcheck
  obrigatório**. O serviço leva cerca de 30 segundos até aceitar conexão, e sem healthcheck
  o script conecta antes e produz um erro de rede que na verdade é erro de tempo.
- O índice vive em volume Docker, descartável e reconstruível por reindexação.
- Portas já ocupadas no workspace: 8000 (Chroma do Projeto 1), 8001 (Chroma do Projeto 2,
  sob profile `experimento`), 6333 (Qdrant do Projeto 2). O Elasticsearch usa a 9200.
- API HTTP em `127.0.0.1`, sem autenticação, servindo o frontend local do mesmo usuário.

Tecnologias principais

- Python 3.12.3
- LangChain 1.3.14, `langchain-openai` 1.4.1, `langchain-text-splitters` 1.1.2,
  `langchain-community` 0.4.2
- `langchain-elasticsearch` 1.0.0 sobre Elasticsearch em container
- `sentence-transformers` 5.6.1 para o cross encoder, em CPU
- `pypdf` 6.14.2, `python-dotenv` 1.2.2
- FastAPI 0.140.9 e uvicorn 0.51.0
- mypy 2.3.0 (obrigatório: os `Protocol` não são verificados em runtime)
- pytest 9.1.1, com escopo restrito à fusão, ao funil de rerank e à deduplicação

O `rank-bm25` aparece no `pip install` do guia e **não entra aqui**: seria um segundo
mecanismo de BM25, in process e sem persistência, competindo com o do Elasticsearch. Um
motor de busca por projeto.

Padrões adotados

- Camadas com dependência estritamente descendente e inversão nas fronteiras externas, via
  `typing.Protocol`.
- Serviço sem estado. Todo contexto de conversa entra por parâmetro (herdado do ADR-002 do
  Projeto 2, que aqui vale como precedente e é reafirmado).
- Funil de recuperação: recall barato primeiro, precisão cara depois, sobre poucos
  candidatos. O bi encoder escolhe 20 entre dezenas de milhares; o cross encoder escolhe 4
  entre 20.
- Fusão por posição, não por valor, para não depender de normalizar scores incomparáveis.
- REST sobre o contrato compartilhado, com descoberta de capacidades por
  `GET /capabilities`.

---

### Componentes e responsabilidades

Componentes novos deste projeto em **negrito**; os demais são herdados do Projeto 2 e
listados apenas quando mudam ou quando o funil depende deles.

| Componente | Responsabilidades | Dependências |
| --- | --- | --- |
| `IngestionFacade` | Caso de uso de indexação. Inalterado em forma; muda apenas o repositório que recebe os chunks. | `DocumentReader`, `ChunkingService`, `VectorRepository` |
| `QueryFacade` | Caso de uso de consulta. **Inalterada em orquestração**, alterada em transporte de métrica (ADR-007): continua chamando os mesmos estágios na mesma ordem, sem saber que a recuperação virou funil, mas deixa de cronometrar a busca e passa a repassar os tempos que o `RetrievalService` mediu por dentro. | `QueryRewriteService`, `RetrievalService`, `PromptBuilder`, `GenerationService`, `CitationResolver` |
| `RetrievalService` | Política de recuperação, agora do funil inteiro: dono de `k`, `candidates` e `rrf_k`, da validação de faixa e do `require_index()` que origina o 409 no `/ask`. Dispara os dois caminhos, entrega os rankings à fusão, passa os candidatos ao rerank e devolve `RetrievalResult` com métrica. Não implementa fusão nem pontuação, e **fala com serviços, nunca com repositórios** (ADR-009). Expõe `keyword_only()`, diagnóstico do critério de aceite 8. | **`DenseSearchService`**, **`KeywordSearchService`**, **`FusionService`**, **`RerankService`** |
| `VectorRepository` | Busca kNN densa sobre o índice. `Protocol` com adaptador Elasticsearch. Nada do vocabulário do Elasticsearch atravessa a fronteira. | Elasticsearch |
| **`KeywordRepository`** | Busca BM25 sobre o **mesmo** índice e o mesmo documento. `Protocol` com adaptador Elasticsearch. Nominalmente previsto na seção 5 da guideline do workspace. | Elasticsearch |
| **`FusionService`** | Reciprocal Rank Fusion. **Função pura:** recebe uma lista de rankings, devolve um ranking fundido e deduplicado. Não tem dependência nenhuma, e é por isso que mora aqui e não dentro do `RetrievalService`: é o componente que a guideline manda testar, e componente sem dependência é o mais barato de testar que existe. | nenhuma |
| **`RerankService`** | Pontua cada par (pergunta, candidato) com o cross encoder e devolve os `k`. `Protocol`, com implementação local em `sentence-transformers`. O `Protocol` existe para a API de rerank da Cohere entrar depois como segunda implementação, sem reescrita. Nominalmente previsto na seção 5 da guideline. | `sentence-transformers` |
| `QueryRewriteService` | Inalterado. Continua decidindo se reescreve e reescrevendo. O funil recebe a pergunta já resolvida, nunca a literal. | `GenerationService` |
| `PromptBuilder` | Inalterado. Numera o contexto e monta o prompt de resposta. Passa a receber 4 trechos escolhidos por precisão, em vez de 4 escolhidos por proximidade. | `domain` |
| `CitationResolver` | Inalterado. A citação continua resolvida por referência explícita, nunca por posição (precedente ADR-004 do Projeto 2, que a reordenação deste projeto torna ainda mais crítico). | `domain` |
| **`DenseSearchService`** | Encapsula o caminho denso e expõe a contagem do índice. **Delega ao repositório sem acrescentar política** (ADR-009); existe para o pacote `retrieval/` mostrar as quatro etapas do funil como pares. | `VectorRepository` |
| **`KeywordSearchService`** | Encapsula o caminho léxico. Também delega. Um método só, contra dois do irmão denso: o repositório denso é o dono do índice. | `KeywordRepository` |
| `HealthChecker` | Ganha `check_mapping(repository)`, que confere que o campo de texto do índice está mapeado como analisado e não como valor único. Consulta `/_cluster/health` em vez da raiz. Ver Riscos. | `VectorRepository` |
| `JsonPresenter` | Converte domínio no formato do contrato 1.2.0. Omite estágio não executado em vez de emitir zero, e **nunca** escreve pontuação no campo de distância. | `domain` |
| `ConsoleReporter` | Saída de terminal. Passa a imprimir a procedência por trecho (caminhos, posições, valores de fusão e rerank) em vez de apenas a melhor distância. | `domain` |
| `rag/api/` | Camada HTTP: `app`, `dependencies`, `descriptor`, `error_handlers`, `schemas` e `routes/`. `descriptor` publica os quatro parâmetros do funil; `dependencies` cacheia cliente e reordenador em escopo de processo. | facades, services, repositories |

**Divergência declarada em relação à guideline do workspace.** A seção 5 nomeia
`KeywordRepository` e `RerankService`, mas não prevê o `FusionService`. Ele é acréscimo
deste projeto, e a justificativa é a testabilidade descrita acima. Vira ADR.

---

### Fluxo de requisições e de dados

**Fluxo de requisição (consulta)**

- O cliente envia pergunta, transcrição e opções. O backend não guarda conversa.
- `QueryRewriteService` decide se reescreve e produz a pergunta resolvida.
- `RetrievalService` valida as faixas de `k`, `candidates` e `rrf_k`, e a relação `k <= candidates`.
- `VectorRepository` embeda a pergunta resolvida e busca os `candidates` vizinhos mais
  próximos por kNN.
- `KeywordRepository` busca os `candidates` melhores por BM25, com a mesma pergunta
  resolvida, sobre o mesmo índice.
- `FusionService` funde os dois rankings por RRF, somando `1/(rrf_k + posição + 1)` de cada
  aparição e deduplicando por `_id`. Um documento presente nos dois rankings soma as duas
  contribuições, e é por isso que a fusão o promove.
- `RerankService` pontua os candidatos fundidos com o cross encoder e corta em `k`.
- `PromptBuilder` numera os trechos finais com fonte e página coladas.
- `GenerationService` produz a resposta; `CitationResolver` resolve os `[n]`.
- A resposta carrega os tempos de cada estágio, separadamente.

**Fluxo de dados (ingestão)**

- `pdfs/*.pdf` (glob não recursivo) → `DocumentReader` → `Page` (1 based) → `ChunkingService`
  → `Chunk` → embeddings da OpenAI → um documento por chunk no Elasticsearch, carregando
  no mesmo documento o vetor e o texto analisado.
- `pdfs/fora-do-corpus/` **nunca é indexado.** É o corpus de controle do teste negativo de
  grounding, herdado do Projeto 2. O glob é `pdfs/*.pdf`, não `**/*.pdf`; trocar por
  recursivo mata o teste negativo em silêncio.
- O mapping do índice é **explícito no código**, nunca inferido pelo Elasticsearch. Ver
  Riscos.

---

### Modelo de dados (alto nível)

Entidades principais

- `Page`: texto e número da página, 1 based. Inalterada.
- `Chunk`: trecho, fonte e página. Inalterado.
- `SearchHit`: **muda.** Ganha procedência.
- `Answer`, `Citation`, `Conversation`, `IngestionReport`: inalteradas.

Relações

- Um `Page` gera N `Chunk`; um `Chunk` vira um documento do Elasticsearch; um documento
  recuperado vira um `SearchHit`.
- Um `SearchHit` pode ter vindo de um caminho ou dos dois, e essa é a informação nova.

**Por que o `SearchHit` muda.** Hoje ele carrega um `score` único, que é a distância no
espaço vetorial. Com dois caminhos, "score" perde significado: o BM25 devolve algo como
14.7, a busca densa algo como 0.83, o RRF um adimensional na casa de 0.03 e o cross encoder
outra escala ainda. Um campo chamado `score` carregando qualquer um deles é um campo que
mente conforme a configuração.

O hit passa a carregar de qual caminho ou caminhos veio, a posição que ocupou em cada
ranking, o score do RRF e o score do rerank. Isso não é enfeite de diagnóstico: sem essa
informação a tabela de medição não tem como ser preenchida, e o `chat.py` não tem como
mostrar **por que** aquele trecho subiu.

`domain/` continua sem importar LangChain e sem conhecer vocabulário do Elasticsearch.
`_id`, `_source` e `hits.hits` ficam no adaptador.

Fonte de verdade

- Elasticsearch, em volume Docker. Descartável: `docker compose down -v` mais reindexação
  reconstrói. Os PDFs em `pdfs/` são a fonte primária; o índice é derivado.

---

### Interfaces públicas

| Nome | Tipo | Protocolo | Exposição | SLAs/Limites |
| --- | --- | --- | --- | --- |
| `POST /ask` | API | REST | Interna (loopback) | Sem meta. O `timings` por estágio é o instrumento, não o SLA |
| `POST /ingest` | API | REST | Interna (loopback) | Idem |
| `GET /health` | API | REST | Interna (loopback) | Ganha `text_field_analyzed`. Responde **200** com `status: degraded` quando o índice está vazio ou mal mapeado: saúde REPORTA estado. Quem falha com 409 é o `POST /ask` |
| `GET /capabilities` | API | REST | Interna (loopback) | Publica os parâmetros novos do funil |
| CLI `ingest.py`, `ask.py`, `chat.py` | SDK | processo | Local | `ask.py` continua de turno único, para a medição ser scriptável |

**O contrato compartilhado sobe para 1.2.0, de forma aditiva com **um relaxamento declarado** (`distance` sai de
`required`, porque trecho achado só por BM25 não tem distância).** Todos os campos novos são
opcionais, então `rag-01` e `rag-02` permanecem válidos sem alteração. É o mesmo movimento
que o ADR-005 do Projeto 2 fez ao subir de 1.0.0 para 1.1.0.

O que a versão acrescenta:

- `timings` ganha **quatro** campos opcionais: `dense_s`, `keyword_s`, `fusion_s` e
  `rerank_s`. `search_s` mantém o significado de TOTAL do estágio, e os quatro o
  decompõem; somar os cinco conta a recuperação duas vezes. Um funil de três
  estágios medido como um `search_s` único não permite responder ao exercício 3 do guia
  ("rerankear 50 candidatos em vez de 20 melhora quanto, e custa quantos ms?").
- `SearchHit` ganha `score` e `provenance`, opcionais. O campo `distance` **é mantido**,
  agora documentado como válido apenas na estratégia puramente densa. Depreciar em vez de
  remover é o que mantém os dois projetos anteriores funcionando.

O que a versão **não** precisa acrescentar, e vale registrar porque foi conferido: os
parâmetros novos (`hibrida`, `rerank`, `candidates` e `rrf_k`) não exigem mudança de schema. O `ParameterSpec` já suporta `type: boolean` e `type: integer` com faixa, e o frontend renderiza controles a partir do que
`GET /capabilities` publicar. A comparação das três configurações fica disponível no
navegador sem uma linha de frontend.

---

### Considerações de escalabilidade e disponibilidade

Abordagem geral

- Um usuário, loopback, sem deploy e sem CI. Escalar não é objetivo deste projeto;
  **medir é**. O entregável é uma tabela comparativa, não um serviço.

Técnicas aplicadas

- Funil, que é a técnica central: recall barato sobre muitos, precisão cara sobre poucos.
  Passar 50 candidatos ao cross encoder em vez de 20 é decisão de custo, e por isso
  `candidates` é parâmetro exposto e medido, não constante escondida.
- Reaproveitamento do cliente e do modelo entre chamadas. Precedente direto do Projeto 2,
  onde construir o vector store a cada busca custava uma chamada paga de embedding
  extra por consulta. Aqui o custo equivalente é carregar o cross encoder do disco.
- Healthcheck no compose, obrigatório pelo tempo de subida do Elasticsearch.
- Subir **um serviço por vez**, conforme a guideline. Aqui isso deixa de ser conselho: a
  máquina já hospeda Qdrant e dois Chroma dos projetos anteriores, e o Elasticsearch
  sozinho consome de 1 a 2 GB de RAM.

Meta de disponibilidade

- Nenhuma. Projeto de estudo em máquina local. A única garantia que interessa é
  reprodutibilidade: reindexar tem que produzir o mesmo índice, e a mesma pergunta com os
  mesmos parâmetros tem que produzir o mesmo ranking, porque medição que não repete não
  mede nada.

---

### Segurança

Autenticação

- Nenhuma. API em `127.0.0.1`, servindo o frontend local do mesmo usuário. Inalterado em
  relação aos Projetos 1 e 2.

Autorização

- Nenhuma. Não há papéis nem multiusuário, e ambos estão declarados fora de escopo.

Proteção de dados

- Sem criptografia em trânsito (loopback) nem em repouso (volume Docker local).
- Sem PII: o corpus é obra de ficção publicada.
- **O reranker local reduz superfície.** Nenhum trecho do corpus sai da máquina no estágio
  de rerank, ao contrário do que aconteceria com a API da Cohere. É uma consequência
  colateral da escolha, e vale registrá la porque é argumento real caso um dia o corpus
  seja sensível.

Gestão de segredos

- Chave da OpenAI em `.env`, nunca commitada, com `.env.example` como modelo. O
  `docs/gitflow.md` traz a checagem obrigatória antes do primeiro `git add`.
- O Elasticsearch sobe com segurança desabilitada, por ser local e efêmero. Em qualquer
  outro contexto isso seria erro; aqui é a escolha deliberada de não gerir certificado
  para um container descartável.

---

### Observabilidade

Logs

- Sem logging estruturado. Pendência herdada do Projeto 2 e não resolvida aqui.

Métricas

- `timings` por estágio, na resposta: `rewrite_s`, `dense_s` (caminho denso),
  `keyword_s` (BM25), `fusion_s`, `rerank_s`, `generation_s`, e `search_s` como TOTAL do
  estágio de recuperação. Estágio que não executou fica **ausente**, nunca zerado. Neste projeto isso **deixa de ser conforto de
  diagnóstico e vira o instrumento principal**: é o que responde ao exercício 3 do guia e o
  que permite atribuir a lentidão ao estágio certo, em vez de culpar "a busca".
- Contadores de recuperação por hit: posição em cada ranking, score do RRF, score do
  rerank. É o dado bruto da tabela de medição.

Tracing

- Ausente. Um processo, sem rede interna, sem serviço a correlacionar.

Dashboards e alertas

- Nenhum. O painel é a tabela de medição, produzida por script em `docs/operations/` e
  conferida à mão.

---

### Riscos arquiteturais e mitigação

#### Mapping inferido faz o BM25 degradar em silêncio

- **Probabilidade:** média
- **Impacto:** alto, e o pior tipo de alto. Se o campo de texto for mapeado como `keyword`
  em vez de `text` analisado, o BM25 passa a casar apenas o valor inteiro do campo, nunca
  os termos. Metade do funil para de funcionar **sem erro nenhum**, e a conclusão do
  projeto vira "a híbrida não ajudou" quando a verdade é que a híbrida nunca rodou.
- **Mitigação:**
  - Mapping explícito no código, criado junto com o índice, com o analisador em português
    declarado. Nunca deixar o Elasticsearch inferir.
  - `HealthChecker` confere o tipo do campo de texto do índice e reporta divergência, do
    mesmo jeito que hoje confere a dimensão do embedding.
  - Teste de fumaça na validação: buscar por um termo raro do corpus apenas pelo caminho
    BM25 e exigir hit. Se vier vazio, é o mapping.
- **Plano de contingência:** recriar o índice com mapping explícito e reindexar. O índice é
  derivado e descartável, então o custo é tempo e chamadas de embedding, não perda de dado.

#### O corpus escolhido não expõe a falha que motiva o projeto

- **Probabilidade:** alta, e já materializada por decisão consciente
- **Impacto:** médio. O corpus inicial é *Harry Potter e a Pedra Filosofal*, herdado do
  Projeto 2. Ele tem nomes próprios raros (Nicolau Flamel, Quadribol, Grifinória) que se
  comportam parecido com identificador e nos quais o BM25 deve ganhar, mas não tem códigos.
  A falha catastrófica da busca densa, do tipo `E-4021` contra `E-4022`, não vai se
  materializar, e a linha de identificadores da tabela sai com contraste modesto.
- **Mitigação:**
  - O harness de medição nasce **agnóstico de corpus**: as 10 perguntas vivem em arquivo de
    dados, não embutidas no script. Trocar de corpus é trocar o PDF e o arquivo de
    perguntas, e rodar de novo.
  - O ganho do reranking é largamente independente do corpus, então a terceira coluna da
    tabela tem contraste real de qualquer forma.
- **Plano de contingência:** trocar por documentação técnica densa em identificadores
  (tabela CID-10, tabela NCM, manual com códigos de erro). Registrado como pendência de
  validação, não como mudança de escopo, porque nenhuma linha de código muda.

#### Latência do cross encoder na CPU

- **Probabilidade:** alta
- **Impacto:** **alto, e maior do que a versão 1.0.0 deste documento estimava.** Aquela
  versão dizia "centenas de ms", por estimativa e não por dado. O BEIR (Thakur et al.,
  2021, Tabela 3) mede 6,1 segundos para rerankear o top-100 em CPU, contra 450 ms em GPU.
  Extrapolando linearmente para 20 a 50 candidatos: **1,2 s a 3,0 s por turno.** É
  extrapolação sobre hardware de 2021 não especificado, portanto ordem de grandeza e não
  medição, mas a ordem de grandeza é segundos. Isso muda a sensação de uso dos três
  entrypoints interativos.
- **Mitigação:**
  - `candidates` exposto como parâmetro e medido em `rerank_s`, de modo que o custo seja
    visível e atribuível em vez de sentido.
  - Modelo carregado uma vez por processo, nunca por consulta. Atenção: o
    `provide_repository` do Projeto 2 é reconstruído a cada requisição HTTP, então o
    provedor do reranker precisa de escopo de processo, ou o modelo carrega por `/ask`.
  - Decisão de produto tomada no PRD da feature (ADR-001 da feature): o estágio fica
    **ligado por padrão em todos os caminhos**, e a latência vira dado publicado. Esconder
    o custo derrotaria o exercício 3.
- **Plano de contingência:** reduzir `candidates`, ou trocar a implementação do
  `RerankService` pela da Cohere, que é o motivo de ele ser `Protocol`.

#### O reranking piorar o resultado neste corpus

- **Probabilidade:** baixa a média, e é risco que a versão 1.0.0 não registrava
- **Impacto:** médio. No BEIR o ganho médio do rerank é de cerca de +11% em nDCG@10, mas a
  variância por conjunto de dados vai de **−26% (Touché-2020) a +47% (FiQA)**. Existe
  corpus em que o cross encoder degrada o resultado do BM25.
- **Mitigação:** as três configurações da tabela já isolam o efeito do rerank. Se ele
  piorar, a tabela mostra, e isso é resultado válido do projeto e não falha dele.
- **Plano de contingência:** reportar o resultado como está. Um estágio que piora num
  corpus específico é conhecimento, não defeito a esconder.

#### Vocabulário do Elasticsearch vazando pelas fronteiras

- **Probabilidade:** média, e com precedente. O ADR-001 do Projeto 2 existe exatamente
  porque isso quase aconteceu com o Qdrant.
- **Impacto:** médio. Agora são **dois** repositórios adaptando o mesmo motor, o que dobra
  a superfície por onde `_source`, `hits.hits` e a linguagem de query podem escapar.
- **Mitigação:**
  - `Protocol` nas duas fronteiras, com `domain/` sem nenhum import do cliente.
  - Critério de aceite verificável: trocar o motor deveria custar dois adaptadores e
    nenhuma linha em `service/`, `facade/` ou `domain/`.
- **Plano de contingência:** revisão dirigida pelo `dd-doc-sync` no fechamento do ciclo.

#### Primeira execução parece travada

- **Probabilidade:** alta, praticamente certa
- **Impacto:** baixo, mas confunde. O `sentence-transformers` baixa cerca de 500 MB de
  modelo e de torch na primeira execução, sem barra de progresso óbvia, e o Elasticsearch
  leva cerca de 30 segundos até responder.
- **Mitigação:** documentar nas notas de ambiente do `CLAUDE.md` e imprimir aviso explícito
  no primeiro carregamento do reranker.
- **Plano de contingência:** nenhum necessário.

#### Consumo de memória do workspace

- **Probabilidade:** média
- **Impacto:** médio. O Elasticsearch sozinho pede de 1 a 2 GB, e a máquina já hospeda o
  Qdrant do Projeto 2 e dois Chroma.
- **Mitigação:** subir um serviço por vez, conforme a guideline, e derrubar os containers
  dos projetos anteriores antes de trabalhar neste.
- **Plano de contingência:** limitar o heap da JVM do Elasticsearch por variável de
  ambiente no compose.

---

### ADRs e próximos passos

ADRs associados (a escrever no Passo 4 do `dd-greenfield`, todos decididos nesta entrevista)

- ADR-001, Elasticsearch como armazém único, com denso e BM25 no mesmo índice e no mesmo
  documento.
- ADR-002, RRF implementado em Python, não delegado ao retriever `rrf` nativo do
  Elasticsearch.
- ADR-003, `FusionService` como componente próprio, divergindo da seção 5 da guideline do
  workspace, e `SearchHit` com procedência.
- ADR-004, cross encoder local atrás de `Protocol`, com a Cohere prevista como segunda
  implementação.
- ADR-005, contrato compartilhado evoluído para 1.2.0 de forma aditiva, com `distance`
  depreciado em vez de removido.
- ADR-006, buscas densa e BM25 executadas em sequência, com paralelismo registrado como
  decisão pendente.
- ADR-007, `RetrievalService` devolve resultado com métrica e a facade deixa de cronometrar.
  **Corrige uma afirmação errada da versão 1.0.0 deste documento**, escrita a partir do
  desenho antes de o código do Projeto 2 ser lido.
- ADR-008, o funil mora em `rag/service/retrieval/`, pacote próprio dentro de `service/`.
- ADR-009, cada caminho de busca é encapsulado por um service, mesmo delegando.

Os ADR-003, 004 e 005 ganharam seções de **Revisão** depois da validação: o modelo de
reordenação mudou por medição, o contrato 1.2.0 revelou-se não ser aditivo puro, e o
`SearchHit` ganhou um campo de identidade que o desenho não previa.

Os ADRs do `rag-01-fundamentos-pdf` e do `rag-02-conversacional-citacoes` são **precedente
conceitual, não vínculo**: valem para aqueles diretórios. Decisão herdada precisa de ADR
próprio aqui.

Decisões pendentes

- **Paralelizar as duas buscas.** A decisão atual é sequência, pelo argumento de que o
  gargalo do pipeline é o embedding da query (chamada externa paga) e o cross encoder, não
  duas requisições HTTP a um container local. O autor registrou, com razão, que em cenário
  produtivo isso seria latência somada sem motivo. **Critério objetivo de reabertura:**
  quando `search_s + keyword_s` medidos passarem de uma fração relevante do tempo total do
  turno, ou quando o projeto deixar de ser local. A implementação preferida nesse caso é
  `asyncio` ou threads no `RetrievalService`, mantendo os dois repositórios ignorantes da
  concorrência; `_msearch` fica descartado por furar a fronteira entre eles.
- **Troca do corpus** por documentação técnica densa em identificadores. Não muda código,
  muda a força da evidência.
- **Logging estruturado**, pendência herdada do Projeto 2.
- **Comparação com a API de rerank da Cohere** (exercício 2 do guia), que o `Protocol` do
  `RerankService` deixa preparada.

Próximos passos técnicos

- Escrever os ADRs estruturais (Passo 4 do `dd-greenfield`). **Feito: nove ADRs.**
- Primeira feature via `dd-feature`, que produz PRD da feature, FDD, diagramas, coleção
  Postman e implementação.
- A feature natural é o funil de recuperação inteiro, porque fatiá lo em partes entregaria
  estados intermediários que não respondem nada: híbrida sem rerank já é uma das colunas da
  tabela, mas fusão sem os dois caminhos não é nada.
