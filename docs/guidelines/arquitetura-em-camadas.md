# Guideline de arquitetura em camadas

**Fonte de verdade estrutural dos 10 projetos da trilha.** Agnóstica de linguagem: a
seção 6 mapeia para Python, a 7 para Spring.

Origem: extraída do `rag-01-fundamentos-pdf` depois de três decisões encadeadas
(ADR-005 segregação, ADR-006 nomenclatura em camadas, ADR-007 camada de caso de uso).
Cada projeto novo herda a estrutura e registra em ADR próprio o que precisou mudar.

Vive no workspace, não dentro de um projeto, porque cópia diverge na primeira alteração.

---

## 1. A estrutura canônica

```
<projeto>/
├── ingest.py                    entrypoint: indexação
├── ask.py                       entrypoint: consulta
├── serve.py                     entrypoint: HTTP, magro (publica o app)
├── <pacote>/
│   ├── exceptions.py            hierarquia de exceções do domínio
│   ├── config.py                propriedades externas, validadas na construção
│   ├── domain/
│   │   └── models.py            objetos de valor: entrada e saída dos casos de uso
│   ├── facade/                  casos de uso, um método público por operação
│   ├── service/                 uma responsabilidade cada
│   ├── repository/              tudo que fala com o mundo externo
│   ├── presenter/               único lugar que escreve para o usuário
│   └── api/                     camada HTTP, só se o projeto expuser contrato
│       ├── app.py               fábrica: middleware, error handlers, rotas
│       ├── dependencies.py      provedores injetáveis
│       ├── descriptor.py        conteúdo de GET /capabilities
│       ├── error_handlers.py    exceção de domínio -> status HTTP
│       ├── schemas.py           DTOs de entrada
│       └── routes/              um arquivo por recurso
├── docs/                        PRD, HLD, FDDs, ADRs, diagramas
├── pdfs/  ou  corpus/           entrada
├── docker-compose.yml           serviços de que o projeto depende
├── requirements.txt  ou  pom.xml
├── .env / .env.example
└── CLAUDE.md / AGENTS.md
```

---

## 2. As cinco regras

Elas são o que a estrutura significa. Sem elas, é só um conjunto de pastas.

### 2.1 A dependência é estritamente descendente

```
entrypoint → facade → service → repository → domain
                                              ↑
                                          exceptions
```

Nenhuma camada importa outra acima dela. `domain` e `exceptions` são folhas: não importam
nada do projeto.

Verificável por AST, e vale automatizar:

```bash
# nenhum repository pode importar service ou facade
grep -rE 'from \.\.(service|facade)' <pacote>/repository/ && echo "VIOLACAO"
```

### 2.2 A facade não conhece o mundo de fora

Nada de `print`, `argparse`, `sys.stdout`, `sys.stderr`, `HttpServletRequest` ou
`@RequestBody` dentro de `facade/`. Ela recebe tipos de domínio e devolve tipos de
domínio.

É essa ausência que permite ao mesmo caso de uso servir uma CLI, uma API HTTP e um
servidor MCP sem alteração. Se um `print` aparecer ali, a camada virou delegação
decorativa.

### 2.3 Só o presenter escreve

Uma política, um lugar: **stdout carrega o resultado, stderr carrega o diagnóstico.**
É o que permite `python ask.py "..." > saida.txt` gravar só a resposta.

### 2.4 As camadas levantam, o entrypoint encerra

Nenhuma camada chama `sys.exit()`. Elas levantam exceção da hierarquia do projeto; o
entrypoint traduz para código de saída. Uma camada que mata o processo não é reutilizável
nem testável.

### 2.5 Dois modelos de injeção, e a regra entre eles

Nas CLIs, o composition root monta tudo à mão (ADR-007). Na camada HTTP, o
container do framework resolve por anotação (ADR-009). Convivem, e a regra é:

**Container para o que é estável; construção explícita para o que depende da
requisição.** Um parâmetro que chega no corpo (`k`, `chunk_size`) não pode ser
injetado, então a facade que o usa é montada dentro da rota.

Ganho do container que a montagem manual não tem: dependências compostas que não
se esquece. Se `HealthyProperties` já rodou o verificador de saúde, toda rota que
a declarar herda a verificação.

### 2.6 O entrypoint faz duas coisas, e só duas

```python
def main() -> int:
    args = parse_args()                    # controller: adapta o mundo externo
    facade = build_facade(args, config)    # composition root: escolhe o concreto
    reporter.present(facade.run(...))      # delega e apresenta
```

Em Python não há container de injeção de dependência, então alguém precisa escrever as
implementações concretas com a mão. O entrypoint é o lugar honesto: todas as escolhas
juntas, à vista, num arquivo.

---

## 3. Inversão de dependência

Toda fronteira com o mundo externo ganha um `Protocol` (Python) ou `interface` (Java), e
a implementação concreta é injetada pelo composition root.

| Fronteira | Contrato | Implementação |
| --- | --- | --- |
| Leitura de documentos | `DocumentReader` | `PdfDocumentReader`, `HtmlDocumentReader`… |
| Armazém vetorial | `VectorRepository` | `ChromaVectorRepository`, `QdrantVectorRepository`… |
| Divisão em chunks | `ChunkingService` | `RecursiveChunkingService`, `TokenChunkingService`… |
| Modelo de linguagem | `GenerationService` | `OpenAiGenerationService`, `OllamaGenerationService`… |

**O custo pedagógico, registrado para não ser esquecido:** o contrato esconde as
diferenças entre as implementações, e conhecer essas diferenças é objetivo declarado da
trilha ("vector store diferente em quase todo projeto"). Ao comparar dois armazéns, leia
os adaptadores, não o fluxo.

---

## 4. Nomes que não devem ser usados

| Nome | Por que não |
| --- | --- |
| `Entity` | Implica identidade e persistência. Os objetos aqui são de valor, definidos pelo conteúdo. Use `domain/models`. |
| `Controller` | Implica requisição HTTP entrante. Nos projetos CLI, o entrypoint não é controller de HTTP. Nos projetos com API (8 a 10), aí sim. |
| `Facade` para uma única operação trivial | Facade só se paga quando existe mais de um cliente, ou quando o caso de uso precisa ser chamável sem terminal. Delegação pura é camada vazia. |
| `Helper`, `Util`, `Common`, `Misc` | Depósito. Atrai tudo que não coube em outro lugar, e é onde a estrutura apodrece primeiro. Se algo não tem lugar, o lugar está faltando. |
| `Manager`, `Handler`, `Processor` | Não dizem nada. Qualquer classe gerencia, trata ou processa algo. |

Convenção de idioma: **código em inglês, mensagens ao usuário e documentação em
português.** Misturar os dois no mesmo identificador (`store.py` contendo
`ArmazemVetorial`) é inconsistência, não escolha.

---

## 5. Como cada projeto estende sem acoplar

A regra é: **acrescente implementações, não altere contratos.**

| Projeto | O que acrescenta | Onde |
| --- | --- | --- |
| 2 conversacional | `ConversationMemory`, reescrita de pergunta | `service/`, novo `QueryRewriteService` |
| 3 híbrido | `KeywordRepository` (BM25), `RerankService` | `repository/`, `service/` |
| 4 multimodal | `TableSummaryService`, `DocumentStore` para originais | `service/`, `repository/` |
| 5 agêntico | O grafo LangGraph **substitui a facade** — ver 5.1 | `facade/` vira `graph/` |
| 6 roteador | `SqlRepository`, `RouterService` | `repository/`, `service/` |
| 7 GraphRAG | `GraphRepository` (Neo4j), `CypherService` | `repository/`, `service/` |
| 8 a 10 Spring | Mesma estrutura, anotações do framework — ver seção 7 | — |

### 5.1 Onde a estrutura não serve: o Projeto 5

Preciso registrar isto, e não é detalhe. No Projeto 5 (LangGraph, RAG corretivo), **o
grafo de estado É a orquestração**. Ter uma `QueryFacade` chamando um `StateGraph` que
por sua vez chama serviços cria duas camadas de orquestração empilhadas, uma delas vazia.

Recomendação para o Projeto 5: trocar `facade/` por `graph/`, com os nós do grafo
chamando `service/` diretamente. As demais camadas permanecem. Registre em ADR do
projeto: a estrutura foi adaptada, não abandonada.

O mesmo vale, em menor grau, para o Projeto 6: o roteador é um nó de grafo, não uma
facade.

---

## 6. Instanciação em Python

```
rag/
├── exceptions.py       class RagException(Exception) + subclasses
├── config.py           @dataclass(frozen=True) class RagProperties
├── domain/models.py    NamedTuple: SearchHit, Answer, IngestionReport
├── facade/             class QueryFacade, class IngestionFacade
├── service/            typing.Protocol + implementação concreta
├── repository/         typing.Protocol + adaptador
└── presenter/          class ConsoleReporter
```

**`Protocol` em vez de `ABC`**: conformidade estrutural, sem declarar herança. O adaptador
não precisa importar o contrato, o que permite adaptar até classe de biblioteca de
terceiro. O preço é que nada verifica em tempo de execução.

**Por isso o mypy é obrigatório, não opcional.** Sem ele os `Protocol` são comentário:

```bash
python -m mypy <pacote>/ ingest.py ask.py --ignore-missing-imports
```

Fixe `mypy` no `requirements.txt` e rode antes de cada commit.

**`NamedTuple` para objetos de valor**: continua desempacotável como tupla e ganha acesso
por atributo. `frozen dataclass` quando houver métodos ou muitos campos.

---

## 7. Instanciação em Spring (Projetos 8, 9 e 10)

A estrutura é a mesma; o framework fornece o que em Python é manual.

| Camada | Python | Spring |
| --- | --- | --- |
| config | `@dataclass(frozen=True)` + `load()` | `@ConfigurationProperties` |
| entrypoint | `argparse` + `build_facade()` | `@RestController` + `@Configuration` |
| facade | classe simples | `@Service` (caso de uso) |
| service | `Protocol` + classe | `interface` + `@Service` |
| repository | `Protocol` + adaptador | `interface` + `@Repository` |
| presenter | `ConsoleReporter` | serialização do DTO de resposta |
| exceptions | `RagException` | `@ControllerAdvice` + `@ExceptionHandler` |

**A diferença que importa:** em Spring o container resolve as dependências por tipo. Com
duas implementações da mesma interface, ele falha com `NoUniqueBeanDefinitionException`, e
você desempata com `@Primary` ou `@Qualifier`. Em Python o composition root escreve o nome
da classe, e a ambiguidade não existe.

Consequência: em Spring as escolhas concretas ficam espalhadas em anotações; em Python
ficam num arquivo só. Nenhum dos dois é melhor, mas saber a diferença evita procurar em
Python um container que não existe.

---

## 8. Checklist para começar um projeto novo

- [ ] Estrutura de pastas da seção 1 criada
- [ ] `.gitignore` com `.env` **antes** do primeiro `git add`
- [ ] `docker-compose.yml` com healthcheck que de fato roda na imagem escolhida
- [ ] Verificação de pré-condições antes da primeira chamada paga
- [ ] `Protocol` em toda fronteira externa
- [ ] mypy (ou o verificador da linguagem) rodando limpo
- [ ] Nenhuma camada com `print` ou `sys.exit`
- [ ] Grafo de dependências acíclico e descendente
- [ ] ADR registrando o que este projeto mudou em relação a esta guideline
- [ ] Contrato HTTP conforme `docs/contracts/` se o projeto expuser API

---

## 9. Referências

- `rag-01-fundamentos-pdf/docs/adrs/generated/RAG/ADR-005`, `ADR-006`, `ADR-007`
- `rag-01-fundamentos-pdf/docs/domains/rag/diagrams/c4/componente.puml`
- `rag-01-fundamentos-pdf/docs/guidelines/python-development-guidelines.md`
- `docs/contracts/rag-api.yaml` (contrato HTTP compartilhado)
