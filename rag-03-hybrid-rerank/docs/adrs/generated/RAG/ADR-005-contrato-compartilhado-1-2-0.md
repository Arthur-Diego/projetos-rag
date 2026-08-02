# ADR-005: Contrato compartilhado evoluído para 1.2.0, de forma aditiva

- **Status:** aceito, com **revisão de 28/07/2026** (ver Revisão)
- **Data:** 2026-07-28
- **Domínio:** RAG
- **Decisores:** arthu

## Contexto

O contrato `docs/contracts/rag-api.yaml` é compartilhado pelos projetos do workspace e
consumido pelo frontend React genérico, que renderiza controles a partir de
`GET /capabilities`. Está hoje na versão **1.1.0**, elevada pelo Projeto 2 (ADR-005 de lá) de
forma aditiva, acrescentando três campos opcionais.

O funil de recuperação deste projeto pressiona o contrato em dois pontos, e só dois. Foram
conferidos um a um antes desta decisão.

**Onde o contrato já basta.** Os parâmetros novos do funil (`candidates`, `rrf_k`, `top_n` e
a estratégia `densa | híbrida | híbrida+rerank`) **não exigem mudança de schema**. O schema
`Parameter` já suporta `type: enum` com `options`, além de `minimum` e `maximum`, e o
frontend renderiza o controle a partir do que for publicado. A comparação das três
configurações fica disponível no navegador sem uma linha de frontend.

**Onde o contrato não basta.**

1. `timings` tem `rewrite_s`, `search_s` e `generation_s`. Um funil de três estágios medido
   como um `search_s` único não permite responder ao exercício 3 do guia, "rerankear 50
   candidatos em vez de 20 melhora quanto, e custa quantos ms?". A medição por estágio é o
   instrumento principal deste projeto, não conforto de diagnóstico.
2. `SearchHit` tem `distance`. Com RRF, **distância não existe mais**: o valor fundido é
   adimensional e a posição vem de dois rankings incomparáveis. Manter `distance` carregando
   o resultado do funil transforma um campo bem definido num campo que mente conforme a
   configuração.

## Decisão

**O contrato sobe para 1.2.0, e a mudança é aditiva pura.** Todo campo novo é opcional, de
modo que `rag-01` e `rag-02` continuam válidos sem uma linha alterada.

O que a versão acrescenta:

- `timings` ganha `keyword_s`, `fusion_s` e `rerank_s`, opcionais, com a mesma justificativa
  que o Projeto 2 registrou para `rewrite_s`: estágio novo que não é medido em separado é
  custo não atribuível.
- `SearchHit` ganha `score` e `provenance`, opcionais. `provenance` informa de qual caminho
  ou caminhos o trecho veio e a posição em cada ranking.

O que a versão **não** faz:

- `distance` **é mantido**, e passa a ser documentado como válido apenas na estratégia
  puramente densa. Depreciar em vez de remover é o que mantém os dois projetos anteriores
  funcionando sem alteração.

## Alternativas consideradas

### Publicar tudo em `meta`, sem tocar no contrato

Rejeitada. O contrato tem um ponto de extensão desenhado exatamente para isso
(`Answer.meta`, `additionalProperties: true`), e o Projeto 2 já o usa para publicar
`unresolved_labels`. Custo zero e risco zero.

Recusada porque `meta` é o lugar do que é **anomalia diagnosticável de um projeto**, e é
assim que o próprio contrato o descreve. Latência por estágio e procedência de hit não são
anomalia: são a saída principal deste projeto e são conceitos que qualquer RAG híbrido tem.
Além disso o frontend não sabe ler `meta` de forma estruturada, então a medição ficaria
invisível na interface, e o `distance` continuaria mentindo de qualquer jeito.

### Subir para 2.0.0 com quebra, removendo `distance`

Rejeitada. Limparia de vez um campo que passa a ser parcialmente válido.

Recusada por custo desproporcional: quebraria dois projetos que funcionam e estão validados
para arrumar um campo que a documentação resolve. Depreciação é o instrumento correto quando
o campo continua correto no contexto em que nasceu, e `distance` continua exatamente correto
na estratégia densa.

### Criar um contrato separado para o Projeto 3

Rejeitada de plano. Destruiria a propriedade que dá valor ao contrato compartilhado, que é o
mesmo frontend servir os dez projetos, e é justamente a comparação entre projetos que a
trilha quer possibilitar.

## Consequências

**Positivas**

- `rag-01` e `rag-02` seguem válidos sem alteração. Compatibilidade retroativa preservada
  pela segunda vez seguida, o que confirma que a estratégia aditiva do ADR-005 do Projeto 2
  se sustenta.
- A tabela de medição vira extraível da própria resposta da API, sem instrumentação
  paralela.
- O frontend ganha as três configurações comparáveis sem alteração de código.
- O `distance` para de mentir por documentação, sem custar quebra.

**Negativas**

- `timings` acumula seis campos opcionais, e um consumidor ingênuo pode assumir que todos
  estão presentes. O contrato marca cada um com a versão em que entrou, como já fazia.
- Campo depreciado que permanece é dívida: `distance` vai conviver com `score` até algum
  projeto futuro justificar uma versão maior.
- O arquivo do contrato é compartilhado, então esta alteração toca um artefato fora do
  diretório deste projeto. É a natureza dele, e o precedente do Projeto 2 já a estabeleceu.

## Revisão de 28/07/2026: "aditivo puro" era falso, e o que mudou

Este ADR prometeu que a versão 1.2.0 seria **aditiva pura**. A implementação
mostrou que não dá, e a promessa foi quebrada em dois pontos. Os dois estão
registrados no próprio contrato; esta seção existe para o ADR parar de afirmar o
contrário.

**1. `distance` sai de `required` em `SearchHit`, e isso NÃO é aditivo.**

O ADR dizia "`distance` **é mantido**", e ele é, como campo. O que não foi visto
na hora é que o contrato 1.1.0 o declara **obrigatório** (`required: [source,
distance]`), e um trecho encontrado apenas por busca léxica não tem distância
nenhuma: BM25 não mede distância. Manter a obrigatoriedade exigiria inventar um
valor, e número inventado num campo que a interface usa para ordenar é pior que a
ausência.

Relaxar `required` é **quebrante para consumidores** que assumam presença, ainda
que inofensivo para produtores. Decidido com o autor, com a mitigação de que o
campo continua sendo emitido sempre que existe: todo trecho que passou pelo
caminho semântico o carrega, em qualquer configuração. `rag-01` e `rag-02` o
emitem em 100 por cento dos hits, e por isso continuam válidos sem alteração,
verificado rodando a suíte do `rag-02` (74 testes verdes) contra o contrato novo.

**2. `timings` ganha QUATRO campos, não três.**

O ADR previa `keyword_s`, `fusion_s` e `rerank_s`. Faltava `dense_s`. Com
`search_s` mantendo o significado de TOTAL do estágio, o caminho denso ficaria sem
campo próprio, e a decomposição não fecharia. O contrato declara os quatro, e
`search_s` ganhou descrição explícita avisando que somar os cinco conta a
recuperação duas vezes.

**3. `GET /health` não ganha o status 409, ao contrário do que a primeira versão
do contrato 1.2.0 chegou a publicar.**

O 409 foi acrescentado ao `/health` por leitura apressada do critério de aceite
10, que fala em "índice ausente devolve 409". O 409 é do `POST /ask`, que é onde
o índice inutilizável impede o trabalho. Saúde **reporta** estado: responde 200
com `status: degraded`, que é o que o código sempre fez e o que `rag-01` e
`rag-02` fazem. O 409 foi removido do contrato e o critério 10 foi reescrito para
nomear a rota.

## Referências

- `../docs/contracts/rag-api.yaml`
- `docs/domains/rag/hld.md`, "Interfaces públicas"
- Precedente direto: ADR-005 do `rag-02-conversacional-citacoes`, que subiu 1.0.0 para 1.1.0
  pelo mesmo método
- [[ADR-003-fusionservice-e-searchhit-com-procedencia]]
