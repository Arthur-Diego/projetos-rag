# ADR-001: Qdrant como armazém vetorial, em container

- **Status:** aceito
- **Data:** 2026-07-27
- **Domínio:** RAG
- **Decisores:** arthu

## Contexto

O Projeto 1 usa Chroma como serviço em container. O guia da trilha
(`../README.md`, seção "Projeto 2") especifica Qdrant para este projeto, e a razão não é
técnica no sentido usual: **"vector store diferente em quase todo projeto" é objetivo
declarado da trilha**. A escolha não busca o melhor banco; busca a exposição a vários.

Isso cria uma tensão que precisa ficar registrada, porque ela reaparece em todos os
projetos seguintes. A guideline de arquitetura do workspace exige `Protocol` em toda
fronteira externa, e um `VectorRepository` bem feito **esconde** a diferença entre Chroma
e Qdrant. Ou seja: a estrutura que se quer praticar trabalha contra o objetivo pedagógico
de conhecer os bancos. A seção 3 da guideline já reconhece isso e dá a instrução ("ao
comparar dois armazéns, leia os adaptadores, não o fluxo"), mas a instrução só funciona se
alguém a seguir de fato.

## Decisão

Qdrant em container, via `langchain-qdrant` 1.1.0, atrás do `Protocol VectorRepository`.

Duas regras que tornam a decisão verificável em vez de nominal:

1. **Nada do vocabulário do Qdrant atravessa a fronteira.** `payload`, `point_id`,
   `collection_config`, `ScoredPoint` e afins ficam dentro de
   `repository/qdrant_vector_repository.py`. O que sobe é `SearchHit`, com `source`,
   `page`, `distance` e texto.

2. **A troca por Chroma é critério de aceite, não intenção.** O critério 7 do PRD exige
   que trocar o armazém seja uma linha no composition root, e exige que a troca seja
   **feita**. Uma fronteira cuja impermeabilidade nunca foi testada é uma hipótese.

`distance` continua sendo distância, como no Projeto 1 e no contrato compartilhado: menor
é mais próximo. O Qdrant devolve similaridade em algumas configurações; a conversão
acontece no adaptador, e é justamente o tipo de diferença que a leitura do adaptador
revela.

## Alternativas consideradas

### Continuar com Chroma

Rejeitada. Seria mais rápido e reaproveitaria o `docker-compose.yml` do Projeto 1, mas
contraria o objetivo declarado da trilha. O ganho de velocidade num projeto de estudo é o
menos importante dos ganhos.

### Qdrant embarcado, sem container

Rejeitada. O `langchain-qdrant` aceita modo em memória e modo local em disco. Ambos
evitariam o Docker, mas apagariam a distinção entre "o serviço não responde" e "o índice
está vazio", que é um risco registrado no HLD e que o Projeto 1 tratou explicitamente com
o `HealthChecker`. Perder isso para economizar um container é troca ruim.

### Abstrair sobre os dois desde o início, com seleção por configuração

Rejeitada. Colocaria a troca em produção antes de ela ter sido feita uma vez. A ordem
correta é fazer a troca à mão no composition root, sentir o que ela custa, e só então
decidir se vale parametrizar.

## Consequências

**Positivas**
- Exposição a um segundo armazém vetorial, que é o objetivo.
- A fronteira `VectorRepository` ganha um segundo caso real, o que é a única forma
  honesta de saber se ela estava certa.
- Qdrant traz painel web em `localhost:6333/dashboard`, útil para inspecionar a coleção
  sem escrever código.

**Negativas**
- Nenhum código de repositório é reaproveitado do Projeto 1. Consistente com a decisão de
  reescrever cada projeto do zero, mas é trabalho.
- Uma imagem Docker nova, com healthcheck próprio a validar contra a imagem escolhida. O
  healthcheck do Chroma não serve, e um healthcheck que não roda na imagem é pior que
  nenhum, porque dá falsa segurança.

## Referências

- `docs/domains/rag/hld.md`, "Arquitetura geral" e "Fronteira do armazém vetorial vazando"
- `docs/prd.md`, critério de aceite 7
- `../docs/guidelines/arquitetura-em-camadas.md`, seção 3
- [[ADR-003-conversa-como-objeto-de-valor]]
