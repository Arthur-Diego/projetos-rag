# ADR-006: Nomenclatura em camadas explícitas

- **Status:** aceito
- **Data:** 2026-07-25
- **Domínio:** RAG
- **Decisores:** arthu
- **Emenda:** [[ADR-005-segregacao-por-responsabilidade]] (a segregação continua
  valendo; muda apenas a convenção de nomes e o empacotamento)

## Contexto

O ADR-005 segregou o pipeline em dez módulos por responsabilidade, nomeados pelo
**domínio**: `loading`, `chunking`, `store`, `retrieval`, `prompting`, `generation`,
`reporting`. As classes seguiram a mesma linha, em português: `CarregadorPdf`,
`DivisorRecursivo`, `ArmazemChroma`, `Recuperador`, `Relator`.

Dois problemas apareceram no uso.

**Um defeito objetivo: o idioma estava misturado.** Módulos em inglês (`store`,
`loading`, `chunking`) e classes em português (`ArmazemChroma`, `CarregadorPdf`).
O arquivo `store.py` definia `ArmazemVetorial`, que é a mesma palavra em dois idiomas
no mesmo arquivo. Isso não era escolha, era inconsistência.

**Uma limitação de comunicação.** Nomes de domínio dizem o que a peça faz, mas não onde
ela está na hierarquia de chamadas. `ChunkingService` diz "serviço"; `chunking` não diz.
Para quem vem de Java, C# ou Spring, o sufixo de estereótipo é lido instantaneamente e
carrega a direção da dependência junto.

Dois fatos deslocaram o equilíbrio a favor da segunda leitura:

- O ADR-005 tornou **praticar design arquitetural** um objetivo declarado do repositório,
  ao lado de aprender RAG. O vocabulário de camadas passa a ter valor por si.
- Os **Projetos 8, 9 e 10 da trilha são Spring AI**, onde `@Service`, `@Repository` e
  `@RestController` são obrigação do framework. Chegar fluente nesse vocabulário é ganho
  direto.

## Decisão

Adotar nomenclatura em camadas explícitas, com o **código em inglês** e as **mensagens ao
usuário e a documentação em português**. Isso resolve a mistura de idiomas de uma vez.

```
rag/
├── exceptions.py                RagException e subclasses
├── config.py                    RagProperties (equivalente a @ConfigurationProperties)
├── domain/
│   └── models.py                SearchHit (objeto de valor)
├── repository/                  fala com fontes externas
│   ├── document_reader.py       DocumentReader + PdfDocumentReader
│   └── vector_repository.py     VectorRepository + ChromaVectorRepository
├── service/                     regra e orquestração de uma responsabilidade
│   ├── health_checker.py        HealthChecker
│   ├── chunking_service.py      ChunkingService + RecursiveChunkingService
│   ├── retrieval_service.py     RetrievalService
│   ├── prompt_builder.py        PromptBuilder
│   └── generation_service.py    GenerationService + OpenAiGenerationService
└── presenter/
    └── console_reporter.py      ConsoleReporter
```

A direção da dependência fica legível pelo nome: `entrypoint -> service -> repository`.
Nenhum `repository` importa `service`.

**Nomes deliberadamente não adotados**, porque seriam factualmente errados aqui:

| Nome | Por que não |
| --- | --- |
| `Entity` | Implica identidade e ciclo de vida persistido. `SearchHit` e `Document` são objetos de valor, definidos só pelo conteúdo. Daí `domain/models.py`. |
| `Controller` | Implica manipulação de requisição HTTP. Não há HTTP entrante; `ingest.py` e `ask.py` são CLIs. |
| `Facade` | Não há subsistema complexo a esconder atrás de uma interface simplificada. |
| `Helper` / `Util` | Depósito. Um módulo com esse nome atrai tudo que não coube em outro lugar, e é onde a estrutura apodrece primeiro. |

`SearchHit` deixou de ser um alias `tuple[Document, float]` e virou `NamedTuple`: continua
desempacotável como tupla e ganha acesso por atributo (`hit.distance`), o que torna o
código de apresentação legível sem comentário.

## Alternativas consideradas

### Manter nomes de domínio e só unificar o idioma

Rejeitada pelo autor. Era a recomendação apresentada, por três razões: nomes de domínio
comunicam propósito em vez de estereótipo; a convenção do Python é essa (a biblioteca
padrão é `json`, `csv`, `sqlite3`, nunca `JsonService`); e alguns sufixos não acrescentam
informação, apenas rótulo (`ChunkingService` não diz nada que `chunking` já não dissesse).

Corrigiria o defeito real (idioma misturado) sem trocar a filosofia, e a hierarquia
continuaria vindo do C4 e do grafo de dependências, que são mais precisos que um sufixo.

### Híbrido: pastas por camada, nomes de classe por domínio

Rejeitada pelo autor. Daria a hierarquia visível na árvore de arquivos sem encher as
classes de sufixo redundante. Fica registrada como o meio-termo que existia.

## Consequências

**Positivas**
- Idioma coerente: código em inglês, mensagens e documentação em português.
- A camada e a direção da chamada são legíveis pelo nome, sem consultar diagrama.
- Vocabulário alinhado com os Projetos 8 a 10, que são Spring AI.
- A árvore de pastas passa a ser, ela própria, documentação da arquitetura.

**Negativas**
- Menos idiomático em Python. Um pythonista lê `RetrievalService` e reconhece hábitos de
  outra linguagem.
- Alguns sufixos são rótulo sem informação nova. `ChunkingService` não diz mais que
  `chunking`; diz apenas "isto é um serviço".
- Caminhos de import mais longos
  (`from rag.repository.vector_repository import ChromaVectorRepository`).
- 18 arquivos para 235 linhas de lógica. A razão entre estrutura e conteúdo, já alta no
  ADR-005, subiu de novo.
- Risco conhecido da convenção: a facilidade de criar `XxxService` convida a criar
  camadas vazias que só delegam. Não há nenhuma hoje, e não deve haver.

**Comportamento observável: inalterado.** Os oito critérios de aceite do FDD foram
reexecutados após a renomeação, com resultados idênticos, incluindo `dist 0.875` na
mesma pergunta e a frase de escape byte a byte. Renomeação que muda comportamento não é
renomeação.

## Referências

- `docs/domains/rag/hld.md`, seção Componentes e responsabilidades
- `docs/domains/rag/diagrams/c4/componente.puml`
- [[ADR-005-segregacao-por-responsabilidade]]
