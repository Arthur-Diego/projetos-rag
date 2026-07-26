# ADR-004: Corpus de controle mantido fora do índice

- **Status:** aceito
- **Data:** 2026-07-25
- **Domínio:** RAG
- **Decisores:** arthu

## Contexto

O critério de aceite padrão para um RAG é duplo: perguntas cobertas pelo corpus são
respondidas corretamente, e perguntas não cobertas retornam uma frase de escape em vez de
uma invenção. O segundo é o que separa um sistema de RAG de um gerador de alucinação com
uma etapa de busca decorativa.

Esse critério tem um furo quando o corpus é conhecido do modelo de linguagem a partir dos
dados de treino. É exatamente o caso aqui: o corpus indexado é "Harry Potter e a Pedra
Filosofal", que o `gpt-4o-mini` conhece bem.

A consequência é que **acertar não prova nada**. Se a busca retornar lixo e o modelo
responder corretamente sobre o enredo usando conhecimento próprio, o sistema aparenta
funcionar enquanto a recuperação está quebrada. O teste positivo perde poder
discriminatório justamente na falha que ele deveria detectar.

Trocar o corpus não resolve sozinho. O outro documento disponível, uma tradução de
1 Coríntios, também tem conteúdo amplamente presente no treino.

## Decisão

Adotar **dois corpora com papéis distintos**:

| Papel | Arquivo | Situação no índice |
|---|---|---|
| Corpus indexado | `pdfs/j-k-rowling-1-harry-potter-e-a-pedra-filosofal.pdf` (274 páginas) | indexado |
| Corpus de controle | `pdfs/fora-do-corpus/53_1Cor.pdf` (36 páginas) | **nunca indexado** |

Do arranjo decorrem dois testes complementares:

**Teste negativo.** Toda pergunta sobre 1 Coríntios é, por construção, ausente do índice e
presente na memória do modelo. É o incentivo máximo para alucinar. O sistema tem que
devolver a frase de escape. Se responder, o grounding falhou, e isso está provado, não
suspeitado.

**Teste positivo.** As perguntas de verificação são sobre a **edição em PDF**, não sobre a
história: em que página aparece determinada passagem, o que está no sumário, a grafia exata
de um trecho nesta tradução. Nada disso está no treino do modelo. Acertar implica ter
recuperado.

O mecanismo que sustenta a separação é o glob de `ingest.py`, que é `pdfs/*.pdf` e
**não recursivo**. `pdfs/fora-do-corpus/` fica de fora por construção, não por convenção.

A escolha do documento maior como corpus indexado também é deliberada: 274 páginas geram
cerca de 800 chunks, de modo que uma busca com `k=4` precisa discriminar de verdade. Com
as 36 páginas do outro documento, o top-4 cobriria uma fração grande do corpus e quase
qualquer configuração pareceria funcionar.

## Alternativas consideradas

### Confiar apenas no teste padrão de pergunta fora do assunto

Rejeitada. Perguntar "qual a capital da Mongólia?" e receber a frase de escape prova pouco:
a distância semântica é tão grande que qualquer recuperação, mesmo degradada, tende a
produzir contexto irrelevante o bastante para o modelo recusar. O teste que importa é
aquele em que o modelo **sabe** a resposta e mesmo assim precisa se calar.

### Trocar por um corpus ausente do treino

Rejeitada por ora, mantida como plano de contingência. Um manual de equipamento doméstico
ou uma norma técnica recente eliminaria o problema na origem. Rejeitada porque os PDFs
disponíveis são os que existem, e porque o arranjo de dois corpora resolve o problema e
ainda produz um teste mais informativo do que um corpus desconhecido produziria sozinho.

### Limiar de similaridade como proteção

Rejeitada para este projeto. Descartar chunks abaixo de um score mínimo tornaria o teste
negativo mais fácil de passar, o que é precisamente o motivo de não fazê-lo agora: sentir
o problema sem a proteção é o que dá sentido ao grading do Projeto 5. Registrado no HLD
como plano de contingência, não como desenho atual.

## Consequências

**Positivas**
- O teste negativo passa a ser evidência, não impressão.
- O teste positivo mede recuperação, não memória do modelo.
- O corpus indexado é grande o bastante para que a qualidade da busca importe.

**Negativas**
- Restrição frágil por natureza: trocar o glob de `ingest.py` para `pdfs/**/*.pdf` indexa
  o corpus de controle e destrói o teste **em silêncio**, sem erro nem aviso. Mitigado por
  este ADR, por nota no `CLAUDE.md` e pelo comentário no cabeçalho de `ingest.py`.
- Um PDF ocupa espaço no repositório sem nunca ser indexado, o que parece descuido para
  quem chega sem contexto. Este documento é a explicação.
- As perguntas de verificação positiva exigem consultar o PDF à mão para saber a resposta
  esperada. É trabalho manual, e é o preço de ter um critério confiável.

## Referências

- `docs/prd.md`, critérios de aceite 3 e 4
- `docs/domains/rag/hld.md`, risco "Grounding falso"
- [[ADR-003-scripts-independentes-sem-modulo-compartilhado]]
