# ADR-003: `FusionService` como componente próprio e `SearchHit` com procedência

- **Status:** aceito
- **Data:** 2026-07-28
- **Domínio:** RAG
- **Decisores:** arthu
- **Diverge de:** `../docs/guidelines/arquitetura-em-camadas.md`, seção 5

## Contexto

A seção 5 da guideline do workspace, "Como cada projeto estende sem acoplar", antecipa o
que cada projeto acrescenta. Para o Projeto 3 ela prevê:

| Projeto | O que acrescenta | Onde |
| --- | --- | --- |
| 3 híbrido | `KeywordRepository` (BM25), `RerankService` | `repository/`, `service/` |

A previsão está certa nos dois componentes que nomeia, e **incompleta**: ela não prevê onde
mora a fusão RRF, que o [[ADR-002-rrf-em-python]] decidiu implementar em Python. Sobram dois
lugares plausíveis, dentro do `RetrievalService` ou em componente próprio, e a guideline não
decide entre eles.

Há um segundo problema, e ele aparece assim que existem dois caminhos de busca. O
`SearchHit` do Projeto 2 carrega um `score` único, que é a distância no espaço vetorial.
Com o funil, "score" deixa de ter significado único: o BM25 devolve `14.7`, a busca densa
`0.83`, o RRF um adimensional na casa de `0.03` e o cross encoder outra escala ainda. Um
campo chamado `score` carregando qualquer um desses é um campo que muda de significado
conforme a configuração, sem que nada indique qual está ali.

## Decisão

**O RRF mora em um `FusionService` próprio, em `service/`.** Ele recebe uma lista de
rankings e devolve um ranking fundido e deduplicado. Não tem dependência nenhuma.

O `RetrievalService` continua dono da **política** de recuperação: valida as faixas de
`candidates`, `rrf_k` e `top_n`, dispara os dois repositórios, entrega os rankings à fusão,
passa o resultado ao rerank e devolve os finais. Ele orquestra e não calcula.

**O `SearchHit` ganha procedência.** Passa a carregar de qual caminho ou caminhos o trecho
veio, a posição que ocupou em cada ranking, o score do RRF e o score do rerank. O campo de
distância densa continua existindo, agora significando uma coisa só.

**A seção 5 da guideline fica como está.** Ela registra a previsão original, e este ADR é
encontrável a partir dela. Mesmo tratamento que o ADR-003 do `rag-02-conversacional-citacoes`
deu à divergência dele sobre o `ConversationMemory`.

## Alternativas consideradas

### Colocar o RRF dentro do `RetrievalService`

Rejeitada. Produziria um arquivo a menos e não violaria nenhuma regra de camada, já que o
`RetrievalService` está em `service/` de qualquer forma.

Recusada por testabilidade, que aqui não é argumento genérico e sim o argumento decisivo. A
guideline manda testar a fusão, e o `rrf_k` é parâmetro que o exercício 1 do guia manda
variar. Dentro do `RetrievalService`, testar a fusão exige dublar dois repositórios e um
serviço de rerank para exercitar uma função que não depende de nenhum deles. Fora, o teste é
uma lista entrando e uma lista saindo. Além disso o `RetrievalService` passaria a acumular
três responsabilidades (política de faixas, orquestração dos caminhos, cálculo da fusão), e
a seção 4 da guideline é explícita sobre componentes que fazem tudo.

### Atualizar a seção 5 da guideline para incluir o `FusionService`

Rejeitada pelo autor. Deixaria a guideline correta para quem a ler antes do código.

Recusada porque a guideline é previsão feita antes de construir e o ADR é o que se
descobriu construindo; sobrescrever a previsão apaga o registro de que ela errou, que é
informação. Também porque o `rag-02` já divergiu da mesma seção sem atualizá la, então
corrigir só este caso deixaria o documento com um ponto reconciliado e outro não, o que é
pior do que dois pontos divergentes com ADR cada.

### Manter o `SearchHit` como está e publicar a procedência apenas em `meta`

Rejeitada. Evitaria mexer no modelo de domínio. Recusada porque a procedência não é extra de
diagnóstico deste projeto: ela é o **dado bruto da tabela de medição**, que é o entregável
declarado. Sem ela não há como preencher as três colunas, e o `chat.py` não tem como mostrar
por que um trecho subiu. Dado que sustenta o entregável pertence ao domínio.

## Consequências

**Positivas**

- A fusão vira o componente mais barato de testar do projeto, sem um único dublê.
- A `QueryFacade` não muda uma linha. Isso é a evidência de que a estrutura em camadas
  herdada do Projeto 1 aguentou uma troca de mecanismo de recuperação sem vazar para cima.
- O `SearchHit` passa a explicar a própria ordem. Quem lê a resposta consegue distinguir
  "o BM25 achou e a densa não" de "os dois acharam e a fusão promoveu".
- A tabela de medição se torna extraível da resposta, sem instrumentação paralela.

**Negativas**

- Divergência do documento estrutural da trilha. Quem ler a guideline e depois o código vai
  encontrar um componente a mais e depende deste ADR para entendê lo.
- O `SearchHit` fica mais largo, com campos que só fazem sentido em algumas configurações
  (o score de rerank é nulo quando o rerank está desligado). É o preço de o hit ser honesto
  sobre de onde veio, e o contrato trata isso marcando os campos como opcionais. Ver
  [[ADR-005-contrato-compartilhado-1-2-0]].
- Se um projeto futuro fundir por outro critério que não posição, o `FusionService` precisa
  virar `Protocol`. Hoje é implementação concreta, porque uma implementação não justifica
  inversão.

## Nota de 28/07/2026

Dois pontos deste ADR foram refinados depois, e ficam aqui para quem o ler
isolado:

- **"dispara os dois repositórios"** deixou de ser literal. O
  [[ADR-009-services-por-caminho-de-busca]] pôs `DenseSearchService` e
  `KeywordSearchService` entre o orquestrador e os repositórios. A
  responsabilidade descrita aqui não mudou; mudou com quem ele fala.
- **`SearchHit` ganhou um terceiro campo além de `score` e `provenance`:**
  `doc_id`, a identidade do trecho no armazém. É a chave de deduplicação da fusão,
  e é o único identificador do motor que atravessa a fronteira do repositório. Sem
  ele a fusão cairia no `page_content[:200]` do guia da trilha, que funde em
  silêncio dois trechos distintos que comecem igual. Não é emitido no JSON.

## Referências

- `../docs/guidelines/arquitetura-em-camadas.md`, seções 4 e 5
- `docs/domains/rag/hld.md`, "Componentes e responsabilidades" e "Modelo de dados"
- Precedente de forma: ADR-003 do `rag-02-conversacional-citacoes`
- [[ADR-002-rrf-em-python]]
- [[ADR-005-contrato-compartilhado-1-2-0]]
