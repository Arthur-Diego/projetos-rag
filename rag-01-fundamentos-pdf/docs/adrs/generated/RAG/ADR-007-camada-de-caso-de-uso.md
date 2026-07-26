# ADR-007: Camada de caso de uso (facade) separada dos entrypoints

- **Status:** aceito
- **Data:** 2026-07-25
- **Domínio:** RAG
- **Decisores:** arthu
- **Emenda:** [[ADR-006-nomenclatura-em-camadas]]

## Contexto

Depois do ADR-006, `ingest.py` e `ask.py` acumulavam três responsabilidades distintas:

| | Papel | Equivalente Spring |
| --- | --- | --- |
| 1 | Receber argv, validar, traduzir exceção em código de saída | `@RestController` |
| 2 | Escolher implementações concretas e montar o grafo de objetos | `@Configuration` / `@Bean` |
| 3 | Orquestrar o caso de uso | camada ausente |

Os papéis 1 e 2 pertencem legitimamente ao entrypoint: em Python não há container de
injeção de dependência, então alguém precisa escrever `ChromaVectorRepository(...)` com a
mão, e o entrypoint é o lugar honesto para isso. É o padrão *composition root*.

O papel 3 é o problema. A função `run()` de cada entrypoint continha a lógica do caso de
uso misturada com `argparse` e com escrita em `sys.stderr`. Consequência prática: era
impossível executar "responda esta pergunta" sem simular linha de comando, o que bloqueia
três usos previsíveis nesta trilha:

- um teste que exercite o fluxo completo sem terminal;
- uma API HTTP, que é literalmente o Projeto 8 (`POST /chat`);
- um servidor MCP, que é o Projeto 10.

## Decisão

Extrair o caso de uso para `rag/facade/`, com duas classes:

- `QueryFacade.ask(question) -> Answer` orquestra retrieve, augment e generate.
- `IngestionFacade.ingest() -> IngestionReport` orquestra load, split, embed e store.

**Regra dura, e é ela que torna a extração real:** as facades não importam
`ConsoleReporter`, `argparse`, `sys.stdout` nem `sys.stderr`. Elas devolvem objetos de
domínio; a apresentação é decisão de quem chamou. Uma facade que escrevesse na tela seria
delegação decorativa, e é exatamente o risco de camada vazia registrado no ADR-006.

Para isso, dois objetos de valor novos em `rag/domain/models.py`:

```python
class Answer(NamedTuple):
    text: str
    hits: list[SearchHit]
    search_s: float
    generation_s: float

class IngestionReport(NamedTuple):
    pages: int
    chunks: int
    discarded_pages: int
    previous_chunks: int
    chunk_size: int
    chunk_overlap: int
    seconds: float
```

Os entrypoints ficam com duas seções explícitas: `parse_args()` (controller) e
`build_facade()` (composition root).

`IngestionFacade.files()` continua exposto separadamente de `ingest()`, porque o chamador
precisa listar o que vai ser indexado **antes** do trabalho começar. É a mitigação do
risco do ADR-004: um corpus de controle indexado por engano fica visível na listagem.

## Consequência observável: a mensagem de recriação mudou

Esta é a única mudança de comportamento, e ela é consequência direta do desenho.

Uma facade que devolve dados não pode emitir progresso durante a execução. A mensagem
sobre a coleção anterior deixou de ser um anúncio e passou a ser um relato:

| | Antes | Depois |
| --- | --- | --- |
| Texto | `coleção 'livros' já existe com 617 chunks, recriando do zero` | `coleção 'livros' tinha 617 chunks, recriada do zero` |
| Momento | antes da ingestão | depois, junto do relatório |
| Ordem | antes do `lendo <arquivo>` | depois |

O tempo verbal foi ajustado por honestidade: no novo desenho, quando a mensagem aparece,
a recriação já aconteceu. Manter "recriando" seria descrever no presente um fato passado.

O critério de aceite 2 do FDD citava a string antiga como evidência e foi atualizado.

## Alternativas consideradas

### Não extrair, esperar o segundo cliente

Rejeitada pelo autor. Era a recomendação apresentada: com um único chamador por fluxo, a
facade é delegação pura, e o `run()` já estava isolado o bastante para que a extração
fosse mecânica quando fizesse falta. O argumento contrário que prevaleceu é que praticar
a separação é objetivo declarado do repositório desde o ADR-005, e que os três clientes
futuros são previsíveis, não hipotéticos.

### Facade com callback de progresso

Rejeitada. Resolveria a mudança na ordem das mensagens, mas reintroduziria acoplamento
com a apresentação por uma porta lateral. A facade passaria a saber que alguém quer ser
avisado durante a execução, que é meio caminho para saber que existe um terminal.

### Extrair só no `ask.py`, como experimento

Rejeitada pelo autor. Deixaria os dois fluxos assimétricos por tempo indeterminado.

## Consequências

**Positivas**
- O caso de uso passa a ser chamável sem terminal: `QueryFacade(...).ask("pergunta")`
  devolve um `Answer` completo, com trechos e latências.
- Teste de fluxo completo vira possível sem simular `argparse` nem capturar `stderr`.
- Os entrypoints ficaram com duas seções nomeadas e nada mais.
- O grafo de camadas ficou estritamente descendente: `facade -> service -> repository ->
  domain`. Nenhuma camada importa outra acima dela.

**Negativas**
- Mais uma camada para um único cliente por fluxo, hoje. O ganho é antecipado.
- A facade não pode reportar progresso, e daí a mudança na mensagem de recriação. Numa
  ingestão longa, o usuário fica sem retorno até o fim.
- 21 arquivos para cerca de 250 linhas de lógica.

## Referências

- `docs/domains/rag/features/pipeline-rag-pdf-fdd.md`, seções 9 e 11
- `docs/domains/rag/diagrams/c4/componente.puml`
- [[ADR-006-nomenclatura-em-camadas]]
- [[ADR-004-corpus-de-controle-fora-do-indice]]
