# ADR-003: Dois scripts independentes, sem módulo compartilhado

- **Status:** superado por [[ADR-005-segregacao-por-responsabilidade]] em 2026-07-25
- **Data:** 2026-07-25
- **Domínio:** RAG
- **Decisores:** arthu

> **Este ADR não vale mais.** A decisão foi revertida no mesmo dia, depois que o pipeline
> ficou implementado e mediu-se a duplicação real (47 linhas, todas de encanamento). O
> ADR-005 explica o que mudou e por quê. O texto abaixo permanece intacto porque o
> raciocínio continua válido **sob o objetivo original** do projeto, que era exclusivamente
> aprender RAG; o que mudou foi o objetivo, que passou a incluir praticar design.

## Contexto

O objetivo declarado no PRD é ter um RAG mínimo e funcional que "sirva de base para os
próximos projetos". A expressão admite duas leituras incompatíveis, e escolher entre elas
define a forma do código de toda a trilha:

1. **Base conceitual**: o que se leva adiante é o entendimento. Cada projeto seguinte é
   reescrito do zero, e a reescrita faz parte do aprendizado.
2. **Base de código**: um módulo com as peças trocáveis (loader, splitter, store, chain)
   que os Projetos 2 a 7 importam e estendem.

A segunda leitura é a que soa mais profissional, e é por isso que merece exame. Ela implica
projetar uma abstração sobre o pipeline de RAG **antes** de ter entendido o pipeline de
RAG. A abstração precisaria antecipar necessidades que só aparecem nos Projetos 3
(reranking), 5 (ciclos e estado) e 7 (grafo), e abstração projetada sobre requisitos
imaginados costuma precisar ser refeita justamente quando os requisitos reais chegam.

Há um custo mais direto: toda camada colocada entre o autor e o pipeline esconde
exatamente aquilo que o projeto existe para tornar visível.

## Decisão

Manter **dois scripts independentes**, `ingest.py` e `ask.py`, sem módulo compartilhado,
sem pacote e sem camada de configuração comum.

Cada projeto seguinte da trilha começa do zero, copiando ideias e não arquivos.

Consequência aceita e explícita: haverá duplicação entre os sete projetos Python. A
duplicação é o preço, e é considerado justo neste contexto porque o produto da trilha é
entendimento, não software em manutenção.

## Alternativas consideradas

### Módulo reutilizável (`rag/` com loader, splitter, store, chain)

Rejeitada. Permitiria trocar Chroma por Qdrant mudando uma linha, o que é atraente e é a
resposta certa em um sistema real. Aqui, a interface estável que ela criaria esconderia as
diferenças entre os armazéns, e conhecer essas diferenças é um objetivo declarado da
trilha ("vector store diferente em quase todo projeto, parte do objetivo é conhecer
vários"). A abstração entregaria comodidade ao custo do próprio conteúdo do curso.

### Meio-termo: scripts soltos com `settings.py` e `avaliar.py` compartilhados

Rejeitada, com ressalva. O argumento a favor é bom: o que de fato se repete entre os sete
projetos é configuração e medição, não pipeline. Um harness de avaliação reutilizável
tende a se pagar a partir do Projeto 3, quando o Apêndice A (RAGAS) entra em cena e o
experimento passa a exigir comparação sistemática entre configurações.

Rejeitada **para o Projeto 1**, onde não há o que compartilhar ainda. Fica registrada como
decisão a reabrir no Projeto 3, e este ADR deve ser revisitado, não contornado em silêncio.

## Consequências

**Positivas**
- O pipeline inteiro cabe em cerca de 65 linhas legíveis de ponta a ponta, sem indireção.
- Nenhuma abstração projetada sobre requisitos imaginados.
- Cada reescrita nos projetos seguintes é uma repetição deliberada, que consolida o
  aprendizado em vez de pulá-lo.

**Negativas**
- Duplicação entre os sete projetos Python, aceita conscientemente.
- Correção de erro conceitual descoberto no Projeto 4 não se propaga aos anteriores.
- Sem ponto natural para um harness de avaliação compartilhado, que passará a fazer falta
  a partir do Projeto 3. Ver a alternativa de meio-termo acima.

## Referências

- `docs/prd.md`, seção Objetivo
- `docs/domains/rag/hld.md`, seção Padrões adotados
- [[ADR-004-corpus-de-controle-fora-do-indice]]
