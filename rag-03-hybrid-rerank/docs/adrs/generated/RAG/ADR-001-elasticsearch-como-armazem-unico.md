# ADR-001: Elasticsearch como armazém único, com denso e BM25 no mesmo índice

- **Status:** aceito
- **Data:** 2026-07-28
- **Domínio:** RAG
- **Decisores:** arthu

## Contexto

O Projeto 3 precisa de dois caminhos de recuperação sobre o mesmo corpus: busca vetorial
densa (kNN sobre embeddings) e busca léxica por palavra chave (BM25). Eles existem porque
erram coisas diferentes. Embeddings capturam significado e falham em token exato: `E-4021`
e `E-4022` produzem vetores quase idênticos porque um código não carrega significado
semântico. BM25 acerta o token exato e falha no sinônimo. Juntos cobrem os buracos um do
outro, e é essa complementaridade que o projeto existe para medir.

O Projeto 2 usa Qdrant, que faz busca densa e não faz BM25. Portanto alguma coisa precisa
mudar, e a pergunta é o quê.

O guia da trilha instala `langchain-elasticsearch` **e** `rank-bm25` na mesma linha, sem
explicitar se os dois convivem. Essa ambiguidade precisa ser resolvida por decisão.

## Decisão

**Elasticsearch é o armazém único do projeto**, atendendo aos dois caminhos de busca sobre
o mesmo índice e sobre o mesmo documento.

Um chunk vira um documento. Esse documento carrega, lado a lado:

- o campo `embedding`, do tipo `dense_vector`, usado pelo kNN;
- o campo de texto, do tipo `text` **analisado**, usado pelo BM25;
- os metadados `source` e `page`, herdados do modelo de domínio.

Dois repositórios distintos leem esse mesmo índice: `VectorRepository` faz o kNN e
`KeywordRepository` faz o BM25. Cada um é `Protocol` com adaptador próprio, e nada do
vocabulário do Elasticsearch (`_id`, `_source`, `hits.hits`, a linguagem de query)
atravessa a fronteira deles.

**O `rank-bm25` não entra no projeto**, apesar de estar no `pip install` do guia. Ele seria
um segundo mecanismo de BM25, in process, sem persistência e carregando o corpus inteiro na
memória a cada processo, competindo com o BM25 que o Elasticsearch já oferece. Um motor de
busca por projeto.

**O mapping do índice é explícito no código**, criado junto com o índice, com o analisador
em português declarado. Nunca inferido. O motivo está em Consequências e é o risco técnico
mais sério deste projeto.

## Alternativas consideradas

### Manter o Qdrant para o denso e usar `rank-bm25` em memória para o léxico

Rejeitada. É a leitura literal do `pip install` do guia, e tem a vantagem real de
reaproveitar um armazém que já funciona e está validado no Projeto 2, sem container novo.

Recusada por três motivos que se somam. Primeiro, passariam a existir **dois armazéns com
o mesmo conteúdo**, e portanto o estado em que um está atualizado e o outro não; a ingestão
deixaria de ter um único ponto de escrita. Segundo, o `rank-bm25` não persiste: ele
reconstrói o índice invertido em memória a cada processo, o que faz o custo de subir o
`ask.py` crescer com o corpus e torna a medição de latência incomparável entre execuções.
Terceiro, ele não é um motor de busca, é uma biblioteca de scoring, e não oferece
analisador, stemming ou stopwords em português, que é justamente o que faz o BM25 valer a
pena em um corpus real.

### Elasticsearch com dois índices, um por caminho

Rejeitada. Só se pagaria se cada caminho precisasse de tokenizador ou de ciclo de
reindexação próprio, o que não é o caso: os dois consomem o mesmo chunk, gerado na mesma
passada. Dois índices trariam de volta o problema de sincronização da alternativa anterior,
agora dentro do mesmo motor.

### Qdrant com a busca esparsa nativa dele

Não considerada a fundo, e vale registrar o porquê. O Qdrant oferece vetores esparsos, que
permitem uma aproximação de busca léxica. Recusada porque o guia da trilha e a guideline do
workspace apontam para o Elasticsearch, porque a busca esparsa por vetor não é BM25 e
tornaria a comparação com a literatura confusa, e porque conhecer o motor de busca da
família Lucene é parte declarada do que o projeto ensina.

## Consequências

**Positivas**

- Uma passada de ingestão, um ponto de escrita, nenhuma sincronização entre armazéns.
- O `_id` do documento vira a chave natural de deduplicação do RRF. O guia usa
  `page_content[:200]` como chave, atalho que colide em dois chunks com o mesmo começo de
  texto e que silenciosamente funde trechos distintos.
- Um container em vez de dois numa máquina que já hospeda o Qdrant do Projeto 2 e os Chroma
  dos Projetos 1 e 2.
- BM25 de verdade, com analisador em português, stemming e stopwords, em vez de uma
  aproximação.

**Negativas**

- **O risco do mapping.** Se o campo de texto for mapeado como `keyword` em vez de `text`
  analisado, o BM25 passa a casar apenas o valor inteiro do campo e nunca os termos. Metade
  do funil para de funcionar **sem erro nenhum**, e a conclusão do projeto vira "a híbrida
  não ajudou" quando a verdade é que a híbrida nunca rodou. Mitigado por mapping explícito,
  por conferência no `HealthChecker` e por teste de fumaça que busca um termo raro só pelo
  caminho BM25 e exige hit.
- O Elasticsearch sozinho consome de 1 a 2 GB de RAM, e a guideline do workspace já
  recomendava subir um serviço por vez. Aqui isso deixa de ser recomendação.
- Cerca de 30 segundos até aceitar conexão. Healthcheck no compose passa a ser obrigatório,
  não opcional.
- Perde se a continuidade direta com o Projeto 2 no adaptador de armazém. O código de
  Qdrant não é reaproveitado, embora o `Protocol` seja.
- Dois repositórios adaptando o mesmo motor dobram a superfície por onde o vocabulário do
  Elasticsearch pode vazar. Ver [[ADR-003-fusionservice-e-searchhit-com-procedencia]].

## Referências

- `docs/domains/rag/hld.md`, "Arquitetura geral" e "Riscos arquiteturais e mitigação"
- `../docs/guidelines/arquitetura-em-camadas.md`, seção 5
- `docs/guidelines/README.md`, "Stack confirmada"
- Precedente conceitual: ADR-001 do `rag-02-conversacional-citacoes`, que fixou a mesma
  regra de não vazar vocabulário do armazém através do `VectorRepository`
- [[ADR-002-rrf-em-python]]
