# ADR-007: O estágio de resposta recebe a pergunta resolvida, com a literal ao lado

- **Status:** aceito
- **Data:** 2026-07-27
- **Domínio:** RAG
- **Decisores:** arthu
- **Origem:** defeito encontrado na validação do FDD `consulta-ciente-do-historico`

## Contexto

O desenho original, escrito no FDD antes de existir código, dividia o uso da reescrita
assim: a query reescrita ia para a **busca**, e a pergunta original ia para o **prompt de
resposta**, acompanhada do histórico. O raciocínio era que o modelo veria a formulação
literal do usuário e usaria a conversa para interpretá-la, que é o que a cadeia
`history-aware` padrão do LangChain faz.

Na primeira execução com LLM real, a conversa de três turnos falhou:

```
[reescrita: há histórico, reescrita incondicional]
  original: E o que ela faz?
  buscado : O que a capa de invisibilidade faz?
[busca: 4 trecho(s), melhor distância 0.4545]
[RECUSOU: nada no contexto sustentava a resposta]
```

A busca funcionou: o trecho que descreve Harry vestindo a capa e ficando invisível estava
entre os quatro recuperados, verificado à mão. A geração é que recusou.

O diagnóstico levou três hipóteses erradas antes da certa, e vale registrar as três,
porque cada uma parecia óbvia:

1. **"O prompt de resposta está estrito demais."** Refutada: com a pergunta autossuficiente
   e o mesmo contexto, o modelo responde e cita corretamente.
2. **"A recusa no histórico contamina os turnos seguintes."** Refutada por experimento:
   histórico contendo a frase de escape não impede a resposta seguinte.
3. **"O bloco de histórico proíbe demais."** Refutada: reescrever o bloco não mudou o
   resultado.

A causa real: o prompt de resposta recebia `"E o que ela faz?"`. Nada nele dizia a que
"ela" se referia, e a instrução `Nunca complete lacunas do contexto` fazia o resto. **A
reescrita existe exatamente para resolver esse pronome, e usá-la só na busca desfazia
metade do trabalho.**

## Decisão

O `PromptBuilder` recebe a `RewriteDecision` inteira, não uma string, e monta a pergunta
que o modelo vê:

```python
@staticmethod
def format_question(decision: RewriteDecision) -> str:
    if not decision.rewritten:
        return decision.used
    return decision.used + _LITERAL_SUFFIX.format(original=decision.original)
```

Onde o sufixo é:

```
(esta pergunta foi resolvida contra o histórico; o usuário digitou literalmente:
"{original}". Se a pergunta resolvida tiver mudado o assunto do que o usuário
perguntou, responda ao que ele perguntou.)
```

Duas partes, e a segunda não é enfeite:

- **A pergunta resolvida** é o que o modelo responde. Busca e geração passam a perguntar a
  mesma coisa, o que era a incoerência do desenho anterior.
- **A literal do usuário continua visível.** É a mitigação do risco número 1 do FDD: se a
  reescrita derrapar e trocar o assunto, o modelo tem como perceber, porque vê as duas.
  Mandar só a resolvida deixaria uma reescrita ruim invisível para quem responde.

Verificado depois da mudança que a recusa no corpus de controle continua valendo: três
turnos sobre a Primeira Carta aos Coríntios, todos recusados, com a reescrita mantendo o
assunto fora do corpus em vez de puxá-lo para dentro.

## Alternativas consideradas

### Mandar só a pergunta resolvida, sem a literal

Testada e funcional: responde certo e recusa no controle. Rejeitada pelo autor porque
elimina a única chance de o estágio de geração notar uma reescrita ruim. O risco número 1
deste projeto é a reescrita trocar o assunto; abrir mão do sinal que permite detectá-la,
para economizar duas linhas de prompt, é caro pelo lado errado.

### Manter a pergunta original e melhorar o prompt

Rejeitada. É a tentativa de resolver com redação um problema que é de fluxo: nenhuma
instrução faz o modelo saber a que "ela" se refere se o antecedente não estiver no prompt.
Duas tentativas nessa direção falharam antes de o diagnóstico ficar claro.

### Não corrigir e registrar como limitação

Rejeitada pelo autor. Reprovaria o critério de aceite 1 do PRD e tornaria a conversa
multi-turno pouco útil, que é justamente o que o Projeto 2 existe para consertar.

## Consequências

**Positivas**
- O critério 1 do PRD passa: a conversa de três turnos funciona, com citação.
- Busca e geração perguntam a mesma coisa. A incoerência anterior não podia ser notada
  lendo o código, só executando, e agora não existe.
- O estágio de geração ganha um sinal para desconfiar de reescrita ruim.

**Negativas**
- O prompt cresce e fica menos legível quando há reescrita.
- O modelo pode, em tese, responder à pergunta literal em vez da resolvida quando as duas
  divergirem legitimamente. Não observado, mas é o preço de dar a ele a escolha.
- `PromptBuilder.build` mudou de assinatura: recebe `RewriteDecision` em vez de `str`.
  Quem chamava com uma pergunta solta precisa passar a decisão. Só a `QueryFacade` chama.

## Referências

- `docs/domains/rag/features/consulta-ciente-do-historico-fdd.md`, seções 4, 9.1 e 10
- `rag/service/prompt_builder.py::format_question`
- `rag/facade/query_facade.py::ask`
- [[ADR-004-citacao-resolvida-por-referencia-explicita]]
