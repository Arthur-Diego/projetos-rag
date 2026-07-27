### HLD: domínio `rag` (rag-02-conversacional-citacoes)

Versão: 1.0.0
Data: 2026-07-27
Responsável: Arthur Diego (autor único)

Escopo de negócio no PRD (`docs/prd.md`). Este documento é o **como** técnico e não
repete a narrativa de lá.

---

### Objetivo técnico

Acrescentar duas capacidades ao pipeline do Projeto 1 sem quebrar a estrutura em camadas
que ele deixou como herança:

1. **Recuperação ciente do histórico.** A pergunta do usuário deixa de ser embedada
   diretamente. Antes da busca, um estágio de reescrita transforma a última pergunta em
   uma pergunta autossuficiente, resolvendo pronomes e referências implícitas com base na
   transcrição. É esse texto reescrito, e não o original, que vira vetor.

2. **Procedência por afirmação.** O trecho recuperado chega ao modelo numerado e
   acompanhado do identificador de origem, e a resposta carrega `[n]` colado a cada
   afirmação. O rótulo `n` é resolvível pelo cliente até `fonte` e `página`, sem depender
   da ordem em que os trechos foram devolvidos.

O problema técnico que isso endereça, e que o Projeto 1 tem: a segunda pergunta de um
diálogo é embedada fora de contexto, produz um vetor sobre o assunto errado e traz lixo,
sem que nada na saída indique que a busca falhou. A resposta sai plausível, com uma lista
de fontes ao lado que parece corroborá-la.

Dependências com outros sistemas

- OpenAI: `text-embedding-3-small` (embeddings) e `gpt-4o-mini` (reescrita e geração).
  Dois estágios de LLM por turno, não um. Ver Riscos.
- Qdrant, em container local, acessado por HTTP.
- Contrato HTTP compartilhado `../docs/contracts/rag-api.yaml`, na versão 1.1.0 (ver
  Interfaces públicas).
- Frontend React genérico do workspace (`frontend/`), que renderiza controles a partir de
  `GET /capabilities`.
- Guideline de arquitetura em camadas do workspace, que este projeto segue com uma
  divergência declarada (ver Componentes).

---

### Arquitetura geral

Aplicação Python única, em camadas estritamente descendentes, com quatro entrypoints
sobre as mesmas facades. Não há processo de fundo, fila nem agendador.

```
entrypoint → facade → service → repository → domain
                                              ↑
                                          exceptions
```

O que muda em relação ao Projeto 1 é apenas o interior do caminho de consulta: entre
receber a pergunta e chamar o retriever entra um estágio novo, e entre recuperar e gerar
entra outro. As camadas e a direção das dependências ficam idênticas.

**A decisão que organiza todo o resto: o backend não guarda conversa.** A transcrição é
propriedade do cliente. A CLI mantém a sua em memória do processo, o frontend mantém a
dele no navegador, e ambos a enviam inteira a cada chamada. O servidor recebe histórico,
usa e esquece.

Três consequências que valem registrar, porque são o motivo da escolha:

- A facade continua recebendo tipos de domínio e devolvendo tipos de domínio, sem
  conhecer sessão, cookie ou identificador de requisição. A regra 2.2 da guideline
  sobrevive intacta, e é ela que permite a mesma facade servir CLI e HTTP.
- Não existe estado mutável compartilhado no processo do servidor. Nada vaza entre
  requisições, nada precisa ser limpo, nada morre no restart porque nada vivia lá.
- A memória vira **dado de entrada explícito**, visível na assinatura do caso de uso.
  Num projeto cujo objetivo é entender o mecanismo, memória implícita gerenciada por
  framework esconde exatamente o que se quer ver.

O preço: a transcrição trafega inteira a cada turno. Em `127.0.0.1`, com um usuário,
isso é irrelevante. Com múltiplos usuários e rede real seria a decisão errada, e o PRD
declara que múltiplos usuários estão fora de escopo.

Ambiente de implantação

- On-premises, máquina do autor. Sem deploy, sem orquestrador, sem CI.
- Qdrant v1.18.1 em `docker-compose.yml`, com healthcheck validado contra a imagem. O
  índice vive no volume Docker, descartável e reconstruível por reindexação. A versão da
  imagem acompanha a do `qdrant-client` que o `langchain-qdrant` traz.
- Um segundo serviço, Chroma, existe no mesmo compose sob o profile `experimento`, na
  porta 8001. Não sobe por padrão e não faz parte do projeto: existe só para o critério de
  aceite 7. A porta 8001 evita colisão com o container do Projeto 1, que ocupa a 8000.
- API HTTP em `127.0.0.1`, sem autenticação, servindo o frontend local do mesmo usuário.

Tecnologias principais

- Python 3.12.3
- LangChain 1.3.14, `langchain-openai` 1.4.1, `langchain-text-splitters` 1.1.2,
  `langchain-community` 0.4.2
- `langchain-qdrant` 1.1.0 sobre Qdrant em container
- `pypdf` 6.14.2, `python-dotenv` 1.2.2
- FastAPI 0.140.1 e uvicorn 0.51.0
- mypy 2.3.0 (obrigatório: os `Protocol` não são verificados em runtime)
- pytest 9.1.1, com escopo restrito à matriz de recusa e à reescrita

Padrões adotados

- Camadas com dependência estritamente descendente e inversão nas fronteiras externas,
  via `typing.Protocol`.
- Serviço sem estado. Todo contexto de conversa entra por parâmetro.
- REST sobre o contrato compartilhado, com descoberta de capacidades por
  `GET /capabilities`.
- Composition root no entrypoint para as CLIs; container do framework para o HTTP, com a
  regra da guideline 2.5 (container para o estável, construção explícita para o que vem
  do corpo da requisição).

---

### Componentes e responsabilidades

| Componente | Responsabilidades | Dependências |
| --- | --- | --- |
| `ingest.py` | Composition root da indexação. Adapta argumentos, monta a facade, apresenta o relatório. | `IngestionFacade`, `ConsoleReporter` |
| `ask.py` | Composition root da consulta de turno único. Continua existindo: é o comando que termina, e é sobre ele que a matriz de recusa é scriptada. | `QueryFacade`, `ConsoleReporter` |
| `chat.py` | Composition root do REPL. Mantém a transcrição em memória do processo, acrescenta cada turno e imprime a query reescrita ao lado da original. | `QueryFacade`, `ConsoleReporter` |
| `serve.py` | Publica o app FastAPI. Magro por decisão: nenhuma lógica de RAG. | `rag.api.app` |
| `composition.py` | Composition root das CLIs. Monta o grafo que `ask.py`, `chat.py` e `ingest.py` compartilham. **Não é camada** (ADR-006): é função no nível dos entrypoints, e nada em `rag/` a conhece. É onde o critério 7 do PRD se cumpre, em `build_repository`. | facades, services, repositories |
| `IngestionFacade` | Caso de uso de indexação: ler, dividir, embedar, gravar, relatar. | `DocumentReader`, `ChunkingService`, `VectorRepository` |
| `QueryFacade` | Caso de uso de consulta. Recebe pergunta **e** conversa, devolve `Answer`. Orquestra reescrita, busca, montagem de contexto numerado, geração e resolução de citação. Calcula `refused`. Não conhece terminal nem HTTP. | `QueryRewriteService`, `RetrievalService`, `PromptBuilder`, `GenerationService`, `CitationResolver` |
| `QueryRewriteService` | Decide se reescreve e reescreve. Devolve a query de busca e o motivo da decisão. Nunca levanta: falha vira `reescrita_falhou` e cai para a original. Componente novo deste projeto. | `GenerationService` |
| `RetrievalService` | Política de recuperação: dono do `k`, da validação de faixa e do `require_index()` que origina o 409. Busca pela query **já resolvida**. | `VectorRepository` |
| `ChunkingService` | Divide o documento em `Chunk`, preservando `source` e `page`. `Protocol` com implementação recursiva. | — |
| `PromptBuilder` | Monta o contexto **numerado**, com `fonte` e `página` colados ao texto, e o prompt de resposta com a instrução de citar por número e a frase de escape. Recebe a `RewriteDecision` inteira e monta a pergunta resolvida com a literal do usuário ao lado (ADR-007). | `domain` |
| `CitationResolver` | Traduz os rótulos `[n]` presentes no texto gerado em referências resolvidas para os trechos recuperados. Isola o parsing num lugar só. Componente novo deste projeto, em `service/`. | `domain` |
| `GenerationService` | Fronteira com o LLM. `Protocol`; implementação OpenAI. Usado por dois chamadores distintos: reescrita e resposta. | OpenAI |
| `VectorRepository` | Fronteira com o armazém vetorial. `Protocol` de cinco métodos (`count`, `vector_size`, `recreate`, `add`, `search`); implementações Qdrant e Chroma. **Normaliza aqui, uma vez:** página para 1-based e similaridade para distância. | Qdrant |
| `DocumentReader` | Fronteira com o sistema de arquivos e o formato. `Protocol`; implementação pypdf. Devolve `Page` de domínio, já 1-based. | `pdfs/` |
| `HealthChecker` | Verifica pré-condições antes da primeira chamada paga. `check()` só pergunta se o Qdrant responde, e é barato; `check_dimensions()` compara o modelo de embedding com a coleção existente. Separados porque o segundo precisa do repositório pronto. | `RagProperties`, `VectorRepository` |
| `ConsoleReporter` | Único componente que escreve no terminal. stdout carrega o resultado, stderr carrega o diagnóstico. | `domain` |
| `JsonPresenter` | Serializa `Answer` e `IngestionReport` para o formato do contrato. | `domain` |
| `rag.api` | Camada HTTP: `app.py`, `routes/`, `schemas.py`, `dependencies.py`, `descriptor.py`, `error_handlers.py`. Traduz HTTP em chamadas de facade e exceção de domínio em status. | facades, `JsonPresenter` |

**Divergência declarada em relação à guideline do workspace.** A seção 5 da
`arquitetura-em-camadas.md` prevê que o Projeto 2 acrescente um `ConversationMemory` em
`service/`. Não é o que este HLD faz. Com o backend sem estado, não há nada para um
serviço de memória guardar ou gerenciar: a conversa é um valor que entra pela assinatura
do caso de uso. Um `ConversationMemory` aqui seria uma camada vazia, exatamente o que a
seção 4 da guideline chama de delegação decorativa. A conversa vive em `domain/models.py`
como objeto de valor, e a única lógica associada a ela (aplicar a janela) é uma função
pura sobre esse valor. Registrado em ADR próprio.

---

### Fluxo de requisições e de dados

**Fluxo de requisição — consulta com histórico (`POST /ask` e `chat.py`)**

- O cliente envia `question` e, em `options.history`, a transcrição dos turnos anteriores.
  Primeiro turno envia lista vazia ou omite o campo.
- A camada de entrada valida o corpo e constrói uma `Conversation` de domínio a partir da
  transcrição recebida.
- A `QueryFacade` aplica a **janela de histórico**: dos turnos recebidos, mantém os N mais
  recentes. N é parâmetro, exposto em `/capabilities`. Truncar no servidor, e não no
  cliente, mantém o experimento do critério 6 do PRD controlável de um lugar só.
- O `QueryRewriteService` decide. Se a conversa está vazia, não reescreve e não gasta
  chamada. Se a **reescrita condicional** está ligada, avalia a heurística (pergunta curta
  ou com pronome/referência anafórica) e pode pular. Caso contrário, chama o LLM com um
  prompt que não responde nada e só produz uma pergunta autossuficiente.
- A query resultante, reescrita ou original, é embedada e buscada no Qdrant. O retriever
  devolve os `k` trechos mais próximos, com `source` e `page` nos metadados.
- O `PromptBuilder` numera os trechos de 1 a k e cola a origem ao texto de cada um. O
  prompt de resposta exige `[n]` ao final de cada afirmação e traz a frase de escape.
- O LLM responde. A conversa **truncada** vai junto, para que o modelo entenda o fio.
- O `CitationResolver` extrai os rótulos `[n]` do texto e os resolve para os trechos
  correspondentes.
- A facade monta o `Answer`: texto, citações resolvidas, trechos recuperados, indicador de
  recusa, query reescrita, decisão de reescrita e latência por estágio.
- O apresentador escreve. A CLI imprime a query reescrita ao lado da original; a API
  serializa conforme o contrato.
- **O cliente**, e só ele, acrescenta o turno à sua transcrição.

**Fluxo de requisição — indexação (`POST /ingest` e `ingest.py`)**

Idêntico ao do Projeto 1, **inclusive na ordem**: conferir que há PDF em `pdfs/*.pdf`
(glob não recursivo, de propósito), **recriar a coleção**, ler, dividir, embedar em lote,
gravar, relatar páginas, chunks e tempo.

A coleção é apagada **antes** da leitura, e isso é decisão, não acaso: falha depois disso
deixa o índice vazio e a próxima consulta devolve 409 `rode python ingest.py`, que é
barulhento. Na ordem inversa, a falha deixaria o índice **antigo** intacto e a próxima
consulta responderia com dados obsoletos sem sintoma nenhum.

A única checagem feita antes de destruir é a existência de PDFs: é barata, não depende de
conseguir ler nenhum deles, e destruir o índice porque alguém rodou com a pasta vazia
seria punição sem informação. Coberto por `tests/test_ingestion.py`, que fixa a ordem —
uma versão anterior deste projeto a havia invertido sem registro.

**Fluxo de dados**

- `pdfs/*.pdf` → `DocumentReader` → páginas com `source` e `page` → `ChunkingService` →
  chunks com os mesmos metadados preservados → embeddings da OpenAI → coleção no Qdrant,
  em volume Docker.
- `pdfs/fora-do-corpus/*.pdf` → **nenhum destino**. O glob não os alcança. É o corpus de
  controle, e a ausência é o mecanismo.
- Transcrição do cliente → corpo da requisição → `Conversation` (truncada) → prompt de
  reescrita → query de busca → Qdrant → trechos numerados → prompt de resposta → texto com
  `[n]` → citações resolvidas → resposta ao cliente → transcrição do cliente, um turno
  maior.

O ciclo se fecha no cliente. Nenhum dado de conversa atravessa duas requisições pelo lado
do servidor.

---

### Modelo de dados (alto nível)

Entidades principais

- `Page` — uma página lida, antes de dividida. `number` já 1-based.
- `Chunk` — um pedaço indexável com a procedência preservada. Existe para que
  `domain/` não importe o `Document` do LangChain: com `Citation` precisando de `source` e
  `page`, a normalização passaria a existir em três consumidores, e descê-la ao adaptador
  exige que o que sobe já seja domínio puro. Diferença deliberada em relação ao Projeto 1,
  que carregava o `Document` dentro do domínio.
- `Turn` — um par pergunta e resposta já ocorrido. Objeto de valor.
- `Conversation` — sequência ordenada de `Turn`. Objeto de valor, imutável; aplicar a
  janela produz uma `Conversation` nova, não muta a original.
- `SearchHit` — um trecho recuperado, com `source`, `page`, `distance` e o texto.
  `distance` é distância: menor é mais próximo. Chamar de score inverteria a leitura na
  interface.
- `Citation` — a ligação entre um rótulo `[n]` presente no texto gerado e o `SearchHit`
  que ele referencia. Entidade nova deste projeto.
- `RewriteDecision` — a query usada na busca, a original, e se houve chamada de LLM e por
  quê. Existe para tornar o critério 2 do PRD observável, não como conveniência de log.
- `Answer` — texto, citações, **rótulos não resolvidos** (`unresolved_labels`, que
  sustenta a invariante 4: nenhum `[n]` some em silêncio), trechos, indicador de recusa,
  decisão de reescrita, tempos. **`refused` é campo de domínio, calculado na
  `QueryFacade`**, e não cálculo do presenter como era no Projeto 1: a invariante "recusa
  não cita" precisa valer onde a decisão é tomada, e uma invariante que só existe na
  apresentação não vale em lugar nenhum.
- `IngestionReport` — páginas, chunks, descartes, parâmetros, tempo.
- Chunk indexado — texto e metadados (`source`, `page`), no Qdrant.

Relações

- `Conversation` contém zero ou mais `Turn`, ordenados.
- `Answer` contém zero ou mais `Citation`; cada `Citation` referencia exatamente um
  `SearchHit` do mesmo `Answer`.
- `Answer` contém exatamente uma `RewriteDecision`.
- Uma `Answer` recusada tem `citations` vazia. Se vier recusa com citação, há defeito.

Fonte de verdade

- **Do corpus:** os PDFs em `pdfs/`. O índice no Qdrant é derivado e descartável;
  `docker compose down -v` seguido de reindexação reconstrói.
- **Da conversa:** o cliente. Não há cópia no servidor, e portanto não há divergência
  possível entre duas cópias. É o principal ganho operacional da decisão de sessão.

Versionamento e retenção

- Índice: sem versionamento. A ingestão recria a coleção; o relatório informa quantos
  chunks foram descartados da anterior.
- Conversa: retenção é do cliente. A CLI descarta ao encerrar o processo; o frontend
  descarta ao recarregar. Persistência está fora de escopo pelo PRD.

---

### Interfaces públicas

| Nome | Tipo | Protocolo | Exposição | SLAs/Limites |
| --- | --- | --- | --- | --- |
| `GET /health` | API | REST/JSON | Interna, `127.0.0.1` | Sem chamada paga. Reporta coleção e contagem de chunks. |
| `GET /capabilities` | API | REST/JSON | Interna, `127.0.0.1` | Declara `features: [ask, ingest, history]` e os parâmetros `k`, `chunk_size`, `chunk_overlap`, `history_window`, `conditional_rewrite`. |
| `POST /ask` | API | REST/JSON | Interna, `127.0.0.1` | Aceita `options.history`. Latência dominada por dois estágios de LLM; sem meta formal. |
| `POST /ingest` | API | REST/JSON | Interna, `127.0.0.1` | Destrutiva: recria a coleção. O frontend confirma antes. |
| `ingest.py`, `ask.py`, `chat.py` | CLI | argv, stdout/stderr | Local | stdout carrega o resultado, stderr o diagnóstico. |

**Evolução do contrato compartilhado para 1.1.0.** Três acréscimos, todos opcionais, sem
tocar em nenhum campo obrigatório, conforme a regra de evolução do próprio contrato:

- `history` na requisição de `/ask`, dentro de `options`: lista de turnos.
- `citations` no `Answer`: cada item liga um rótulo ao trecho que o sustenta.
- `rewritten_question` (e a decisão que a produziu) no `Answer`.

A promoção ao contrato compartilhado, em vez de esconder tudo em `meta`, é deliberada:
nenhum dos três é idiossincrasia do Projeto 2. Os Projetos 3 a 10 vão querer citação e
conversa, e um campo em `meta` não pode ser renderizado por um frontend genérico sem que
alguém ensine o frontend caso a caso, que é o acoplamento que o contrato existe para
evitar. O Projeto 1 continua válido sem alteração: campos opcionais que ele não emite.

Resolução de `[n]`: o rótulo é resolvido por `citations`, não pela posição em `hits`.
Amarrar à posição pareceria mais barato e é a armadilha central deste projeto: qualquer
dedup ou reordenação de `hits` faria `[3]` apontar para o trecho errado sem erro nenhum,
produzindo uma citação que parece verificada e não está.

---

### Considerações de escalabilidade e disponibilidade

Abordagem geral

Não há requisito de escala. Um usuário, uma máquina, uso interativo. Registrar isto é
parte do design: escalar antes de precisar acrescentaria camadas que escondem o mecanismo
que o projeto existe para ensinar.

O que **é** tratado, porque afeta o custo e a qualidade em uso normal:

Técnicas aplicadas

- **Janela de histórico** como controle de contexto. Conversa longa estoura o contexto e,
  pior, degrada a reescrita: com vinte turnos, o modelo tem material demais para escolher
  a referência errada. Truncar é a mitigação, e medir a degradação é o critério 6.
- **Reescrita condicional** como controle de custo. Cada turno custa uma chamada de LLM a
  mais que no Projeto 1. Pular a reescrita quando a pergunta já é autossuficiente evita
  parte disso, e o critério 5 exige medir quanto e registrar ao menos um caso em que a
  heurística errou.
- Primeiro turno nunca reescreve. Sem histórico não há o que resolver.
- Embeddings em lote na ingestão.
- Verificação de pré-condições antes da primeira chamada paga.

Meta de disponibilidade

- Nenhuma formal. O critério operacional é: quando uma dependência está fora do ar, a
  mensagem diz **qual** e **o que fazer**, em vez de um traceback.

---

### Segurança

Autenticação

- Nenhuma, por decisão de escopo. A API escuta em `127.0.0.1` e serve o frontend local do
  mesmo usuário. Expor em `0.0.0.0` invalidaria a premissa e exigiria HLD novo.

Autorização

- Nenhuma. Um único perfil.

CORS

- `allow_origin_regex` restrito a `http://(localhost|127.0.0.1):<qualquer porta>`, métodos
  `GET` e `POST`, `allow_headers=["*"]`. Existe porque o frontend roda em outra porta
  (Vite usa 5173) e o navegador exige.
- É superfície pública e por isso está registrada aqui. A permissividade de porta é
  aceitável **apenas** enquanto a API escuta em `127.0.0.1`: qualquer processo local já
  alcançaria a API diretamente, então o CORS não é a fronteira de segurança. Expor em
  `0.0.0.0` mudaria isso e exigiria fechar a origem.

Proteção de dados

- Sem criptografia em repouso: índice local em volume Docker, corpus local.
- Em trânsito: HTTPS nas chamadas à OpenAI, feito pelo SDK. Tráfego local em HTTP puro.
- **PII e conteúdo do corpus:** o corpus previsto é texto normativo público, sem dado
  pessoal. Registrado como premissa: indexar documento com PII mudaria a avaliação, porque
  o conteúdo dos chunks é enviado à OpenAI a cada consulta.
- **A transcrição da conversa passa a trafegar a cada requisição.** Em rede local sem
  autenticação isso é aceitável apenas porque não há segundo usuário. É a premissa que
  torna a decisão de sessão barata, e a que a invalidaria se mudasse.

Gestão de segredos

- Chave da OpenAI em `.env`, carregada por `python-dotenv`. `.env` coberto pelo
  `.gitignore` da raiz; o `docs/gitflow.md` traz a verificação antes do primeiro `git add`.
- Nenhum segredo em log, em mensagem de erro ou no descritor de `/capabilities`.

---

### Observabilidade

Logs

- **Não há logging estruturado.** O que existe é diagnóstico em prosa no
  `ConsoleReporter`, em stderr, separado do resultado em stdout, e **apenas nas CLIs**: a
  camada HTTP não emite log nenhum, e as métricas existem só dentro do corpo da resposta.
  A seção 7 do FDD detalha campo a campo o que sai e o que não sai.
- É pendência declarada, não esquecida. Não bloqueia nenhum critério de aceite deste
  projeto, porque em uso interativo com um usuário o `ConsoleReporter` cumpre o papel, mas
  bloqueia qualquer agregação entre requisições, inclusive a taxa de recusa por posição no
  turno que a lista de métricas abaixo prevê.
- Nenhum log de conversa em disco. Não haveria onde guardar sem contrariar a decisão de
  sessão.

Métricas

- Latência por estágio, exposta em `timings` da resposta: reescrita, busca, geração. Três
  estágios, não dois: o custo novo deste projeto precisa ser atribuível.
- Chamadas de LLM por turno, e quantas a reescrita condicional evitou. É a métrica do
  critério 5, e por isso é produto, não instrumentação acessória.
- Taxa de recusa, segmentada por corpus indexado e corpus de controle, e por posição no
  turno. Recusa que cai do turno 1 para o turno 3 é o defeito que o critério 4 procura.
- Distância do melhor trecho recuperado, antes e depois da reescrita.

Tracing

- Sem tracing distribuído: processo único. Os `timings` por estágio cumprem o papel.

Dashboards e alertas

- Nenhum. Um usuário interativo lê a saída. O `ConsoleReporter` imprimir a query reescrita
  e as distâncias substitui um painel nesta escala.

---

### Riscos arquiteturais e mitigação

#### A reescrita legitima uma pergunta fora do corpus

- **Probabilidade:** média
- **Impacto:** alto, e específico deste projeto. Uma pergunta sobre o corpus de controle
  ("e o artigo seguinte?") pode ser reescrita usando o histórico até virar uma pergunta que
  parece pertencer ao corpus indexado. A busca então devolve trechos plausíveis mas
  errados, e o sistema responde em vez de recusar. É a falha que o critério 4 do PRD
  existe para caçar, e ela não existia no Projeto 1.
- **Mitigação:**
  - Instruir explicitamente o prompt de reescrita a não introduzir assunto ausente da
    pergunta original: ele resolve referências, não completa lacunas.
  - Manter a recusa como decisão do estágio de geração, sobre os trechos efetivamente
    recuperados, e nunca do estágio de reescrita.
  - Cobrir a matriz de recusa com pytest e dublês: turnos 1, 2 e 3, dentro e fora do
    corpus, com e sem reescrita.
  - Registrar a query reescrita em toda resposta, para que o caso seja diagnosticável
    depois do fato.
- **Plano de contingência:** desligar a reescrita por parâmetro e comparar. Se a recusa
  volta com a reescrita desligada, o defeito está no prompt de reescrita, e o lugar da
  correção fica identificado sem adivinhação.

#### Citação inventada ou mal resolvida

- **Probabilidade:** média
- **Impacto:** alto. Uma citação errada é pior que nenhuma: ela transfere confiança que
  não foi conquistada. O caso mais perigoso não é o modelo inventar `[7]` quando só há
  quatro trechos, que é detectável, mas `[2]` apontar para o trecho errado, que não é.
- **Mitigação:**
  - Numerar os trechos e pedir referência por número, não por nome de arquivo. Copiar um
    rótulo é mais confiável que gerar um identificador.
  - Resolver `[n]` por `citations` explícitas, nunca pela posição em `hits`.
  - Validar no `CitationResolver` que todo rótulo citado existe entre os recuperados, e
    sinalizar quando não existir em vez de silenciar.
  - Conferência manual, cinco vezes, como critério 3 do PRD. Nesta altura da trilha não
    há avaliação automatizada, e fingir que há seria pior.
- **Plano de contingência:** se a taxa de citação incorreta for alta, reduzir `k`. Menos
  trechos, menos oportunidade de confundir, ao custo de recall.

#### Custo dobrado por turno

- **Probabilidade:** alta, é o comportamento esperado
- **Impacto:** médio. Dois estágios de LLM por turno, e um REPL convida a conversas
  longas. O custo por sessão cresce mais rápido do que a intuição do Projeto 1 sugere.
- **Mitigação:**
  - Reescrita condicional, com o ganho medido (critério 5).
  - Primeiro turno nunca reescreve.
  - `timings` e contagem de chamadas visíveis em toda resposta.
  - Limite de gasto mensal na conta OpenAI, antes da primeira execução.
- **Plano de contingência:** desligar a reescrita e operar como o Projeto 1, aceitando a
  quebra no segundo turno, até que o custo seja revisto.

#### Degradação silenciosa da reescrita em conversa longa

- **Probabilidade:** média
- **Impacto:** médio. Com muitos turnos, a reescrita passa a resolver o pronome contra a
  referência errada. A pergunta reescrita sai bem formada e sobre o assunto errado, o que
  é justamente o que não dispara suspeita.
- **Mitigação:**
  - Janela de histórico, com valor padrão conservador.
  - A query reescrita sempre visível: é o que torna a falha percebível.
  - Experimento do critério 6, em branch `exp/`, com a degradação anotada.
- **Plano de contingência:** reduzir a janela.

#### Distância alta confundida com ausência de resposta

- **Probabilidade:** média
- **Impacto:** médio. Herdado do Projeto 1 e agravado aqui: a busca sempre devolve `k`
  trechos, mesmo quando nenhum serve. Com histórico no prompt, o modelo tem contexto extra
  para preencher a lacuna com o que já sabe.
- **Mitigação:**
  - Frase de escape explícita no prompt e campo `refused` na resposta.
  - Distância do melhor trecho sempre reportada, junto da resposta.
  - Corpus de controle fora do índice, que torna o teste negativo executável e não
    hipotético.
- **Plano de contingência:** limiar de distância acima do qual a facade recusa antes de
  gastar a chamada de geração. Não entra agora: escolher o limiar sem medição seria
  arbitrário.

#### Fronteira do armazém vetorial vazando

- **Probabilidade:** baixa
- **Impacto:** médio, e mensurável. O critério 7 do PRD exige que trocar Qdrant por Chroma
  seja uma linha no composition root. Se exigir mais, `VectorRepository` deixou passar
  detalhe do Qdrant, e o mesmo vazamento vai custar caro nos projetos 3, 6 e 7.
- **Mitigação:**
  - `Protocol` na fronteira, com mypy rodando limpo.
  - Nomes do `Protocol` em termos do domínio, não do Qdrant: nada de `payload`,
    `point_id` ou `collection_config` atravessando para cima.
  - Fazer a troca de fato, como critério de aceite, e não deixá-la como intenção.
- **Plano de contingência:** se vazar, registrar em ADR o que vazou e por quê, antes de
  consertar. A guideline diz que conhecer a diferença entre armazéns é objetivo declarado
  da trilha, então o vazamento pode ser informação, não só defeito.

#### Incompatibilidade de dimensão ao trocar o modelo de embedding

- **Probabilidade:** baixa
- **Impacto:** alto. Herdado do Projeto 1. Coleção criada com 1536 dimensões não aceita
  vetor de outra dimensão, e o erro do cliente costuma ser obscuro.
- **Mitigação:**
  - `HealthChecker` compara o modelo configurado com o registrado na coleção antes da
    primeira consulta.
  - `/health` reporta modelo e dimensões.
- **Plano de contingência:** recriar a coleção e reindexar. O índice é derivado.

#### Falha de infraestrutura confundida com falha do pipeline

- **Probabilidade:** média
- **Impacto:** médio. Qdrant fora do ar produz sintoma parecido com índice vazio, e num
  projeto de estudo isso custa uma tarde de depuração no lugar errado.
- **Mitigação:**
  - Healthcheck no `docker-compose.yml`, verificado contra a imagem escolhida.
  - `HealthChecker` distinguindo "serviço não responde" de "coleção vazia".
  - Mensagens de erro que dizem o comando a rodar, no formato `Problem` do contrato.
- **Plano de contingência:** `docker compose up -d qdrant` e reindexar.

#### Vazamento da chave da OpenAI

- **Probabilidade:** baixa
- **Impacto:** alto. Chave em repositório público é explorada em minutos.
- **Mitigação:**
  - `.gitignore` da raiz cobre `.env`; verificação no `docs/gitflow.md`.
  - `.env.example` sem valor real.
  - Nenhum segredo em log ou mensagem de erro.
- **Plano de contingência:** revogar e rotacionar.

---

### ADRs e próximos passos

ADRs associados

Herdados do Projeto 1 como precedente conceitual, não como vínculo: os ADR-001 a 009 do
`rag-01-fundamentos-pdf` valem para aquele repositório. Este projeto registra os seus.

Registrados em `docs/adrs/generated/RAG/`:

- **ADR-001** Qdrant como armazém vetorial, em container, substituindo o Chroma do
  Projeto 1
- **ADR-002** Conversa fora do servidor: o cliente é dono da transcrição
- **ADR-003** Conversa como objeto de valor em `domain`, e não `ConversationMemory` em
  `service` (divergência declarada em relação à seção 5 da guideline de arquitetura)
- **ADR-004** Citação resolvida por `citations` explícitas, não pela posição em `hits`
- **ADR-005** Evolução do contrato compartilhado para 1.1.0 com três campos opcionais
- **ADR-006** `chat.py` como quarto entrypoint, preservando `ask.py` de turno único
- **ADR-007** O estágio de resposta recebe a pergunta resolvida, com a literal ao lado.
  Nasceu de um defeito encontrado na validação, não do desenho prévio.

Decisões que o FDD fechou

- Heurística da reescrita condicional: léxica, com precedência definida (comprimento vence
  marcador). Ver contrato 6 do FDD.
- Janela padrão: seis turnos. Mantida depois do experimento do critério 6, que revelou que
  janela **curta** demais também degrada, por truncar o antecedente.
- `conditional_rewrite` nasce desligado: o caminho correto e mais caro é o padrão.

Decisões ainda pendentes

- Limiar de distância para recusa antecipada. Continua fora de escopo: escolher o limiar
  sem medição sistemática seria arbitrário, e medição sistemática entra no Projeto 3.
- Calibragem do limiar de recusa do modelo. A validação observou cerca de um terço de
  recusas em perguntas que o corpus sustentava, com `k=4` e busca puramente densa. É a
  limitação que o Projeto 3 existe para resolver.

Próximos passos

- Conferência visual da conversa no frontend, no navegador. Único critério de aceite ainda
  parcial.
- Refazer a validação com corpus normativo, se e quando ele existir: o corpus atual é o do
  Projeto 1, e narrativa gera menos follow-up dependente de contexto que norma.
- Logging estruturado da seção 7 do FDD, ainda não implementado.
