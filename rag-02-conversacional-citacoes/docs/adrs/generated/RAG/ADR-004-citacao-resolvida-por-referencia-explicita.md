# ADR-004: A citação `[n]` é resolvida por referência explícita, não pela posição em `hits`

- **Status:** aceito
- **Data:** 2026-07-27
- **Domínio:** RAG
- **Decisores:** arthu

## Contexto

O prompt de resposta numera os trechos recuperados de 1 a k e exige que o modelo cite
`[n]` ao final de cada afirmação. Alguém precisa transformar esse rótulo numa referência
que o leitor possa abrir e conferir.

O caminho barato é implícito: `[3]` é o terceiro item de `hits`. Nenhum campo novo, nenhum
código de resolução, e funciona na primeira execução.

Ele falha do pior jeito possível. Qualquer coisa que altere a ordem ou a composição de
`hits` entre a montagem do prompt e a serialização da resposta — deduplicação de trechos
sobrepostos, reordenação por página para exibição, filtro por distância mínima, corte de
um trecho vazio — faz `[3]` apontar para outro trecho. **Sem erro, sem log, sem sintoma.**
A resposta continua bem formada, a citação continua presente, e ela passou a mentir.

Isso não é um risco genérico de engenharia: é exatamente a falha que o Projeto 2 existe
para eliminar. O PRD diz, no problema e no critério 3, que citação inventada é a
alucinação mais perigosa porque parece verificada. Um acoplamento posicional produz
citação inventada por construção, com a agravante de que a culpa não é do modelo, e
portanto nenhuma melhoria de prompt a corrige.

## Decisão

A `Answer` carrega **citações explícitas**. Cada citação liga o rótulo emitido pelo modelo
ao trecho que o sustenta, e a ligação não depende de posição em nenhuma lista.

```python
class Citation(NamedTuple):
    label: int          # o n que apareceu como [n] no texto
    source: str
    page: int
    excerpt: str
```

Um `CitationResolver` isolado faz o parsing dos rótulos presentes no texto gerado e os
resolve contra os trechos que foram efetivamente numerados no prompt. Concentrar isso num
componente só é parte da decisão: parsing espalhado é parsing que diverge.

Três regras de validação, e elas são o conteúdo real do ADR:

1. **Rótulo citado que não existe entre os numerados é sinalizado, nunca silenciado.** O
   modelo citar `[7]` quando só houve quatro trechos é o caso fácil, e o sistema tem que
   dizer.
2. **Recusa não tem citação.** Se `refused` for verdadeiro e houver citação, há defeito. A
   invariante está no HLD, no modelo de dados, e é verificável em teste.
3. **A numeração do prompt e a das citações vêm da mesma fonte.** O `PromptBuilder` numera
   e o `CitationResolver` resolve contra aquela numeração, não contra `hits` reconstruído
   depois.

`hits` continua na resposta, com o mesmo significado que tem no Projeto 1: os trechos
recuperados, para diagnóstico da busca. Ele responde "o retriever trouxe o quê"; as
citações respondem "esta frase veio de onde". São perguntas diferentes, e o Projeto 1 só
conseguia responder a primeira.

## Alternativas consideradas

### `[n]` como índice de `hits`

Rejeitada, pelo motivo desenvolvido no Contexto. Vale registrar que ela é mais barata hoje
e que o custo aparece depois, na forma de um defeito silencioso e difícil de atribuir.

### Pedir ao modelo que cite pelo nome do arquivo e página

Rejeitada. Elimina a indireção, mas troca copiar um rótulo curto por gerar um
identificador, que é justamente onde o modelo alucina. A observação está no guia da trilha
e é o motivo de numerar: o modelo copia melhor do que inventa.

### Exigir citação estruturada via saída em JSON

Rejeitada por ora. Pedir ao modelo um objeto com `claim` e `source_id` daria ligação forte
sem parsing de texto. Custa saída estruturada e mais tokens, e afasta a resposta do formato
legível que o REPL exibe. Fica registrada como caminho natural se a taxa de citação
incorreta for alta: é uma escalada disponível, não um caminho fechado.

## Consequências

**Positivas**
- A citação sobrevive a qualquer transformação de `hits`. Dedup e reordenação passam a ser
  decisões de apresentação, sem consequência para a procedência.
- Rótulo inventado vira sintoma visível em vez de referência silenciosamente errada.
- A conferência manual do critério 3 do PRD fica direta: a citação já traz `source` e
  `page`.
- O frontend genérico pode renderizar citação sem conhecer o projeto, porque o campo está
  no contrato compartilhado (ver [[ADR-005-contrato-compartilhado-1-1-0]]).

**Negativas**
- Um componente e um tipo de domínio a mais.
- Parsing de texto gerado por modelo, que é frágil por natureza. Mitigado por concentrá-lo
  num lugar e por sinalizar o que não resolver, em vez de engolir.
- O modelo pode escrever uma afirmação sem citar nada. A decisão não resolve isso; ela
  garante que o que **for** citado seja resolvível. Detectar afirmação sem procedência é
  problema de avaliação, e avaliação entra no Projeto 3 em diante.

## Referências

- `docs/prd.md`, problema e critério de aceite 3
- `docs/domains/rag/hld.md`, "Citação inventada ou mal resolvida"
- [[ADR-005-contrato-compartilhado-1-1-0]]
