### FDD: Funil de recuperação híbrido

Versão: 1.0
Data: 2026-07-28
Responsável: Arthur Diego (autor único)

Escopo de negócio no PRD da feature
(`.compozy/tasks/funil-recuperacao-hibrido/_prd.md`) e no catálogo de stories
(`_user_stories.md`). Este documento é o **como** técnico e não repete a narrativa de lá.

---

### 1. Contexto e motivação técnica

O estágio de recuperação do pipeline herdado do Projeto 2 tem um único caminho: kNN denso
sobre embeddings. Isso produz uma falha estrutural e medida. O Projeto 2 registrou que
cerca de um terço das perguntas factuais recebia recusa apesar de existir passagem
indexada que as sustentava: com `k=4` sobre 617 trechos, o trecho certo não entrava nos
quatro.

A causa é conhecida e documentada na literatura. Embeddings representam significado, e
termos literais não têm significado a representar. Em *EntityQuestions* (Sciavolino et al.,
EMNLP 2021), a acurácia de recuperação em top-20 para perguntas simples sobre entidades é
de 72,0% para BM25 contra 49,7% para recuperação densa, e o desempenho denso cai
monotonicamente conforme a entidade fica mais rara.

**Encaixe no HLD.** A feature vive inteiramente dentro do estágio de recuperação. O
`RetrievalService` deixa de ser um repassador de chamada ao repositório e passa a ser o
dono de um funil de quatro etapas. A `QueryFacade` não ganha nenhuma responsabilidade nova
de orquestração: ela continua chamando os mesmos estágios na mesma ordem, sem saber que a
recuperação virou funil. O que muda nela é transporte de métrica, conforme o ADR-007.

**Atores.**

- Os quatro entrypoints (`ingest.py`, `ask.py`, `chat.py`, `serve.py`), inalterados em
  papel.
- Elasticsearch em container, atendendo os dois caminhos de busca sobre o mesmo índice.
- API de embeddings da OpenAI, para a ingestão e para a query do caminho denso.
- Cross encoder local, carregado uma vez por processo.
- O frontend compartilhado do workspace, que descobre os controles novos sozinho.

**Limites.** A feature não toca reescrita, montagem de prompt, geração nem resolução de
citação. Não toca autenticação (não existe), nem persistência de conversa (não existe).

**Suposições explícitas.**

- Um usuário por vez. Concorrência não é caso tratado, e isso está registrado.
- A máquina não tem GPU. Todo o custo de reordenação é de processador comum.

**Restrições explícitas.** Os oito ADRs do projeto (`docs/adrs/generated/RAG/`) e os
quatro ADRs de produto do PRD são vinculantes.

---

### 2. Objetivos técnicos

- **Fusão promove o consenso.** Um trecho presente nos dois rankings recebe a soma das duas
  contribuições e fica acima de trechos presentes em um só. Invariante verificável por
  teste da função pura, sem dublê de infraestrutura.
- **Fusão depende de posição, nunca de valor.** Multiplicar todos os scores de um dos
  rankings por uma constante não altera o resultado da fusão. É o teste que prova que a
  implementação é RRF e não soma disfarçada.
- **Reordenação manda na ordem final.** A saída do estágio de rerank reflete a pontuação do
  cross encoder, e não a ordem de entrada. Verificável com dublê de reranker que inverte.
- **Deduplicação por identidade do documento.** Dois trechos distintos com o mesmo prefixo
  de texto contam como dois. Um mesmo documento em dois rankings conta como um.
- **Custo atribuível por estágio.** Cada resposta carrega tempo separado de busca densa,
  busca léxica, fusão e reordenação. Estágio que não executou aparece **ausente**, nunca
  zerado.
- **Citação sobrevive à reordenação.** Nenhuma reordenação ocorre depois da numeração do
  contexto. Invariante herdado do ADR-004 do Projeto 2, que a feature torna crítico.
- **Índice mal mapeado é detectado.** Campo de texto não analisado é reportado, e não
  degrada em silêncio.
- **Determinismo.** Mesma pergunta, mesmos parâmetros e mesmo índice produzem o mesmo
  ranking. Sem isso a tabela de medição não mede.

---

### 3. Escopo e exclusões

**Incluído**

- Mapping explícito do índice, com `dense_vector` e campo de texto analisado em português,
  criado pelo sistema e nunca inferido pelo motor.
- Adaptador de busca densa e adaptador de busca léxica, dois `Protocol` distintos sobre o
  mesmo índice.
- `FusionService`, função pura de RRF com deduplicação por identidade do documento.
- `RerankService` como `Protocol`, com implementação local em cross encoder.
- `RetrievalService` reescrito como dono do funil, devolvendo resultado com métrica.
- Parâmetros novos `candidates`, `rrf_k`, `hibrida` e `rerank`, com faixa e validação.
- Contrato compartilhado elevado a 1.2.0, aditivo.
- Procedência por trecho, no console e no JSON.
- Conferência de mapping no `HealthChecker`, com endpoint de saúde adequado ao
  Elasticsearch.
- Harness de medição em `docs/operations/`, com perguntas e páginas esperadas em arquivo de
  dados.
- Testes com dublês para fusão, funil de rerank e deduplicação.

**Excluído**

- Os oito Non-Goals do PRD, com destaque para: substituibilidade do armazém como critério
  (ADR-004 da feature), fusão nativa do motor, segunda implementação de rerank por API,
  execução concorrente dos dois caminhos, e logging estruturado.
- `top_n` como parâmetro novo. O `k` existente **é** o corte final do funil; criar um
  segundo nome para a mesma grandeza seria dívida imediata.
- Migração de dados do Qdrant para o Elasticsearch. O índice é derivado; reindexa se.

---

### 4. Fluxos detalhados e diagramas

**Fluxo principal, consulta**

1. O entrypoint recebe pergunta, transcrição e opções, e monta a facade.
2. `QueryFacade.ask` chama `QueryRewriteService.decide`, que devolve a pergunta resolvida.
   Inalterado.
3. `QueryFacade` chama `RetrievalService.retrieve` com a pergunta resolvida. **Não
   cronometra o estágio.**
4. `RetrievalService` valida as faixas de `k`, `candidates` e `rrf_k`, e a relação
   `k <= candidates`.
5. `RetrievalService` chama `VectorRepository.search`, que embeda a pergunta e busca os
   `candidates` vizinhos mais próximos. Cronometra em `dense_s`.
6. Se `hibrida` estiver ligado, `RetrievalService` chama `KeywordRepository.search`, que
   busca os `candidates` melhores por BM25 sobre o mesmo índice. Cronometra em `keyword_s`.
7. `RetrievalService` entrega os rankings a `FusionService.fuse`, que soma
   `1 / (rrf_k + posição + 1)` por aparição, deduplica por identidade de documento e
   ordena. Cronometra em `fusion_s`.
8. Se `rerank` estiver ligado, `RetrievalService` chama `RerankService.rerank` com a
   pergunta e os candidatos fundidos, e corta em `k`. Cronometra em `rerank_s`. Se estiver
   desligado, corta os fundidos em `k` direto.
9. `RetrievalService` devolve `RetrievalResult`, com os hits finais e os quatro tempos.
10. `QueryFacade` segue inalterada: `PromptBuilder` numera, `GenerationService` gera,
    `CitationResolver` resolve. A numeração acontece **depois** de o funil ter terminado,
    e nada reordena a partir daqui.

**Fluxo de ingestão**

1. `DocumentReader` lê `pdfs/*.pdf`, glob não recursivo, e devolve páginas 1-based e a
   contagem de descartes, numa passada.
2. `IngestionFacade` conta o índice anterior, **antes** de destruir.
3. O adaptador destrói o índice e cria o novo com **mapping explícito**.
4. `ChunkingService` divide; os trechos são embedados e gravados como um documento cada,
   carregando vetor, texto analisado, fonte e página.
5. O relatório mantém os mesmos números do Projeto 2.

A ordem "conta, checa PDFs, destrói, lê, grava" é herdada e testada: falha depois da
destruição deixa o índice vazio, cujo sintoma é evidente, e nunca desatualizado, cujo
sintoma não existe.

**Fluxos alternativos e exceções**

- `hibrida` desligado: passo 6 é pulado; a fusão recebe um ranking só e o RRF sobre uma
  lista devolve a mesma ordem. `keyword_s` fica **ausente**.
- `rerank` desligado: passo 8 vira corte simples. `rerank_s` fica **ausente**.
- `hibrida` ligado e `rerank` desligado: a coluna "híbrida" da tabela.
- `hibrida` desligado e `rerank` desligado: a coluna "só densa", linha de base equivalente
  ao Projeto 2.
- **`hibrida` ligado e denso desligado não existe:** o caminho denso é sempre executado. O
  diagnóstico "só BM25" é obtido pelo harness, que consulta o `KeywordRepository`
  diretamente, e não por combinação de parâmetros públicos.
- Um dos caminhos devolve lista vazia: a fusão prossegue com o outro.
- Os dois devolvem vazio: o fluxo segue e a geração produz recusa, sem citação.
- Motor de busca cai no meio: erro de indisponibilidade, sem resultado parcial.

**Diagramas.** Gerados em `docs/domains/rag/diagrams/`: fluxo do funil, sequência da
consulta, componentes, e fluxo da ingestão com o mapping explícito.

---

### 5. Contratos públicos

#### 5.1 `POST /ask`

- Tipo: endpoint HTTP
- Rota: `POST /ask`
- Contrato compartilhado: `../docs/contracts/rag-api.yaml`, **versão 1.2.0**

**Parâmetros novos em `options`** (todos opcionais):

| Nome | Tipo | Padrão | Faixa | Semântica |
| --- | --- | --- | --- | --- |
| `hibrida` | boolean | `true` | - | Liga o caminho BM25. Desligado, só o caminho denso alimenta a fusão |
| `rerank` | boolean | `true` | - | Liga a reordenação por cross encoder |
| `candidates` | integer | `20` | 1 a 50 | Candidatos buscados **por caminho** |
| `rrf_k` | integer | `60` | 1 a 1000 | Amortecimento da fusão |

`k` **não é parâmetro novo.** O `k` existente desde 1.0.0 (rótulo "Chunks recuperados",
padrão 4, máximo 20) é o corte final do funil, e mantém exatamente esse significado.

O teto de `candidates` é 50 e não 100 por decisão de latência: o custo do cross encoder é
aproximadamente linear no número de pares, e 100 candidatos em processador comum sairiam da
faixa em que o uso interativo é praticável. O teto é revisável com a primeira medição real.

**Campos novos na resposta** (todos opcionais):

- `timings.dense_s`, `timings.keyword_s`, `timings.fusion_s`, `timings.rerank_s`. O
  `timings.search_s` existente **mantém o significado**: tempo total do estágio de
  recuperação. Os quatro campos novos o decompõem.
  *Refinamento em relação ao ADR-005*, que previa três campos novos: `dense_s` entra como
  quarto porque, com `search_s` significando o total, o tempo do caminho denso ficaria sem
  campo próprio.
- `hits[].score`: valor final de ordenação, **maior é melhor**. É o valor do rerank quando
  ele rodou, e o da fusão quando não rodou.
- `hits[].provenance`: objeto com `paths` (lista contendo `densa`, `bm25` ou ambos),
  `dense_rank`, `keyword_rank`, `rrf_score` e `rerank_score`. Ranks são 1-based; campos de
  caminho não executado ficam ausentes.
- `hits[].distance` **é mantido e depreciado**, documentado como válido apenas quando
  `hibrida` e `rerank` estão desligados. **Menor é melhor**, semântica original preservada.

`score` e `distance` nunca compartilham campo, porque têm sentidos opostos. O
`ConsoleReporter`, que hoje imprime "melhor distância" usando o mínimo, precisa escolher o
rótulo pelo que de fato está preenchido.

**Exemplo de requisição**

```json
{
  "question": "O que Nicolau Flamel fabricava?",
  "options": {
    "k": 4,
    "hibrida": true,
    "rerank": true,
    "candidates": 20,
    "rrf_k": 60,
    "history": []
  }
}
```

**Exemplo de resposta** (abreviada)

```json
{
  "text": "Nicolau Flamel é o único fabricante conhecido da Pedra Filosofal [1].",
  "refused": false,
  "hits": [
    {
      "source": "harry-potter.pdf",
      "page": 178,
      "excerpt": "...o único fabricante conhecido da Pedra Filosofal...",
      "score": 8.42,
      "provenance": {
        "paths": ["densa", "bm25"],
        "dense_rank": 3,
        "keyword_rank": 1,
        "rrf_score": 0.032266,
        "rerank_score": 8.42
      }
    }
  ],
  "citations": [
    { "label": 1, "source": "harry-potter.pdf", "page": 178, "excerpt": "..." }
  ],
  "timings": {
    "rewrite_s": 0.41,
    "search_s": 2.13,
    "dense_s": 0.28,
    "keyword_s": 0.04,
    "fusion_s": 0.0002,
    "rerank_s": 1.81,
    "generation_s": 1.12
  }
}
```

**Semântica de status**

- `200`: resposta produzida, inclusive quando `refused` é `true`.
- `409`: índice vazio ou inexistente (`EMPTY_INDEX`), ou índice mal mapeado
  (`INVALID_INDEX_MAPPING`, e apenas quando `hibrida` está ligado).
- `422`: parâmetro fora de faixa, `k` maior que `candidates`, pergunta vazia, ou turno de
  histórico malformado.
- `503`: motor de busca indisponível, ou falha ao preparar o modelo de reordenação.

#### 5.2 `GET /capabilities`

Publica os quatro parâmetros novos no mesmo formato dos existentes, com rótulo em
português, ajuda curta, padrão, faixa e `applies_to: ["ask"]`. Padrões e tetos são
importados de `config.py`, nunca reescritos no descritor. A rota continua sem `Depends`,
para responder com a infraestrutura fora do ar.

#### 5.3 `GET /health`

Passa a reportar o estado do mapping do campo de texto, além da dimensão do vetor. O
endpoint consultado no Elasticsearch é `/_cluster/health`, **não a raiz**: a raiz responde
200 mesmo com o cluster em estado vermelho, e aprovar cluster degradado é exatamente a
confusão que o `HealthChecker` existe para evitar.

#### 5.4 Contratos internos

```python
class KeywordRepository(Protocol):
    def search(self, query: str, k: int) -> list[SearchHit]: ...

class RerankService(Protocol):
    def rerank(self, question: str, hits: list[SearchHit], top_n: int) -> list[SearchHit]: ...

class FusionService:                      # classe concreta; uma implementação não justifica Protocol
    def fuse(self, rankings: list[list[SearchHit]], rrf_k: int) -> list[SearchHit]: ...

class RetrievalService:
    def retrieve(self, query: str) -> RetrievalResult: ...
```

`RetrievalResult` é `NamedTuple` em `domain/models.py`, com `hits` e os quatro tempos
opcionais. `SearchHit` ganha `score: float | None` e `provenance: Provenance | None`.
`Provenance` é `NamedTuple` própria.

`domain/` continua sem importar LangChain e sem conhecer vocabulário do Elasticsearch.

---

### 6. Erros, exceções e fallback

**Matriz de erros**

| Condição | Tratamento | Status | Observação |
| --- | --- | --- | --- |
| Elasticsearch fora do ar | `ServiceUnavailableException` com a receita `docker compose up -d elasticsearch` | 503 | Distinto de índice vazio |
| Cluster respondendo mas degradado | `ServiceUnavailableException` | 503 | Detectado por `/_cluster/health`, não pela raiz |
| Índice vazio ou inexistente | `EmptyIndexException` | 409 | Nasce em `require_index()`, comportamento herdado |
| Campo de texto não analisado **e** `hibrida` ligado | `InvalidIndexMappingException` (nova) com receita de reindexação | 409 | **Não falha com `hibrida` desligado**: a busca densa não depende desse campo |
| Dimensão do embedding divergente | `InvalidConfigurationException` | 500 | Herdado, inalterado |
| `candidates`, `rrf_k` ou `k` fora de faixa | `InvalidParameterException` nomeando parâmetro, valor e faixa | 422 | Validado no construtor do serviço dono |
| `k` maior que `candidates` | `InvalidParameterException` | 422 | Contradição de configuração |
| Pergunta vazia | `InvalidParameterException` | 422 | Herdado |
| Falha ao carregar o cross encoder | `ServiceUnavailableException` | 503 | **Nunca degradar em silêncio para "sem rerank"** |
| Falha da OpenAI ao embedar a query | Herdado do Projeto 2 | 503 | Inalterado |

`InvalidIndexMappingException` precisa entrar na lista ordenada de `error_handlers.py`
**antes** do tratador genérico, senão cai em 500 por omissão.

**Estratégias de resiliência.** Timeout configurado no cliente do Elasticsearch, herdando o
padrão do Projeto 2. Sem retry, sem backoff e sem circuit breaker: um usuário local, e
mascarar falha transitória atrapalharia a medição de latência que é o instrumento do
projeto.

**Política de fallback.** Só existe uma, e é explícita: um caminho de busca que devolve
lista vazia não impede o outro de contribuir. **Não há fallback silencioso de rerank
ligado para desligado**, nem de híbrido para denso. Estágio pedido que não pode rodar é
erro, porque um fallback silencioso aqui produziria a tabela errada.

**Invariantes**

- Resposta com `refused: true` tem `citations` vazia.
- `[n]` nunca é a posição do trecho em `hits`.
- Nenhuma reordenação ocorre depois da numeração do contexto.
- O corpus de controle nunca é indexado.
- `score` e `distance` nunca ocupam o mesmo campo.
- Estágio não executado tem tempo **ausente**, nunca zero.

---

### 7. Observabilidade

**Métricas** (na resposta, por turno)

- `rewrite_s`, `dense_s`, `keyword_s`, `fusion_s`, `rerank_s`, `generation_s`, e
  `search_s` como total do estágio de recuperação.
- Por hit: posição em cada ranking, valor da fusão, valor da reordenação, e caminhos de
  origem.
- No relatório de ingestão: páginas, descartes, trechos, trechos do índice anterior,
  parâmetros de divisão e tempo.

Estas são as métricas que respondem ao exercício 3 do guia e que fornecem o critério
objetivo de reabertura do ADR-006 (paralelizar as buscas). Sem `dense_s` e `keyword_s`
separados, aquela decisão não tem como ser revista com evidência.

**Logs.** Sem logging estruturado. Pendência herdada do Projeto 2, mantida em aberto e
declarada aqui para não ser confundida com esquecimento.

**Tracing.** Ausente. Um processo, sem rede interna e sem serviço a correlacionar.

**Dashboards e alertas.** Nenhum. O painel deste projeto é a tabela de medição, produzida
por `docs/operations/` e conferida à mão.

**Dados sensíveis.** O trecho do corpus aparece em `excerpt`, como já acontecia. Nenhum
trecho sai da máquina no estágio de rerank, porque ele roda local.

---

### 8. Dependências e compatibilidade

| Componente | Versão mínima | Observações |
| --- | --- | --- |
| Python | 3.12.3 | Herdado |
| `langchain` | 1.3.14 | Herdado |
| `langchain-openai` | 1.4.1 | `gpt-4o-mini` e `text-embedding-3-small` |
| `langchain-elasticsearch` | 1.0.0 | Substitui `langchain-qdrant` |
| `sentence-transformers` | 5.6.1 | Cross encoder local, cerca de 500 MB no primeiro uso |
| Elasticsearch | tag fixada no compose | Healthcheck obrigatório, cerca de 30 s até aceitar conexão |
| `fastapi` | 0.140.9 | Guia fixa 0.140.0; Projeto 2 usa 0.140.1 |
| `mypy` | 2.3.0 | Obrigatório: `Protocol` não é verificado em runtime |
| `pytest` | 9.1.1 | Escopo restrito |

`rank-bm25` **não entra** (ADR-001). `langchain-qdrant` sai.

**Garantias de compatibilidade**

- Contrato compartilhado 1.2.0 é **aditivo puro**: todo campo novo é opcional e nenhum
  existente muda de significado. Projetos 1 e 2 permanecem válidos sem alteração.
- `distance` é depreciado, não removido.
- O frontend compartilhado trata ausência de campo como "não exibir", de modo que os
  projetos que não publicam procedência continuam renderizando normalmente.
- `k` mantém rótulo, padrão, faixa e significado.

---

### 9. Critérios de aceite técnicos

1. **Fusão promove consenso.** Teste com dois rankings construídos à mão em que um trecho
   aparece em ambos e outro em um só: o presente nos dois fica acima. Sem infraestrutura.
2. **Fusão ignora escala.** Multiplicar todos os scores de um dos rankings por 1000 não
   altera a saída da fusão.
3. **Deduplicação por identidade.** Dois trechos distintos com os mesmos 200 primeiros
   caracteres contam como dois; o mesmo documento em dois rankings conta como um.
4. **Rerank manda na ordem.** Com dublê de reranker que inverte a pontuação, a ordem final
   sai invertida em relação à entrada.
5. **Corte respeitado.** Com `candidates` maior que o número de trechos existentes, o
   sistema devolve o que há, sem erro; com `k` maior que `candidates`, recusa com 422.
6. **Timings completos e honestos.** Com `hibrida` e `rerank` ligados, os quatro tempos
   estão presentes; com cada um desligado, o tempo correspondente está **ausente** da
   resposta, e não zerado.
7. **Mapping explícito.** Inspeção do índice criado pela ingestão mostra o campo de texto
   analisado, com analisador em português, e o campo vetorial com a dimensão declarada.
8. **Teste de fumaça do BM25.** Busca por um termo raro conhecido do corpus, apenas pelo
   caminho léxico, retorna pelo menos um trecho contendo o termo. Este critério é o que
   impede que a conclusão do projeto seja falsa.
9. **Índice mal mapeado é reportado.** Com um índice criado sem mapping explícito, uma
   consulta com `hibrida` ligado devolve 409 `INVALID_INDEX_MAPPING`, e uma com `hibrida`
   desligado responde normalmente.
10. **Health distingue estados.** Motor fora do ar devolve 503; motor no ar com índice
    ausente devolve 409; cluster degradado não é aprovado como saudável.
11. **Citação sobrevive à reordenação.** Em cinco perguntas com `rerank` ligado, cada `[n]`
    é conferida à mão contra a página real do PDF, e todas conferem. Recusa não traz
    citação.
12. **Compatibilidade preservada.** Os Projetos 1 e 2 rodam sem alteração contra o contrato
    1.2.0, e o frontend atualizado os renderiza sem coluna vazia.
13. **A tabela existe.** O harness produz as 10 perguntas contra as três configurações, com
    acerto medido contra páginas anotadas e taxa de recusa ao lado, e duas execuções
    seguidas produzem a mesma tabela.
14. **Ganho demonstrado, ou ausência de ganho registrada.** Na linha de identificadores, a
    configuração híbrida acerta pelo menos tanto quanto a só densa. Se não acertar mais,
    o resultado é reportado como está, junto do diagnóstico do critério 8.
15. **Suíte e tipos limpos.** `pytest` verde e `mypy` sem erro.

---

### 9.1 Estado da validação (28/07/2026)

Ambiente: Elasticsearch 8.19.10 em container, cluster verde, índice `normas` com
617 trechos de 274 páginas. Reordenador `mmarco-mMiniLMv2-L12-H384-v1`.

| # | Critério | Estado | Evidência |
| --- | --- | --- | --- |
| 1 | Fusão promove consenso | atendido | `tests/test_fusion.py`, trecho nos dois rankings fica acima |
| 2 | Fusão ignora escala | atendido | multiplicar um ranking por 1000 não altera a saída |
| 3 | Deduplicação por identidade | atendido | dois trechos com 380 caracteres iniciais idênticos contam como dois |
| 4 | Reordenação manda na ordem | atendido | `InvertingReranker` inverte a entrada e a saída sai invertida |
| 5 | Corte e faixas | atendido | `k > candidates` recusado; 6 faixas parametrizadas |
| 6 | Tempos ausentes, nunca zero | atendido | `keyword_s` e `rerank_s` ausentes com o estágio desligado |
| 7 | Mapping explícito | atendido | `GET /normas/_mapping`: `text` com analisador `brazilian`, `dense_vector` 1536 `cosine` |
| 8 | Fumaça do BM25 | atendido | 5 termos raros buscados só pelo caminho léxico retornam |
| 9 | Índice mal mapeado é reportado | atendido | índice sintético com `keyword` levanta `InvalidIndexMappingException`; índice bom passa |
| 10 | Health distingue estados | atendido | porta morta 503, índice inexistente 409, cluster saudável 200 |
| 11 | Citação sobrevive à reordenação | atendido | **6 citações conferidas contra o texto da página real** via `pypdf`, 6 conferem; 3 recusas, todas sem citação |
| 12 | Compatibilidade preservada | atendido | rag-02: 74 testes verdes, mypy limpo; rag-01 e rag-02 emitem `distance` incondicionalmente |
| 13 | A tabela existe e repete | atendido | três execuções, mesma tabela |
| 14 | Ganho demonstrado, ou ausência registrada | atendido **como resultado negativo** | ver abaixo |
| 15 | Suíte e tipos limpos | atendido | 107 testes, mypy limpo em 52 arquivos |

**O critério 14 merece leitura cuidadosa.** Ele foi escrito prevendo os dois
desfechos, e o desfecho foi o segundo: **a busca híbrida não demonstrou ganho
neste corpus.**

| | só densa | híbrida | híbrida+rerank |
| --- | --- | --- | --- |
| Acertos (10) | 8/10 | 7/10 | 8/10 |
| Recusas (10) | 3/10 | 2/10 | 5/10 |
| Latência média | 2,68 s | 2,23 s | 3,03 s |

Não é defeito de implementação, e os critérios 7 e 8 são a prova: o mapping está
correto e o BM25 responde sozinho. A causa é a pendência declarada desde o PRD, o
corpus sem identificadores de verdade.

**As duas métricas discordam, e a discordância é o achado mais útil da
validação.** A reordenação melhora o acerto (7/10 para 8/10) e piora a recusa
(2/10 para 5/10). A explicação é uma limitação da medição: o acerto é anotado por
**página**, e os trechos têm 1000 caracteres, então uma página rende vários. O
reordenador escolhe trechos que falam sobre a entidade sem conter a frase que a
responde; a página bate, o acerto é contado, e o modelo corretamente recusa.
Confirmado na conferência do critério 11, onde `I4` e `I5` aparecem como acerto na
tabela e recusaram quando perguntados.

**Portanto a coluna de acertos é otimista e a de recusas é a confiável.** Descer a
anotação de página para trecho é a pendência número 1.

Um achado que nenhum documento previa, e que a validação encontrou: o reordenador
indicado pelo guia da trilha é treinado em inglês, e sobre corpus em português
**derrubava três acertos em dez** (5/10 contra 8/10). Ver `docs/operations/README.md`
e a revisão do ADR-004.

Pendências registradas, em `docs/operations/README.md`: anotação por trecho, troca
de corpus, âncora do `C1`, e logging estruturado.

---

### 10. Riscos e mitigação

#### Mapping inferido faz o BM25 degradar em silêncio

- **Probabilidade:** média
- **Impacto:** alto, e do pior tipo. Metade do funil para de funcionar sem erro nenhum, e a
  conclusão do projeto vira "a híbrida não ajudou" quando a híbrida nunca rodou.
- **Mitigação:**
  - Mapping explícito no código, criado junto com o índice (critério 7).
  - `HealthChecker` confere o tipo do campo e reporta divergência (critério 9).
  - Teste de fumaça buscando termo raro só pelo caminho léxico (critério 8).
  - Erro dedicado com status próprio, inserido antes do tratador genérico.
- **Plano de contingência:** recriar o índice com mapping explícito e reindexar. O índice é
  derivado; o custo é tempo e chamadas de embedding, não perda de dado.

#### Cross encoder carregado por requisição

- **Probabilidade:** alta se não for tratado explicitamente
- **Impacto:** alto. `provide_properties` e `provide_repository` são reconstruídos a cada
  requisição HTTP no Projeto 2. Um provedor ingênuo de `RerankService` carregaria meio
  gigabyte de modelo por `/ask`. É a mesma classe de defeito que o cache do vector store já
  corrigiu uma vez, e lá o comentário no código diz "isto não é micro otimização; é
  dinheiro".
- **Mitigação:**
  - Provedor do reranker com escopo de processo, não de requisição.
  - `rerank_s` medido desde o primeiro turno torna a regressão visível imediatamente: um
    carregamento apareceria como segundos a mais no primeiro número.
- **Plano de contingência:** cache em nível de módulo, seguindo o precedente do `_store()`.

#### Reordenação piorar o resultado neste corpus

- **Probabilidade:** baixa a média
- **Impacto:** médio. No BEIR o ganho médio do rerank é de cerca de +11% em nDCG@10, com
  variância de −26% (Touché-2020) a +47% (FiQA). Existe corpus em que o cross encoder
  degrada o BM25.
- **Mitigação:** as três configurações da tabela isolam o efeito. O `rerank` é desligável
  por parâmetro, não por edição de código.
- **Plano de contingência:** reportar como está. Estágio que piora num corpus específico é
  conhecimento, não defeito a esconder.

#### Latência tornando o uso interativo desagradável

- **Probabilidade:** alta
- **Impacto:** médio. A estimativa é de 1,2 a 3,0 s por turno só de reordenação,
  extrapolada do BEIR sobre hardware não especificado de 2021.
- **Mitigação:**
  - `candidates` exposto, com teto de 50 escolhido por essa razão.
  - `rerank_s` medido, tornando o custo atribuível em vez de sentido.
  - Decisão de produto de manter o estágio ligado por padrão (ADR-001 da feature), com o
    ajuste na mão do usuário.
- **Plano de contingência:** reduzir `candidates`, ou implementar o `RerankService` sobre
  API hospedada, que é o motivo de ele ser `Protocol`.

#### Colisão de escala entre `score` e `distance`

- **Probabilidade:** média
- **Impacto:** médio. O domínio define `distance` como "menor é mais próximo", o
  `ConsoleReporter` imprime o mínimo como "melhor" e um teste existente afirma
  `distance > 0.9` para o caso fora do corpus. Escrever score de fusão ou de rerank nesse
  campo inverteria a leitura em três lugares ao mesmo tempo, sem erro.
- **Mitigação:** campos separados com semânticas declaradas no contrato; o apresentador
  escolhe o rótulo pelo campo preenchido; os testes herdados que afirmam `distance` são
  revisados explicitamente.
- **Plano de contingência:** nenhum necessário se a separação for respeitada desde o
  primeiro commit.

#### Vocabulário do Elasticsearch vazando pelas fronteiras

- **Probabilidade:** média, e com precedente
- **Impacto:** médio. Agora são dois repositórios adaptando o mesmo motor, o que dobra a
  superfície. O Projeto 2 conteve o vazamento do Qdrant a `config.py` e a duas mensagens do
  `HealthChecker`.
- **Mitigação:** `Protocol` nas duas fronteiras; `domain/` sem import do cliente;
  conferência dirigida no fechamento do ciclo.
- **Plano de contingência:** revisão pelo `dd-doc-sync` antes do PR.

---

### 11. Sequenciamento de implementação (Build Order)

| Ordem | Etapa | Depende de | Componentes e arquivos prováveis | Critérios que fecha |
| --- | --- | --- | --- | --- |
| 1 | Fundação de domínio e configuração | - | `rag/domain/models.py` (`SearchHit` com `score` e `provenance`, `Provenance`, `RetrievalResult`, `Answer` com os quatro tempos), `rag/config.py` (constantes `Final` e faixas novas, propriedades do Elasticsearch), `rag/exceptions.py` (`InvalidIndexMappingException`) | 5 (parcial) |
| 2 | Fusão RRF | 1 | `rag/service/retrieval/fusion_service.py`, `tests/test_fusion.py` | 1, 2, 3 |
| 3 | Infraestrutura e mapping | 1 | `docker-compose.yml` (Elasticsearch com healthcheck e tag fixa), `.env.example`, `requirements.txt` | - |
| 4 | Adaptadores de busca | 1, 3 | `rag/repository/vector_repository.py` (kNN, mapping explícito no `recreate`), `rag/repository/keyword_repository.py` (BM25) | 7 |
| 5 | Reranking | 1 | `rag/service/retrieval/rerank_service.py` (`Protocol` mais implementação local), `tests/test_rerank.py` | 4 |
| 6 | Funil no `RetrievalService` | 2, 4, 5 | `rag/service/retrieval/retrieval_service.py`, `tests/test_retrieval.py`, `tests/conftest.py` (dublês novos: repositório léxico, reranker inversor, e um `FakeVectorRepository` com listas distintas por ramo) | 4, 5, 6 |
| 7 | Facade e apresentadores | 6 | `rag/facade/query_facade.py` (deixa de cronometrar), `rag/presenter/json_presenter.py`, `rag/presenter/console_reporter.py` (rótulo por campo preenchido) | 6 |
| 8 | Saúde e matriz de erros | 4, 7 | `rag/service/health_checker.py` (`/_cluster/health` e conferência de mapping), `rag/api/error_handlers.py`, `rag/repository/*` (método novo no `Protocol` para expor o mapping) | 9, 10 |
| 9 | Camada HTTP e descoberta | 7, 8 | `rag/api/descriptor.py`, `rag/api/routes/ask.py`, `rag/api/dependencies.py` (provedor de reranker com escopo de processo) | 5, 6 |
| 10 | Contrato compartilhado | 9 | `../docs/contracts/rag-api.yaml` elevado a 1.2.0 | 12 |
| 11 | Entrypoints e composition root | 9 | `composition.py`, `ingest.py`, `ask.py`, `chat.py` (argumentos novos), `serve.py` | 6 |
| 12 | Frontend | 10 | `frontend/src/` (procedência por trecho, tolerante a ausência) | 12 |
| 13 | Ingestão ponta a ponta | 4, 11 | `rag/facade/ingestion_facade.py`, execução real contra o corpus | 7, 8 |
| 14 | Harness de medição | 11, 13 | `docs/operations/tabela-medicao.py`, `docs/operations/perguntas.json` (perguntas e páginas esperadas) | 13, 14 |
| 15 | Validação e conferência à mão | todas | Execução dos 15 critérios, conferência de citação contra o PDF, `mypy` e `pytest` | 11, 15 |

A ordem privilegia fechar cedo o que é testável sem infraestrutura. A fusão (etapa 2) é o
componente de maior valor por esforço de teste e não depende de container nenhum, então
vem antes de qualquer coisa que exija Elasticsearch no ar. O teste de fumaça do BM25
(critério 8) só é possível a partir da etapa 13, e é o portão que autoriza confiar na
tabela.
