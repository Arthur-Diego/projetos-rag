# ADR-009: Cada caminho de busca é encapsulado por um service, mesmo delegando

- **Status:** aceito
- **Data:** 2026-07-28
- **Domínio:** RAG
- **Decisores:** arthu
- **Diverge de:** `../docs/guidelines/arquitetura-em-camadas.md`, seção 4

## Contexto

Depois de o [[ADR-008-pacote-retrieval-dentro-de-service]] agrupar o funil em
`rag/service/retrieval/`, ficou visível uma assimetria: o pacote continha duas
das quatro etapas do funil (fusão e reordenação), enquanto as outras duas (busca
densa e busca léxica) viviam em `repository/`. Abrir a pasta não contava a
história inteira, que era justamente o objetivo do ADR-008.

**O conflito é real e vale enunciar sem suavizar.** A seção 4 da guideline do
workspace lista, entre os antipadrões, a camada que só repassa:

> `Facade` para uma única operação trivial: facade só se paga quando existe mais
> de um cliente, ou quando o caso de uso precisa ser chamável sem terminal.
> **Delegação pura é camada vazia.**

E os dois repositórios não têm política própria hoje. Os dois expõem a mesma
assinatura, `search(query, k) -> list[SearchHit]`. Um serviço em cima disso tem o
corpo inteiro em uma linha de repasse. Há ainda um agravante: os repositórios
**já são `Protocol`**, então a substituibilidade, que costuma ser a razão de
existir de um serviço acima do adaptador, já estava garantida. Os serviços dão uma
segunda costura no mesmo ponto.

O autor foi informado disso, com o precedente do Projeto 2 (o ADR-003 de lá
recusou o `ConversationMemory` exatamente por esse argumento) e com a
recomendação de **esperar o gatilho**: criar os serviços no dia em que um dos
caminhos ganhasse política própria. Ele decidiu criar assim mesmo, pela
legibilidade da pasta. Este ADR registra a decisão e o custo, para que quem ler
depois saiba que a camada vazia foi **escolha consciente e não descuido**.

## Decisão

**`DenseSearchService` e `KeywordSearchService` existem em
`rag/service/retrieval/`, e o `RetrievalService` fala com eles em vez de falar com
os repositórios.**

O pacote passa a conter as quatro etapas do funil como pares:

```
rag/service/retrieval/
├── dense_search_service.py      busca por significado
├── keyword_search_service.py    busca por palavra exata
├── fusion_service.py            funde por posição
├── rerank_service.py            reordena por precisão
└── retrieval_service.py         orquestra os quatro
```

Os repositórios **permanecem em `repository/`**. A decisão não os move: a
fronteira deles é de camada, e os serviços novos são um degrau acima dela.

**A assimetria entre os dois serviços é deliberada e não deve ser "corrigida".**
`DenseSearchService` delega dois métodos (`search` e `indexed_count`); o léxico
delega um. O motivo é que o repositório denso é o dono do índice e do mapping
(ADR-001), então é dele que sai a contagem que o `require_index` consulta. Forçar
o serviço léxico a expor uma contagem que ele não tem produziria simetria falsa.

Nos testes, os dublês continuam sendo **repositórios**, embrulhados nos serviços
reais. Dublar os serviços também esconderia justamente a delegação que este ADR
introduz, e um repasse quebrado passaria despercebido.

## Alternativas consideradas

### Esperar o gatilho e não criar agora

Rejeitada pelo autor, e era a recomendação. Evitaria dois arquivos sem conteúdo e
manteria a guideline intacta.

O gatilho continua nomeado, e vale registrar porque é quando estes arquivos
deixam de ser vazios: BM25 ganhar tratamento de query próprio (aspas para frase
exata, boost por campo, sinônimos); o caminho denso ganhar expansão de query,
cache de embedding ou HyDE; os dois passarem a ter contagens de candidatos
diferentes; ou o Projeto 4, que acrescenta consulta ao docstore depois da
recuperação densa e quase certamente cria política de caminho.

Recusada porque a legibilidade do pacote foi julgada como valendo o custo, e
porque num projeto de estudo a estrutura também ensina: ver as quatro etapas lado
a lado torna o funil compreensível antes de o leitor conhecer o código.

### Criar os serviços com responsabilidade real, em vez de repasse

Proposta como meio-termo e não escolhida. Cada serviço passaria a ser dono da
própria contagem de candidatos e da própria cronometragem, e o `RetrievalService`
deixaria de medir `dense_s` e `keyword_s` por fora, aplicando um nível abaixo a
mesma correção que o [[ADR-007-retrieval-devolve-resultado-com-metrica]] fez acima.

Recusada pelo autor. Registrada aqui porque é o caminho natural de evolução
quando o gatilho chegar: os arquivos já existem, e passar a política para dentro
deles é uma mudança contida.

### Mover os repositórios para dentro de `retrieval/`

Rejeitada, e já havia sido rejeitada na conversa que originou o ADR-008. Colocaria
um adaptador de infraestrutura dentro de um pacote de serviço, misturando o eixo
"qual camada" com o eixo "qual assunto". A regra "nada do vocabulário do motor
sobe de camada" perderia a fronteira que a torna verificável.

## Consequências

**Positivas**

- `rag/service/retrieval/` conta a história inteira do funil: quatro etapas, um
  orquestrador, todos no mesmo lugar.
- Existe um lugar óbvio para a política de caminho quando ela aparecer, e ela vai
  aparecer no Projeto 4.
- O `RetrievalService` deixa de importar repositórios, o que reduz o que ele
  conhece: ele passa a falar só com pares da própria camada.

**Negativas**

- **Duas camadas vazias**, pelo critério da própria guideline. Enquanto não houver
  política de caminho, os dois arquivos são repasse, e quem os abrir procurando
  lógica não vai encontrar.
- Segunda costura sobre um `Protocol` que já existia. Trocar o adaptador continua
  custando uma linha, mas agora há dois pontos onde alguém pode inserir
  comportamento, e o menos óbvio dos dois é o novo.
- Terceira divergência da guideline neste projeto, depois dos ADR-003 e ADR-008.
  Três é o suficiente para valer a pergunta, no fechamento da trilha, se a
  guideline é que precisa mudar.
- Indireção a mais para depurar: uma busca que devolve resultado errado agora
  passa por dois arquivos antes do adaptador.

## Referências

- `../docs/guidelines/arquitetura-em-camadas.md`, seção 4
- `rag/service/retrieval/__init__.py`
- ADR-003 do `rag-02-conversacional-citacoes`, o precedente que recusou uma camada
  vazia pelo mesmo argumento
- [[ADR-008-pacote-retrieval-dentro-de-service]]
- [[ADR-007-retrieval-devolve-resultado-com-metrica]]
