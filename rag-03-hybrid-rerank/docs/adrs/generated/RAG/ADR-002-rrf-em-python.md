# ADR-002: Reciprocal Rank Fusion implementado em Python, não delegado ao Elasticsearch

- **Status:** aceito
- **Data:** 2026-07-28
- **Domínio:** RAG
- **Decisores:** arthu

## Contexto

Fundir dois rankings exige resolver um problema concreto: os scores são incomparáveis. O
BM25 devolve algo como `14.7`, numa escala sem limite superior que depende da frequência
dos termos no corpus; a busca densa por cosseno devolve algo como `0.83`, limitado a
`[-1, 1]`. Não existe normalização honesta entre eles, porque as duas escalas não medem a
mesma grandeza.

Reciprocal Rank Fusion resolve isso ignorando o valor e usando só a **posição**:

```
score(d) = Σ  1 / (k + rank(d, r) + 1)
          r
```

para cada ranking `r` em que o documento `d` aparece, com `k` tipicamente 60. Um documento
presente nos dois rankings soma as duas contribuições, e é por isso que a fusão o promove.
Por não depender de escala, o RRF virou padrão de fato.

O Elasticsearch, a partir da versão 8.x, oferece um retriever `rrf` nativo que faz
exatamente isso dentro do motor, numa única requisição.

## Decisão

**O RRF é implementado em Python**, no `FusionService`, e não delegado ao retriever nativo
do Elasticsearch.

A implementação recebe uma lista de rankings e devolve um ranking fundido e deduplicado.
Não conhece Elasticsearch, não conhece LangChain e não tem dependência nenhuma. A chave de
deduplicação é o `_id` do documento, resolvido no adaptador antes de a lista chegar aqui.

O parâmetro `k` é exposto e configurável, não constante escondida. O exercício 1 do guia
manda variá lo (valor baixo dá muito peso ao primeiro colocado; alto achata tudo), e um
parâmetro que se pretende variar precisa ser parâmetro.

## Alternativas consideradas

### Usar o retriever `rrf` nativo do Elasticsearch

Rejeitada, e é a alternativa mais forte. Ela produziria menos código, uma requisição HTTP
em vez de duas, e a fusão rodaria mais perto dos dados.

Recusada por dois motivos. O primeiro é pedagógico e é explícito: escrever o RRF à mão é o
entregável do projeto. O guia da trilha traz as sete linhas da função porque entender que a
fusão usa posição e não valor é a ideia central, e delegar isso ao motor entrega o
resultado escondendo o mecanismo. O segundo é arquitetural e sobrevive ao fim do estudo: a
estratégia de fusão passaria a ser propriedade do armazém. Trocar Elasticsearch por outro
motor custaria, além do adaptador, reimplementar a fusão, quando ela não tem nada a ver com
onde os dados estão guardados.

### Normalizar os scores e somar

Rejeitada. É a solução ingênua e é pior do que parece. Normalizar exige conhecer o mínimo e
o máximo de cada escala, que no BM25 dependem do corpus e da query, então a normalização
teria que ser feita por consulta sobre os candidatos retornados. Isso torna o score de um
documento dependente de quem mais foi retornado com ele, o que é instável entre execuções e
inviabiliza medição reprodutível.

### Fundir por interseção ou por união simples

Rejeitada. Interseção descarta o documento que só um caminho encontrou, que é exatamente o
caso que motiva a busca híbrida. União sem pontuação não produz ranking, só um conjunto.

## Consequências

**Positivas**

- A fusão é **função pura**: recebe listas, devolve lista, sem dependência externa. É o
  componente mais barato de testar do projeto inteiro, e a guideline manda testá lo.
- A estratégia de fusão fica independente do motor. Trocar o armazém custa adaptadores, não
  a fusão.
- O `k` é visível, variável e medível, o que é pré requisito do exercício 1.
- O comportamento é determinístico e reprodutível, o que a medição exige.

**Negativas**

- Uma requisição HTTP a mais ao Elasticsearch e uma passada extra em Python sobre algumas
  dezenas de documentos. Custo real, e pequeno perto do embedding da query e do cross
  encoder. Ver [[ADR-006-buscas-em-sequencia]].
- Reimplementa algo que o motor já oferece, o que a quem chegar depois pode parecer
  duplicação. Este ADR existe para responder essa pergunta.

## Referências

- `docs/domains/rag/hld.md`, "Fluxo de requisições e de dados"
- `../README.md`, seção "Projeto 3", subseção "O núcleo, fusão RRF"
- [[ADR-001-elasticsearch-como-armazem-unico]]
- [[ADR-003-fusionservice-e-searchhit-com-procedencia]]
