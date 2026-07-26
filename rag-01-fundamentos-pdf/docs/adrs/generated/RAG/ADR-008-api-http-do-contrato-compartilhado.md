# ADR-008: API HTTP implementando o contrato compartilhado

- **Status:** aceito
- **Data:** 2026-07-25
- **Domínio:** RAG
- **Decisores:** arthu

## Contexto

O PRD do Projeto 1 lista "API HTTP própria" em **fora de escopo**. Essa exclusão fazia
sentido enquanto o único cliente era a linha de comando.

Duas coisas mudaram. Primeiro, o autor decidiu construir um frontend único, capaz de
conversar com os dez projetos da trilha. Um frontend precisa de alguém do outro lado
atendendo requisição, e os Projetos 1 a 7 são CLIs.

Segundo, o ADR-007 já tinha extraído o caso de uso dos entrypoints exatamente prevendo
isto: `QueryFacade.ask(question) -> Answer` não conhece `argparse` nem `sys.stderr`.
Expor por HTTP virou escrever um adaptador, não reescrever lógica.

## Decisão

Acrescentar `serve.py` como terceiro entrypoint, ao lado de `ingest.py` e `ask.py`,
implementando `docs/contracts/rag-api.yaml` sobre as mesmas facades.

**Emenda ao PRD:** "API HTTP própria" sai de fora-de-escopo e entra no escopo, com a
ressalva de que ela não acrescenta comportamento de RAG. É superfície, não função.

Stack: FastAPI 0.140.0 e uvicorn 0.51.0. A guideline manda preferir a biblioteca padrão,
e aqui ela é deixada de lado conscientemente: `http.server` exigiria implementar
roteamento, validação e o preflight de CORS à mão, que é justamente o que o framework
resolve. Um servidor HTTP é onde um framework se paga.

Quatro endpoints:

| Rota | Papel |
| --- | --- |
| `GET /health` | Serviço de pé e índice com conteúdo |
| `GET /capabilities` | **O mecanismo de desacoplamento.** Ver abaixo |
| `POST /ask` | Pergunta ao corpus |
| `POST /ingest` | Reindexa, destrutivo |

### O desacoplamento vive no `/capabilities`

O backend descreve, em JSON Schema reduzido, os parâmetros que aceita:

```json
{ "k": {"type":"integer","default":4,"minimum":1,"maximum":20,
        "label":"Chunks recuperados","applies_to":["ask"]} }
```

O frontend renderiza os controles a partir daí e **nunca conhece parâmetro de projeto
nenhum**. O Projeto 3 acrescenta `rerank_top_n`, o Projeto 7 acrescenta `max_hops`, e o
frontend continua o mesmo arquivo.

Duas regras sustentam isso:

- **`options` aceita chaves desconhecidas e as ignora**, em vez de falhar. É o que permite
  ao mesmo frontend falar com projetos de gerações diferentes.
- **A resposta traz `refused: boolean`.** O backend compara com a própria frase de escape
  e informa. Sem esse campo, o cliente teria que comparar strings e ficaria acoplado ao
  texto exato de cada projeto.

### A apresentação em JSON é uma camada, não código solto

`rag/presenter/json_presenter.py` é irmão do `ConsoleReporter`: mesma camada, mesmo
papel, saída diferente. A existência dos dois é a evidência de que o ADR-007 valeu, e
mantém a invariante de que só o presenter formata saída.

Exceções de domínio viram status HTTP num único `exception_handler`, equivalente ao
`@ControllerAdvice` do Spring:

| Exceção | Status | `code` |
| --- | --- | --- |
| `ServiceUnavailableException` | 503 | `SERVICE_UNAVAILABLE` |
| `EmptyIndexException` | 409 | `EMPTY_INDEX` |
| `InvalidConfigurationException` | 422 | `INVALID_CONFIGURATION` |

CORS restrito a `localhost` e `127.0.0.1` em qualquer porta, por regex. O Vite usa 5173, e
fixar a porta quebraria no primeiro conflito. Isto é ferramenta de estudo local, não
serviço exposto.

## Alternativas consideradas

### Não expor HTTP no Projeto 1, começar no Projeto 8

Rejeitada pelo autor. O Projeto 8 (Spring AI) precisa de API por natureza, e o PRD do
Projeto 1 permaneceria intacto. Rejeitada porque o frontend ficaria sem backend para
testar por semanas, e porque o custo aqui é baixo justamente por causa do ADR-007.

### `http.server` da biblioteca padrão

Rejeitada. Zero dependência, mas exigiria roteamento, validação de corpo e o preflight
`OPTIONS` do CORS escritos à mão. Seriam dezenas de linhas de infraestrutura que não
ensinam nada sobre RAG.

### Streamlit ou Gradio no lugar de API mais frontend

Rejeitada. É o caminho mais curto para uma interface de RAG, e foi descartado porque
acoplaria a interface ao Python. Os Projetos 8, 9 e 10 são Java, e o requisito declarado
era um frontend que servisse a todos.

## Consequências

**Positivas**
- O mesmo caso de uso serve CLI e HTTP sem alteração. É a validação prática do ADR-007.
- O contrato passa a ser a fronteira entre os dez projetos e um frontend só.
- `/capabilities` permite estender por projeto sem tocar no cliente.
- O `serve.py` do Projeto 1 vira a referência de implementação para os projetos seguintes.

**Negativas**
- Duas dependências novas (FastAPI, uvicorn) num projeto que tinha sete.
- Mais uma superfície para manter em cada projeto da trilha.
- O PRD precisou ser emendado no mesmo dia em que foi escrito, o que é sinal de que
  "fora de escopo" foi decidido cedo demais para um item que o autor viria a querer.
- Sem autenticação e sem limite de taxa. Aceitável porque escuta em `127.0.0.1` e é
  ferramenta local, mas seria inaceitável em qualquer outro contexto.

## Referências

- `docs/contracts/rag-api.yaml` (no workspace)
- `docs/guidelines/arquitetura-em-camadas.md`, seção 8
- [[ADR-007-camada-de-caso-de-uso]]
