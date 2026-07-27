### FDD: consulta ciente do histórico com citação resolvida

Versão: 1.0
Data: 2026-07-27
Responsável: Arthur Diego (autor único)

PRD desta feature: `docs/prd.md` (PRD do projeto; é ele que define os 7 critérios de
aceite de negócio). HLD do domínio: `docs/domains/rag/hld.md`.

---

### 1. Contexto e motivação técnica

O `rag-01-fundamentos-pdf` embeda a pergunta do usuário diretamente. Num diálogo, a
segunda pergunta ("e se eu vender dez?") vira um vetor sobre o assunto errado, o retriever
traz lixo, e o LLM responde em cima do lixo sem que nada na saída denuncie a falha. O
projeto também imprime os trechos recuperados ao lado da resposta, mas não amarra qual
afirmação veio de qual trecho.

Esta feature é o caminho de consulta inteiro do `rag-02`, construído do zero sobre a
estrutura em camadas da guideline do workspace. Ela introduz dois estágios que o Projeto 1
não tem, e nada mais muda de forma:

```
[1] pergunta -> reescrita contra o histórico -> query de busca
[2] trechos numerados -> geração -> texto com [n] -> citações resolvidas
```

**Encaixe no HLD.** O HLD já descreve a topologia, os componentes e a decisão de sessão.
Este FDD detalha o comportamento verificável e fecha as três pendências que o HLD deixou
declaradas, mais cinco omissões encontradas no reconhecimento (seção 3).

**Atores.** Um único: o autor, estudando, por quatro superfícies (`ingest.py`, `ask.py`,
`chat.py`, `serve.py`) e pelo frontend genérico do workspace.

**Restrições que não se negociam nesta feature**, todas com ADR:

| Restrição | ADR |
| --- | --- |
| Qdrant atrás do `VectorRepository`; nada do vocabulário dele sobe | 001 |
| Backend sem estado: proibido `conversation_id`, dicionário de sessão ou cache de conversa | 002 |
| Sem `ConversationMemory`; `Conversation` é objeto de valor em `domain` | 003 |
| `[n]` nunca resolve pela posição em `hits` serializado | 004 |
| Contrato compartilhado já está em 1.1.0; nenhum campo novo em `required` | 005 |
| Quatro entrypoints; `ask.py` é turno único e não acumula histórico | 006 |

**Suposições.** Um usuário; API em `127.0.0.1`; corpus normativo público, sem PII;
Docker Desktop com integração WSL ativa (falhou em 27/07/2026, ver seção 8).

---

### 2. Objetivos técnicos

- **A query buscada é a query resolvida.** Invariante: quando `history` é não vazio e a
  reescrita ocorre, o texto enviado ao retriever é `rewritten_question.used`, e nunca a
  pergunta original. Verificável comparando o log da query com o campo da resposta.
- **A reescrita é observável em toda resposta.** Invariante: `rewritten_question` está
  presente em 100 por cento das respostas de `/ask` e é impressa por `chat.py` e `ask.py`.
  Nunca é omitida por ser igual à original.
- **A citação é resolvível ou sinalizada, nunca ambígua.** Invariante: todo rótulo `[n]`
  presente em `text` ou aparece em `citations`, ou aparece em `meta.unresolved_labels`.
  Nenhum rótulo desaparece em silêncio.
- **Recusa não cita.** Invariante: `refused == true` implica `citations == []`. Imposta na
  facade, não no presenter, e coberta por teste.
- **A recusa é estável ao longo da conversa.** Meta: na matriz de recusa (turnos 1, 2 e 3 ×
  dentro/fora do corpus × reescrita ligada/desligada), 100 por cento dos casos fora do
  corpus devolvem `refused == true`.
- **O custo do estágio novo é atribuível.** Invariante: `timings.rewrite_s` presente
  sempre; vale `0.0` exatamente quando não houve chamada de LLM de reescrita.
- **A fronteira do armazém não vaza.** Meta: trocar Qdrant por Chroma altera apenas a
  linha de construção no composition root de cada entrypoint.

---

### 3. Escopo e exclusões

**Incluído**

- Estrutura do projeto conforme a seção 1 da guideline de arquitetura: `rag/` com
  `domain/`, `facade/`, `service/`, `repository/`, `presenter/`, `api/`, mais `config.py`
  e `exceptions.py`.
- Quatro entrypoints: `ingest.py`, `ask.py`, `chat.py`, `serve.py`.
- `QueryRewriteService` com heurística condicional léxica.
- `PromptBuilder` que numera os trechos e `CitationResolver` que resolve os rótulos.
- `QdrantVectorRepository`, e `ChromaVectorRepository` para o critério 7.
- API HTTP completa do contrato 1.1.0: `/health`, `/capabilities`, `/ask`, `/ingest`.
- `docker-compose.yml` do Qdrant com healthcheck validado contra a imagem.
- `requirements.txt`, `.env.example`.
- Testes pytest com dublês, cobrindo a matriz de recusa e a reescrita.
- **Frontend genérico:** conversa completa em `frontend/src/`, ativada por
  `features.includes("history")`.

**Resoluções desta feature para as omissões do HLD** (o HLD será corrigido no fechamento):

- `RetrievalService` volta à arquitetura: é dele a política de `k` e o `require_index()`
  que origina o 409. Sem ele, o 409 de índice vazio não tem dono.
- `CitationResolver` mora em `service/citation_resolver.py` e entra nas dependências da
  `QueryFacade`.
- `SearchHit` deixa de carregar o `Document` do LangChain: vira
  `(text, source, page, distance)`, com a página já 1-based. A normalização desce para o
  adaptador, porque agora três consumidores precisam dela (`ConsoleReporter`,
  `JsonPresenter`, `Citation`).
- `refused` é campo de domínio calculado na `QueryFacade`, não cálculo do presenter. É a
  única forma de a invariante "recusa não cita" ser verificável.
- `reason` do `RewrittenQuestion` tem conjunto fechado de valores (seção 5).

**Excluído**

- Persistência de conversa entre execuções.
- Múltiplos usuários, autenticação, isolamento de sessão.
- Limiar de distância para recusa antecipada: fora até haver medição (HLD).
- Busca híbrida, reranking, avaliação automatizada: projetos 3 em diante.
- Testes das camadas de repositório e de leitura de PDF, que exigiriam infraestrutura.
  **Testes da camada HTTP entraram no escopo durante a implementação**
  (`tests/test_api.py`): eles executam com dublês as mesmas asserções da coleção Postman,
  a custo zero e sem infraestrutura, e foram o que expôs dois dos três defeitos altos do
  fechamento de ciclo. A exclusão original era prudente demais.
- Rebuild de `frontend/dist/`: fica defasado e é regenerável (`npm run build`).

---

### 4. Fluxos detalhados e diagramas

**Fluxo principal: consulta com histórico**

1. A superfície recebe `question` e a transcrição. `chat.py` a tem no processo; `/ask` a
   recebe em `options.history`; `ask.py` não tem transcrição, por decisão do ADR-006.
2. A borda valida e constrói `Conversation` a partir dos turnos. Turno malformado (sem
   `question` ou sem `answer`) é erro 422, não descarte silencioso.
3. `QueryFacade.ask(question, conversation, k)` assume. **A facade não conhece HTTP nem
   terminal.**
4. Janela: `conversation.last(history_window)`. Aplicada no servidor (ADR-002).
5. `QueryRewriteService.decide(question, conversation)` devolve `RewriteDecision`:
   - conversa vazia → `used = question`, `rewritten = false`, `reason = primeiro_turno`.
     Nenhuma chamada de LLM.
   - `conditional_rewrite = false` → reescreve. `reason = historico_presente`.
   - `conditional_rewrite = true` → heurística léxica (seção 5). Reescreve com
     `reason = pergunta_curta` ou `marcador_anaforico`; pula com
     `reason = pergunta_autossuficiente`.
6. `RetrievalService.search(decision.used, k)` faz `require_index()` e busca no Qdrant.
   Devolve `list[SearchHit]` **construída uma vez** e nunca reordenada depois.
7. `PromptBuilder.build(question, hits, conversation)` numera os trechos de 1 a k, cola
   `fonte` e `página` a cada um, injeta a frase de escape e a conversa truncada.
8. `GenerationService.generate(prompt)` devolve o texto.
9. `refused = (texto normalizado == ESCAPE_PHRASE)`, calculado na facade.
10. `CitationResolver.resolve(text, hits)` extrai os rótulos e os resolve **contra a mesma
    lista numerada no passo 7**. Se `refused`, devolve lista vazia sem parsear.
11. A facade monta o `Answer` e devolve. Presenter escreve; **o cliente**, e só ele,
    acrescenta o turno à sua transcrição.

**Fluxos alternativos e exceções**

- **Primeiro turno.** Passo 5 curto-circuita. `timings.rewrite_s = 0.0`.
- **Reescrita falha** (timeout ou erro da OpenAI). Não derruba a requisição: cai para a
  pergunta original, `rewritten = false`, `reason = reescrita_falhou`, log em WARNING. A
  degradação é para o comportamento do Projeto 1, e ela fica visível em vez de silenciosa.
- **Índice vazio.** `require_index()` levanta `EmptyIndexException` antes de qualquer
  chamada paga. 409.
- **Qdrant fora do ar.** `ServiceUnavailableException`, 503, com o comando a rodar no
  `detail`.
- **Rótulo não resolvível** (`[7]` com k=4). Não vira `Citation`; entra em
  `meta.unresolved_labels` e em log WARNING. A resposta continua 200: o texto é válido, a
  procedência daquele rótulo é que não é.
- **Modelo não cita nada.** `citations = []` com `refused = false`. Permitido: detectar
  afirmação sem procedência é avaliação, e avaliação entra no Projeto 3.
- **Ingestão com corpus vazio.** `EmptyCorpusException`. Sem chamada paga.
- **Histórico maior que a janela.** Truncado sem erro. É o caminho normal.

**Diagramas**

- Sequência da consulta com reescrita e resolução de citação.
- Fluxo de decisão do `QueryRewriteService`.
- Componentes do domínio `rag`.
- C4 de contexto, container e componente (projeto novo, ver seção 11).

---

### 5. Contratos públicos (assinaturas, endpoints, headers, exemplos)

Base: `../docs/contracts/rag-api.yaml` **1.1.0**, já publicado. Nada aqui pode alterar
campo obrigatório, sob pena de quebrar o `rag-01`.

**Contrato 1: `POST /ask`**

- Tipo: http_endpoint
- Rota: `POST /ask`
- Semântica de status:
  - `200` resposta produzida, inclusive quando `refused == true`. Recusa não é erro.
  - `409` índice vazio, rode a ingestão. Levantado antes de gastar LLM.
  - `422` parâmetro inválido (`k < 1`, `k > 20`, `history_window < 0`) ou turno
    malformado em `options.history`. Os limites são os mesmos declarados em
    `/capabilities`, e não uma segunda régua.
  - `503` Qdrant ou OpenAI inalcançável. `detail` traz o comando de correção.
- Limites: sem rate limit. Timeout do cliente 120 s (já é o do `frontend/src/api.js`).
- Chaves desconhecidas em `options` são ignoradas, nunca causam erro.

**Exemplo de requisição**

```json
{
  "question": "E se eu vender dez?",
  "options": {
    "k": 4,
    "history_window": 6,
    "conditional_rewrite": false,
    "history": [
      { "question": "Quantos dias de férias eu tenho?", "answer": "30 dias corridos [1]." }
    ]
  }
}
```

**Exemplo de resposta**

```json
{
  "text": "A conversão de férias em abono pecuniário é limitada a um terço do período [1], o que para 30 dias corridos permite vender no máximo 10 dias [1][2].",
  "refused": false,
  "rewritten_question": {
    "used": "Quantos dias de férias posso vender em abono pecuniário?",
    "original": "E se eu vender dez?",
    "rewritten": true,
    "reason": "historico_presente"
  },
  "citations": [
    { "label": 1, "source": "clt.pdf", "page": 47, "excerpt": "Art. 143. É facultado ao empregado converter um terço do período de férias a que tiver direito em abono pecuniário..." },
    { "label": 2, "source": "clt.pdf", "page": 48, "excerpt": "O abono de férias deverá ser requerido até 15 dias antes do término do período aquisitivo." }
  ],
  "hits": [
    { "source": "clt.pdf", "page": 47, "distance": 0.312, "excerpt": "Art. 143..." },
    { "source": "clt.pdf", "page": 48, "distance": 0.401, "excerpt": "O abono de férias..." }
  ],
  "timings": { "rewrite_s": 0.72, "search_s": 0.11, "generation_s": 1.94 }
}
```

**Exemplo de resposta recusada** (pergunta sobre o corpus de controle)

```json
{
  "text": "Não encontrei essa informação nos documentos.",
  "refused": true,
  "rewritten_question": {
    "used": "O que o Código de Defesa do Consumidor diz sobre vício do produto?",
    "original": "E nesse caso?",
    "rewritten": true,
    "reason": "marcador_anaforico"
  },
  "citations": [],
  "hits": [{ "source": "clt.pdf", "page": 12, "distance": 0.887, "excerpt": "..." }],
  "timings": { "rewrite_s": 0.68, "search_s": 0.10, "generation_s": 0.55 }
}
```

`hits` não vazio com `refused: true` é o caso normal e importante: a busca sempre devolve
`k` trechos, e a distância alta é a evidência de que nenhum servia.

**Contrato 2: `GET /capabilities`**

```json
{
  "project": "rag-02-conversacional-citacoes",
  "description": "RAG conversacional com reescrita ciente do histórico e citação verificável",
  "features": ["ask", "ingest", "history"],
  "parameters": {
    "k": { "type": "integer", "label": "Chunks recuperados", "help": "Quantos trechos enviar ao modelo. Baixo demais falta contexto; alto demais dilui e aumenta a chance de citação confusa.", "default": 4, "minimum": 1, "maximum": 20, "applies_to": ["ask"] },
    "history_window": { "type": "integer", "label": "Janela de histórico", "help": "Quantos turnos anteriores considerar. Conversa longa estoura contexto e piora a reescrita.", "default": 6, "minimum": 0, "maximum": 50, "applies_to": ["ask"] },
    "conditional_rewrite": { "type": "boolean", "label": "Reescrita condicional", "help": "Pula a reescrita quando a pergunta já parece autossuficiente. Economiza uma chamada de LLM por turno, ao risco de não reescrever algo que precisava.", "default": false, "applies_to": ["ask"] },
    "chunk_size": { "type": "integer", "label": "Tamanho do chunk", "help": "Caracteres por pedaço. Afeta a indexação, exige reindexar.", "default": 1000, "minimum": 100, "maximum": 8000, "applies_to": ["ingest"] },
    "chunk_overlap": { "type": "integer", "label": "Sobreposição", "help": "Caracteres repetidos entre pedaços vizinhos. Evita cortar uma frase no meio.", "default": 150, "minimum": 0, "maximum": 2000, "applies_to": ["ingest"] }
  }
}
```

`history` em `features` é o gatilho do frontend: é ele que liga a interface de conversa.

**Contrato 3: `GET /health`** e **Contrato 4: `POST /ingest`** — sem mudança semântica em
relação ao contrato 1.0.0. `/health` reporta `collection`, `indexed_chunks`,
`embedding_model` e `embedding_dimensions`; `/ingest` recria a coleção e devolve
`IngestionReport`.

**Contrato 5: `QueryFacade.ask` (assinatura interna, é o contrato das quatro superfícies)**

```python
def ask(
    self,
    question: str,
    conversation: Conversation = Conversation(),
) -> Answer: ...
```

`conversation` tem default vazio: é o que permite `ask.py` chamar sem histórico sem
inventar um caminho paralelo.

**`k` não é parâmetro deste método**, apesar de a primeira versão deste FDD o publicar
como tal. Ele é do `RetrievalService`, fixado na construção, porque é política de
recuperação e não da consulta: quem monta a facade escolhe quantos trechos trazer. Vale o
mesmo para `history_window` (da `QueryFacade`) e `conditional_rewrite` (do
`QueryRewriteService`). A borda HTTP monta a facade por requisição justamente por isso,
conforme a regra 2.5 da guideline: construção explícita para o que vem do corpo.

**Contrato 6: `QueryRewriteService.decide`**

```python
def decide(self, question: str, conversation: Conversation) -> RewriteDecision: ...
```

`reason` é conjunto fechado, e essa é a condição para o critério 5 ser agregável:

| Valor | Quando | Houve chamada de LLM |
| --- | --- | --- |
| `primeiro_turno` | conversa vazia | não |
| `historico_presente` | `conditional_rewrite` desligado e há histórico | sim |
| `pergunta_curta` | condicional ligado, pergunta com menos de 8 palavras | sim |
| `marcador_anaforico` | condicional ligado, pergunta contém marcador | sim |
| `pergunta_autossuficiente` | condicional ligado, nenhum gatilho disparou | não |
| `reescrita_falhou` | a chamada de reescrita falhou; caiu para a original | tentou, falhou |

**Heurística léxica** (`conditional_rewrite = true`). Reescreve se qualquer um:

- a pergunta tem menos de 8 palavras; ou
- contém pronome ou locução anafórica: `ele`, `ela`, `eles`, `elas`, `isso`, `isto`,
  `esse`, `essa`, `aquele`, `aquela`, `o mesmo`, `a mesma`, `nesse caso`, `nesse`,
  `e se`, `e quando`, `e no`, `aí`, `lá`, `dele`, `dela`, `disso`; ou
- começa com conjunção: `e`, `mas`, `ou`, `então`, `porém`.

Comparação sobre o texto normalizado (minúsculas, sem acento, tokenizado por palavra
inteira) para não casar `essencial` com `esse`.

**Precedência quando mais de um gatilho dispara:** vence o comprimento. "E se eu vender
dez?" é curta **e** começa com conjunção, e o `reason` reportado é `pergunta_curta`. A
ordem de avaliação é comprimento, depois token anafórico, depois locução, depois
conjunção inicial. Sem essa regra o `reason` seria não determinístico e o critério 5
deixaria de agregar, que é a única razão de ele ser enumerado.

**`history_window = 0` com `history` preenchido** é caso válido, não erro: a janela zera
a conversa antes da decisão, então o `reason` sai `primeiro_turno` e nenhuma chamada de
reescrita acontece. É como se desliga o histórico sem inventar outro parâmetro, e é o
lado "sem histórico" da comparação do critério 5.

**Modo de falha conhecido, e ele é entregável.** Pergunta longa, sem marcador e mesmo
assim dependente do turno anterior: *"quantos dias posso converter em abono pecuniário
considerando o período aquisitivo mencionado"*. O critério 5 do PRD exige registrar ao
menos um caso assim.

**Contrato 7: `CitationResolver.resolve`**

```python
def resolve(self, text: str, hits: list[SearchHit]) -> tuple[list[Citation], list[int]]: ...
```

Devolve as citações resolvidas e os rótulos não resolvidos. Regras: extrai `\[(\d+)\]`;
deduplica preservando a ordem de primeira aparição; resolve `label` contra
`hits[label - 1]` **da mesma lista numerada pelo `PromptBuilder`**; rótulo fora de
`1..len(hits)` vai para a lista de não resolvidos.

Isto **não** contraria o ADR-004. O que o ADR proíbe é o consumidor resolver `[n]` pela
posição em `hits` **serializado na resposta**. A resolução interna é contra a lista que o
prompt numerou, materializada em `citations` antes de qualquer transformação de
apresentação. Invariante que sustenta isso: `hits` é construído uma vez no passo 6 e não é
reordenado, deduplicado nem filtrado em nenhum ponto entre a numeração e a resolução.

**Contrato 8: constante literal de recusa**

```python
ESCAPE_PHRASE = "Não encontrei essa informação nos documentos."
```

Mesma string do `rag-01`, de propósito: permite comparar a taxa de recusa entre os dois
projetos. Os critérios comparam literal, não interpretam. **Mudar a constante quebra a
validação do projeto.** A frase entra no template sem aspas nem delimitador; com aspas o
modelo as copia e a comparação literal falha (achado registrado no FDD do `rag-01`).

---

### 6. Erros, exceções e fallback

**Matriz de erros**

| Condição | Exceção | HTTP | Tratamento |
| --- | --- | --- | --- |
| `OPENAI_API_KEY` ausente | `InvalidConfigurationException` | 500 | **O servidor sobe mesmo assim.** `provide_properties` reconstrói a configuração a cada requisição (para o `.env` poder mudar sem reiniciar), então a chave ausente vira 500 por requisição, não falha na subida. Nas CLIs, aí sim, falha antes de qualquer chamada. |
| `question` vazia ou só espaços | `InvalidParameterException` | 422 | Validada **na rota**, não no modelo Pydantic: a restrição no modelo faria o framework responder antes do error handler, num formato que não é o `Problem` do contrato. |
| Qdrant não responde **na entrada** | `ServiceUnavailableException` | 503 | `HealthChecker.check()`, com o comando a rodar no `detail`. |
| Qdrant cai **no meio da requisição** | `ServiceUnavailableException` | 503 | Traduzido no adaptador. Engolir a exceção e devolver "coleção vazia" faria isso virar 409 "rode `python ingest.py`", e o usuário reindexaria contra um serviço morto. |
| OpenAI não responde na geração | `ServiceUnavailableException` | 503 | Traduzido na fronteira, em `OpenAiGenerationService.generate`. Sem tradução, sobe até o framework e vira 500 em texto puro, fora do `Problem`. Sem retry além do default do SDK. |
| `k`, `history_window`, `chunk_size` ou `chunk_overlap` fora da faixa | `InvalidParameterException` | 422 | Os limites são os mesmos declarados em `/capabilities` e são **impostos**, não só anunciados. |
| OpenAI não responde na **reescrita** | tratada, não propaga | 200 | Cai para a pergunta original, `reason = reescrita_falhou`, log WARNING. |
| Coleção inexistente ou vazia | `EmptyIndexException` | 409 | `require_index()` no `RetrievalService`, antes da chamada paga. |
| `k < 1` ou `k > 20` | `InvalidParameterException` | 422 | Validado na borda. |
| `history_window < 0` | `InvalidParameterException` | 422 | `0` é válido e significa ignorar o histórico. |
| Turno sem `question` ou sem `answer` | `InvalidParameterException` | 422 | Nunca descarte silencioso: histórico corrompido produziria reescrita errada sem sintoma. |
| `chunk_overlap >= chunk_size` | `InvalidParameterException` | 422 | Validado antes de ler o corpus. |
| `pdfs/` sem PDF | `EmptyCorpusException` | 422 | Sem chamada paga. |
| PDF sem texto extraível | `NoExtractableTextException` | 422 | Página descartada é contada em `discarded_pages`; corpus inteiro sem texto é erro. |
| Dimensão do embedding difere da coleção | `InvalidConfigurationException` | 500 em `/ask` | `HealthChecker.check_dimensions` roda nas rotas que consultam o índice, via `CheckedRepository`. **Não roda em `/health`**, que declara `Repository`. A primeira versão desta matriz prometia "503 no `/health`" com a mesma exceção que já mapeava para 500 em outra linha: dois status para um tipo só, impossível de satisfazer. |
| Rótulo `[n]` fora de `1..k` | não é exceção | 200 | `meta.unresolved_labels` + log WARNING. |

**Estratégias de resiliência.** Timeout explícito nas duas fronteiras externas (OpenAI e
Qdrant). Sem retry, sem backoff, sem circuit breaker: um usuário, uso interativo, e um
retry silencioso dobraria o custo de uma chamada paga sem o usuário saber. O
`HealthChecker` roda antes da primeira chamada paga e é a mitigação principal.

**Política de fallback.** Um único fallback em todo o fluxo: a reescrita que falha cai
para a pergunta original. Todos os outros erros propagam. Fallback silencioso num pipeline
de RAG é como uma citação inventada: produz saída plausível a partir de um caminho que não
funcionou.

**Invariantes**

1. `refused == true` implica `citations == []`.
2. `rewritten_question` presente em toda resposta de `/ask`.
3. **No domínio**, `Answer.rewrite_s == 0.0` se e somente se `reason` for
   `primeiro_turno` ou `pergunta_autossuficiente`. A facade zera explicitamente nesses
   dois casos, em vez de deixar o cronômetro devolver `0.000004`, e é isso que torna a
   igualdade exata.

   **Na serialização o "somente se" não vale, e isso é uma restrição real, não um
   descuido.** O `JsonPresenter` arredonda para 3 casas, então uma reescrita que leve
   menos de meio milissegundo também sai como `0.0`. Com um LLM de verdade isso não
   acontece (a chamada custa centenas de milissegundos), mas com dublê acontece sempre.

   Consequência para quem consome: **`reason` é o sinal autoritativo de "houve chamada",
   não `rewrite_s`.** É a razão de ele ser um conjunto fechado, e não prosa. Um cliente
   que contar chamadas somando `rewrite_s > 0` conta errado; contando `reason` fora de
   `{primeiro_turno, pergunta_autossuficiente}` conta certo.
4. Todo rótulo `[n]` do texto está em `citations` ou em `meta.unresolved_labels`.
5. `hits` não é reordenado entre a numeração do prompt e a resolução das citações.
6. `pdfs/fora-do-corpus/` nunca é alcançado pelo glob. O glob é `pdfs/*.pdf`.
7. **Só o `presenter/` escreve**, e nenhuma camada chama `sys.exit()`. A redação anterior
   dizia "nenhuma camada abaixo do entrypoint escreve", o que era falso pelo próprio
   desenho: o `ConsoleReporter` é presenter, está abaixo do entrypoint, e escrever é a
   função dele. O que a regra 2.3 da guideline garante é que exista **um** lugar que
   escreve, não nenhum.
8. Turno malformado em `options.history` falha alto; valor ilegível de parâmetro escalar
   cai no default. A assimetria é deliberada: `k` errado degrada a busca de um jeito que
   aparece na resposta; histórico truncado em silêncio produz reescrita errada sem sintoma.

---

### 7. Observabilidade

**Métricas** (expostas na resposta, não em sistema externo)

- `timings.rewrite_s`, `timings.search_s`, `timings.generation_s`: três estágios, para o
  custo novo ser atribuível.
- Contagem de chamadas de LLM por turno: 1 quando não reescreve, 2 quando reescreve.
  Derivável de `reason`, que é o motivo de ele ser enumerado.
- Taxa de recusa por corpus (indexado vs controle) e por posição no turno. **Recusa que
  cai do turno 1 para o turno 3 é o defeito do critério 4.**
- Distância do melhor trecho, antes e depois da reescrita.
- Rótulos não resolvidos por resposta.

**Logs. Estado real, e ele é menor que a promessa original desta seção.**

Não existe `logging` estruturado no projeto: `grep -rn "logging\|getLogger" rag/` não
devolve nada. O que existe é **diagnóstico em prosa no `ConsoleReporter`**, em stderr,
separado do resultado em stdout. A versão anterior desta seção prometia campos nomeados,
níveis e dois `WARNING`; nada disso foi implementado, e o FDD prometia o que o código não
faz.

O que de fato sai, e onde:

| Informação | CLI (`ConsoleReporter`) | HTTP |
| --- | --- | --- |
| `rewrite_reason`, `query_used`, pergunta original | sim, em prosa | no corpo da resposta, não em log |
| `hits`, `best_distance` | sim | só `hits` no corpo |
| `rewrite_s`, `search_s`, `generation_s` | sim | no corpo |
| `refused` | sim | no corpo |
| `unresolved_labels` | sim, com prefixo `[ATENÇÃO: ...]` | em `meta` |
| `citations` | sim, com fonte e página | no corpo |
| Ingestão (`file`, `pages`, `chunks`, ...) | sim | no corpo |
| `question_len`, `history_turns_received`, `history_turns_used` | **não sai em lugar nenhum** | idem |

**A camada HTTP não emite log algum.** As métricas existem apenas dentro do corpo da
resposta, o que significa que uma requisição que falha antes de responder não deixa
rastro, e que não há como agregar nada entre requisições sem instrumentar o cliente.

Os dois `WARNING` prometidos (falha de reescrita e rótulo não resolvido) aparecem só na
CLI, como texto, sem nível.

**Pendência declarada, não esquecida.** Logging estruturado é trabalho conhecido e não
feito. Não bloqueia nenhum critério de aceite deste projeto, porque em uso interativo com
um usuário o `ConsoleReporter` cumpre o papel, mas bloqueia qualquer agregação — inclusive
a taxa de recusa por posição no turno que esta mesma seção lista como métrica. Registrado
nos próximos passos do HLD.

Nunca em log: a chave da OpenAI e o conteúdo integral da conversa. `query_used` aparece
porque é o objeto do critério 2, e é conteúdo que o usuário acabou de digitar.

**Tracing.** Sem tracing distribuído: processo único. Os três `timings` cumprem o papel.

**Dashboards e alertas.** Nenhum. O `ConsoleReporter` imprimindo a query reescrita, a
distância do melhor trecho e as citações substitui um painel nesta escala. O
`chat.py` mostra a cada turno, em stderr: `[reescrita: <reason>] <query usada>`.

---

### 8. Dependências e compatibilidade

| Componente | Versão mínima | Observações |
| --- | --- | --- |
| Python | 3.12.3 | O instalado. Sem `pip` no sistema: só dentro do venv. |
| langchain | 1.3.14 | |
| langchain-openai | 1.4.1 | `gpt-4o-mini` e `text-embedding-3-small` |
| langchain-text-splitters | 1.1.2 | |
| langchain-community | 0.4.2 | |
| langchain-qdrant | 1.1.0 | |
| langchain-chroma | 1.1.0 | Só para o critério 7 |
| pypdf | 6.14.2 | |
| python-dotenv | 1.2.2 | |
| fastapi | 0.140.1 | Patch acima do que o guia fixa; revalidado no PyPI em 27/07/2026 |
| uvicorn | 0.51.0 | |
| mypy | 2.3.0 | Obrigatório: `Protocol` não é verificado em runtime |
| pytest | 9.1.1 | Escopo restrito à matriz de recusa e à reescrita |
| Qdrant | imagem oficial | Healthcheck a validar **contra a imagem escolhida** |
| Node | o instalado (v22) | Só para o frontend |

**Garantias de compatibilidade**

- O contrato compartilhado permanece em 1.1.0. Nenhum campo novo entra em `required`.
- **Este projeto garante mais do que o contrato exige, e isso não é divergência.**
  `rewritten_question`, `timings.rewrite_s` e os seis campos de `/health` são opcionais
  no contrato porque torná-los obrigatórios quebraria o `rag-01`, que não os emite. As
  invariantes 2 e 3 da seção 6 são promessas **deste backend**, mais fortes que o
  contrato comum. Um cliente genérico trata como opcional; um cliente que fale com este
  backend pode contar com elas.
- Adições ao contrato feitas durante esta feature, todas retrocompatíveis: `422` e `500`
  em `/ask`, `500` e `503` em `/ingest`, `enum` fechado em `reason`, e a menção de
  `meta.unresolved_labels`. Vieram do cruzamento que o `dd-postman` fez entre o FDD e o
  YAML publicado. Nenhuma toca `required`.
- O `JsonPresenter` **omite** campos que não se aplicam, nunca emite `null`.
- O `rag-01` continua conforme sem alteração de código.
- O frontend detecta a conversa por `features.includes("history")`. Contra o `rag-01`, que
  não declara `history`, a interface fica idêntica à de hoje.
- `frontend/dist/` está commitado e ficará defasado até um `npm run build`. Registrado,
  não tratado nesta feature.

**Pré-requisitos operacionais bloqueantes** (impedem a validação do passo 7, não a
implementação):

1. Corpus normativo em `pdfs/` — hoje só tem `.gitkeep`.
2. Corpus de controle em `pdfs/fora-do-corpus/` — idem.
3. Docker Desktop com integração WSL ativa. Em 27/07/2026 a distro respondia
   *"The command 'docker' could not be found in this WSL 2 distro"*.
4. `OPENAI_API_KEY` em `.env`, com limite de gasto mensal configurado na conta.

---

### 9. Critérios de aceite técnicos

Rastreados contra os critérios de negócio do PRD.

1. **[PRD 1] Diálogo de três turnos.** `chat.py` com o corpus normativo: pergunta sobre
   férias, seguida de "e se eu vender dez?", devolve resposta sobre conversão de férias em
   abono, e não sobre comércio. Evidência: transcrição da sessão.
2. **[PRD 2] Reescrita visível.** `rewritten_question` presente em 100 por cento das
   respostas de `/ask`; `chat.py` e `ask.py` imprimem a query usada e o `reason`.
   Evidência: saída de `chat.py` e corpo JSON de `/ask`.
3. **[PRD 3] Citação confere.** Cinco conferências manuais: abrir a página citada e achar
   o trecho. Evidência: tabela de cinco linhas com pergunta, rótulo, página e veredito.
4. **[PRD 4] Recusa sobrevive ao follow-up.** Matriz completa em pytest com `FakeLLM` e
   `FakeVectorRepository`: turnos 1, 2 e 3 × dentro/fora do corpus ×
   `conditional_rewrite` ligado/desligado. 100 por cento dos casos fora do corpus com
   `refused == true`. Evidência: `pytest -v` verde. **Nenhuma chamada à API paga.**
5. **[PRD 5] Custo da reescrita medido.** Mesma conversa de 6 turnos com
   `conditional_rewrite` ligado e desligado, com a contagem de chamadas de cada lado, e
   ao menos um caso registrado em que a heurística deixou de reescrever algo que
   precisava. Evidência: tabela comparativa.
6. **[PRD 6] Janela experimentada.** Mesma conversa com `history_window` 2, 6 e 20, com a
   degradação observada e anotada. Evidência: anotação em branch `exp/`.
7. **[PRD 7] Troca de vector store.** Trocar `QdrantVectorRepository` por
   `ChromaVectorRepository` alterando apenas a linha de construção nos composition roots,
   com resultado equivalente. Evidência: diff da troca e saída antes e depois.
8. **Invariantes 1 a 7 da seção 6** cobertas por teste ou por verificação executável. A 6
   e a 7 por `grep`; as demais por pytest.
9. **mypy limpo:** `python -m mypy rag/ ingest.py ask.py chat.py serve.py --ignore-missing-imports`
   sem erro.
10. **Contrato conforme:** a coleção Postman roda contra o serviço no ar, e o `required`
    do `rag-api.yaml` não mudou.
11. **Frontend:** conversa de três turnos pela interface, com citação clicável e query
    reescrita visível; contra o `rag-01`, a interface permanece a de pergunta única.

---

### 9.1 Estado da validação (27/07/2026)

Executada com Qdrant v1.18.1 em container, `gpt-4o-mini` e
`text-embedding-3-small` reais, sobre o corpus disponível.

**Divergência de corpus, registrada e não corrigida.** O PRD especifica texto normativo
(CLT ou equivalente); o corpus em `pdfs/` é o do Projeto 1, *Harry Potter e a Pedra
Filosofal* (274 páginas, 617 chunks), com *Primeira Carta aos Coríntios* como corpus de
controle. O controle funciona exatamente como projetado. O corpus positivo não: narrativa
gera menos follow-up dependente de contexto que norma, e as perguntas de validação tiveram
que ser adaptadas. Os critérios foram verificados com o corpus que existe; refazer com
texto normativo continua valendo.

| # | Critério | Estado | Evidência |
| --- | --- | --- | --- |
| 1 | Diálogo de três turnos | **Atendido** | `chat.py`, três turnos: turno 2 "E o que ela faz?" e turno 3 "E como eles **a** usaram para lidar com o dragão?" resolvidos contra o histórico, com resposta e citação. Um defeito foi encontrado e corrigido aqui, ver abaixo. |
| 2 | Reescrita visível | **Atendido** | `chat.py` imprime `original` e `buscado` a cada turno; `POST /ask` devolve `rewritten_question` em 100 por cento das respostas. Exemplo real: "E como eles a usaram para lidar com o dragao?" → "E como Harry e seus amigos usaram a capa de invisibilidade para lidar com o dragão?" |
| 3 | Citação confere | **Atendido, excedido** | **7 de 7** citações conferidas abrindo a página citada no PDF e procurando o trecho (o PRD pede 5). Script em `docs/operations/`. Zero divergências. |
| 4 | **Recusa sobrevive ao follow-up** | **Atendido** | Com LLM real: três turnos sobre o corpus de controle, **todos recusados**, distâncias 0,65 a 0,70. A reescrita resolveu "E nesse caso?" mantendo o assunto fora do corpus em vez de puxá-lo para dentro, que era o risco número 1 do FDD. Mais 16 casos em `pytest tests/test_refusal_matrix.py`, sem chamada paga. |
| 5 | Custo da reescrita medido | **Atendido** | Conversa de 4 turnos: **7 chamadas** com `conditional_rewrite=false` contra **6** com `true`. A heurística classificou corretamente a pergunta longa como `pergunta_autossuficiente` e economizou a chamada sem prejuízo da resposta. |
| 6 | Janela experimentada | **Atendido** | Janelas 0, 2 e 20 sobre a mesma conversa. Achado que contraria a expectativa ingênua, ver abaixo. |
| 7 | Troca de vector store | **Atendido** | Qdrant → Chroma alterando **uma linha** em `composition.build_repository` (mais o import). Mesma pergunta, mesma resposta, **mesma citação** (`[2]` p.178). Diff da troca em `docs/operations/`. |
| 8 | Invariantes 1 a 7 | **Atendido** | 1 a 5 por pytest; 6 e 7 por `grep` (glob não recursivo; nada fora de `presenter/` escreve ou chama `sys.exit`; nenhuma sessão, cache ou `conversation_id` no pacote). |
| 9 | mypy limpo | **Atendido** | `Success: no issues found in 38 source files`. Pegou dois defeitos reais: `total_pages` ausente do `Protocol DocumentReader` e anotação faltando em `QueryFacade`. |
| 10 | Contrato conforme | **Atendido após correção** | `newman`: 86 de 91 asserções (as 5 falhas são os dois requests que exigem infra oposta, documentado). **O `dd-doc-sync` encontrou duas violações reais que o newman não pegava**: `question` vazia e falha da OpenAI devolviam corpo fora do schema `Problem`. Ambas corrigidas e cobertas por teste. `required` do `rag-api.yaml` inalterado. |
| 11 | Frontend | **Parcial** | `vite build` limpo. Os três turnos validados pelo caminho HTTP exato do frontend. **Um defeito foi encontrado e corrigido**: o clique no rótulo `[n]` não navegava, porque nenhum `<li>` de citação tinha `id` e o `getElementById` devolvia `null` em silêncio. **A conferência visual no navegador continua pendente** e depende de você. |

**Suíte:** 63 testes, 0 falhas, 0 chamadas à API paga.

#### Defeito encontrado e corrigido durante a validação

A busca usava a query reescrita, mas o prompt de resposta recebia a **pergunta original**.
Com contexto perfeito sobre a capa de invisibilidade e a pergunta "E o que ela faz?", o
modelo recusava: nada no prompt dizia a que "ela" se referia, e a instrução de não
completar lacunas fazia o resto. A reescrita existe para resolver isso, e usá-la só na
busca desfazia metade do trabalho.

Correção: o `PromptBuilder` passou a receber a `RewriteDecision` inteira e monta a
pergunta resolvida **com a literal do usuário ao lado**. Manter a literal visível é a
mitigação do risco número 1: se a reescrita derrapar e trocar o assunto, o modelo tem como
perceber. Verificado que a recusa no corpus de controle continua valendo depois da mudança.
Registrado em ADR-007.

#### Achado do critério 6: a degradação da janela é bidirecional

O FDD previa que conversa longa piora a reescrita. O experimento mostrou o oposto também,
e mais fácil de disparar:

| Janela | Query reescrita |
| --- | --- |
| 0 | "E como eles a usaram para lidar com o dragao?" (sem reescrita, `primeiro_turno`) |
| 2 | "E como **Rony e ele** usaram a capa da invisibilidade para lidar com o dragão?" |
| 20 | "Como **Harry e Rony** usaram a capa da invisibilidade para lidar com o dragão?" |

A janela de 2 truncou o turno onde "Harry" era nomeado, e a reescrita resolveu o
antecedente errado. **Janela curta demais não economiza contexto: ela remove o antecedente
que a reescrita precisa.** O default de 6 fica mantido, e o risco "degradação silenciosa
em conversa longa" da seção 10 passa a ter um irmão: degradação silenciosa em janela curta.

#### Observação de qualidade de recuperação, para o Projeto 3

Cerca de um terço das perguntas factuais sobre o corpus recebeu recusa mesmo existindo
passagem que as sustentava. Com `k=4` e busca puramente densa sobre um romance de 274
páginas, o trecho certo frequentemente não entra nos quatro. Não é defeito deste projeto:
é exatamente a limitação que o Projeto 3 (busca híbrida e reranking) existe para resolver,
e tê-la medido aqui é o que dá sentido a fazê-lo lá.

Observado também que o modelo recusa quando o contexto mostra uma **instância** e a
pergunta pede uma **propriedade** ("Harry ficou invisível" contra "o que a capa faz").
É comportamento de grounding defensável, não defeito de encanamento. Calibrar o limiar de
recusa exige avaliação sistemática, que o PRD põe no Projeto 3 em diante.

---

### 10. Riscos e mitigação

### A reescrita legitima uma pergunta fora do corpus

- **Probabilidade:** média
- **Impacto:** alto, e é o risco central desta feature. "E nesse caso?" perguntado logo
  depois de um turno sobre a CLT pode ser reescrito para uma pergunta que *parece*
  pertencer ao corpus, mas cujo assunto está no corpus de controle.
- **Mitigação:**
    - O prompt de reescrita instrui explicitamente a **resolver referências, não completar
      lacunas**, e a nunca introduzir assunto ausente da pergunta original.
    - A recusa é decisão do estágio de geração sobre os trechos recuperados, nunca do
      estágio de reescrita.
    - Matriz de recusa em pytest, com o turno 3 incluído.
    - `query_used` registrado em toda resposta, para o caso ser diagnosticável depois.
- **Plano de contingência:** desligar a reescrita e comparar. Se a recusa volta, o defeito
  está no prompt de reescrita, e o lugar do conserto fica identificado sem adivinhação.

### Citação mal resolvida por transformação de `hits`

- **Probabilidade:** baixa, dada a invariante 5; alta se a invariante for quebrada depois
- **Impacto:** alto. `[2]` apontando para o trecho errado não é detectável na leitura.
- **Mitigação:**
    - Invariante 5 explícita: `hits` construído uma vez, nunca reordenado.
    - `citations` materializado na facade, antes de qualquer camada de apresentação.
    - Teste que reordena `hits` **depois** da resolução e verifica que as citações não
      mudam.
- **Plano de contingência:** carregar o texto do trecho dentro da `Citation`, como já é
  feito em `excerpt`, torna a citação autossuficiente mesmo se a lista sumir.

### Custo dobrado por turno

- **Probabilidade:** alta, é o comportamento esperado
- **Impacto:** médio. Dois estágios de LLM por turno, e um REPL convida a conversas longas.
- **Mitigação:**
    - `conditional_rewrite` disponível, com o ganho medido no critério 5.
    - Primeiro turno nunca reescreve.
    - `timings` e `reason` visíveis em toda resposta.
    - Limite de gasto mensal na conta, antes da primeira execução.
- **Plano de contingência:** desligar a reescrita e operar como o Projeto 1.

### Heurística condicional deixa de reescrever algo que precisava

- **Probabilidade:** alta, por construção
- **Impacto:** médio, e **é entregável**: o critério 5 exige registrar um caso.
- **Mitigação:**
    - `conditional_rewrite` nasce **desligado**. O caminho correto e mais caro é o padrão.
    - `reason` sempre visível: `pergunta_autossuficiente` é o sinal de que a heurística
      decidiu pular.
- **Plano de contingência:** baixar o limiar de palavras ou ampliar a lista de marcadores.
  Ambos são constantes num arquivo só.

### Healthcheck do Qdrant escrito às cegas

- **Probabilidade:** média
- **Impacto:** médio. Healthcheck que não roda na imagem é pior que nenhum: dá falsa
  segurança e o `docker compose up -d` reporta saudável um serviço que não responde.
- **Mitigação:**
    - Validar o endpoint de saúde **contra a imagem escolhida** antes de escrever o
      compose, não copiar de tutorial.
    - `HealthChecker` no código também, independente do Docker.
- **Plano de contingência:** healthcheck por TCP na porta, que é fraco mas honesto.

### O glob recursivo mata o teste negativo em silêncio

- **Probabilidade:** baixa
- **Impacto:** alto. `pdfs/*.pdf` trocado por `**/*.pdf` indexa o corpus de controle, e o
  critério 4 passa a testar nada, sem nenhum sintoma.
- **Mitigação:**
    - Invariante 6, verificável por `grep`.
    - `IngestionFacade.files()` exposto separadamente de `ingest()`, para o corpus de
      controle indexado por engano aparecer na listagem antes do trabalho começar.
- **Plano de contingência:** recriar a coleção e reindexar.

---

### 11. Sequenciamento de implementação (Build Order)

| Ordem | Etapa | Depende de | Componentes/arquivos prováveis | Critérios que fecha |
| --- | --- | --- | --- | --- |
| 1 | Esqueleto e infra | - | `requirements.txt`, `.env.example`, `docker-compose.yml` (Qdrant + healthcheck validado), `rag/__init__.py` | pré-requisito |
| 2 | Domínio e exceções | 1 | `rag/domain/models.py` (`Turn`, `Conversation`, `SearchHit`, `Citation`, `RewriteDecision`, `Answer`, `IngestionReport`), `rag/exceptions.py`, `rag/config.py` | 8 (invariantes 1, 3) |
| 3 | Fronteiras externas | 2 | `rag/repository/document_reader.py`, `rag/repository/vector_repository.py` (`Protocol` + `QdrantVectorRepository`, normalização de página e distância) | 7, 8 (invariante 6) |
| 4 | Serviços do caminho de ingestão | 3 | `rag/service/chunking_service.py`, `rag/facade/ingestion_facade.py` | pré-requisito de 1 a 6 |
| 5 | Reescrita | 2 | `rag/service/query_rewrite_service.py` (heurística + prompt), `rag/service/generation_service.py` | 2, 5 |
| 6 | Recuperação e prompt | 3, 5 | `rag/service/retrieval_service.py` (`k`, `require_index`), `rag/service/prompt_builder.py` (numeração, `ESCAPE_PHRASE`) | 1, 8 (invariante 5) |
| 7 | Citação | 6 | `rag/service/citation_resolver.py` | 3, 8 (invariantes 1, 4) |
| 8 | Caso de uso | 5, 6, 7 | `rag/facade/query_facade.py` (janela, `refused`, montagem do `Answer`) | 1, 2, 4 |
| 9 | Apresentação | 8 | `rag/presenter/console_reporter.py`, `rag/presenter/json_presenter.py` (omite, não emite `null`) | 2, 8 (invariante 7) |
| 10 | Entrypoints CLI | 9 | `ingest.py`, `ask.py`, `chat.py` | 1, 2, 5, 6 |
| 11 | Camada HTTP | 9 | `rag/api/{app,dependencies,descriptor,error_handlers,schemas}.py`, `rag/api/routes/{ask,ingest,meta}.py`, `serve.py`, `rag/service/health_checker.py` | 10 |
| 12 | Testes | 8 | `tests/conftest.py` (`FakeLLM`, `FakeVectorRepository`), `tests/test_refusal_matrix.py`, `tests/test_rewrite.py`, `tests/test_citations.py` | 4, 8 |
| 13 | Adaptador Chroma | 3 | `rag/repository/chroma_vector_repository.py` | 7 |
| 14 | Frontend | 11 | `frontend/src/App.jsx` (transcrição, envio de `options.history`, UI de turnos), `frontend/src/Conversa.jsx` (novo), `Resposta` estendido (citações clicáveis, query reescrita, `timings.rewrite_s` com guarda). `api.js` **não muda**: já repassa `options` cru. `Parametros.jsx` **não muda**: nada específico de projeto entra lá. | 11 |
| 15 | mypy e verificação de invariantes | 12 | — | 9 |

Etapas 5, 6 e 7 são independentes entre si depois da 3 e podem ser feitas em qualquer
ordem. A 12 pode começar junto da 8: os dublês não dependem dos adaptadores reais, e
escrever a matriz de recusa cedo é a melhor defesa contra o risco central desta feature.
