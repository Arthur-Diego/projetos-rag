# ADR-003: `Conversation` como objeto de valor em `domain`, sem `ConversationMemory`

- **Status:** aceito
- **Data:** 2026-07-27
- **Domínio:** RAG
- **Decisores:** arthu
- **Diverge de:** `../docs/guidelines/arquitetura-em-camadas.md`, seção 5

## Contexto

A guideline de arquitetura do workspace é a fonte de verdade estrutural dos dez projetos.
A seção 5 dela, "Como cada projeto estende sem acoplar", antecipa o que cada projeto vai
acrescentar. Para o Projeto 2 ela prevê:

| Projeto | O que acrescenta | Onde |
| --- | --- | --- |
| 2 conversacional | `ConversationMemory`, reescrita de pergunta | `service/`, novo `QueryRewriteService` |

A previsão foi escrita antes de o Projeto 2 existir, e assumia implicitamente que a
memória seria gerenciada em algum lugar. O [[ADR-002-conversa-fora-do-servidor]] decidiu o
contrário: a conversa é do cliente, e chega ao caso de uso como argumento.

Isso esvazia o `ConversationMemory`. Um serviço de memória num backend sem estado não
guarda, não busca e não expira nada. Restaria a ele aplicar a janela de histórico, que é
uma função pura de uma lista para uma lista menor. A própria guideline, seção 4, nomeia
esse resultado: delegação pura é camada vazia.

A guideline também diz, na seção 4, o que fazer quando isso acontece: "cada projeto novo
herda a estrutura e registra em ADR próprio o que precisou mudar". Este é esse ADR.

## Decisão

**Não existe `ConversationMemory`.** A conversa é modelada em `rag/domain/models.py`:

```python
class Turn(NamedTuple):
    question: str
    answer: str

class Conversation(NamedTuple):
    turns: tuple[Turn, ...]

    def last(self, n: int) -> "Conversation":
        """Janela de histórico. Devolve uma conversa nova; não muta esta."""
        return Conversation(self.turns[-n:] if n > 0 else ())
```

A janela é método do objeto de valor, não serviço. É uma operação fechada sobre o tipo:
recebe `Conversation`, devolve `Conversation`, não toca em nada externo. Colocá-la num
serviço exigiria injetar o serviço em quem já tem o dado, sem ganho.

O `QueryRewriteService` **continua** existindo como a guideline prevê, e em `service/`.
Ele tem fronteira externa de verdade (chama o LLM), tem decisão de verdade (reescrever ou
não) e tem implementação substituível. A divergência é sobre `ConversationMemory`, não
sobre a outra metade da linha da tabela.

A seção 5 da guideline **fica como está**, registrando a previsão original. Ela é
histórico do que se planejou, e este ADR é encontrável a partir dela.

## Alternativas consideradas

### Seguir a guideline e criar o `ConversationMemory`

Rejeitada pelo autor. O argumento a favor era a consistência com o documento estrutural da
trilha, e ele não é desprezível: divergir do padrão custa a quem lê depois. O argumento
que prevaleceu é que criar uma camada que a própria guideline classifica como decorativa
para obedecer a outra parte da mesma guideline é obedecer à letra contra o espírito, e
ensinaria o hábito errado.

### Corrigir a seção 5 da guideline para refletir o desfecho

Rejeitada pelo autor. Evitaria que quem lê a guideline primeiro comece por uma previsão que
não se cumpriu. Recusada porque transformaria a guideline num documento a manter a cada
projeto, e porque a previsão original tem valor: ela mostra que a estrutura foi pensada
antes e ajustada quando o caso concreto apareceu, que é como o processo deve funcionar.

### `Conversation` como `frozen dataclass` em vez de `NamedTuple`

Não rejeitada por princípio; escolha de forma. `NamedTuple` segue a seção 6 da guideline
Python ("`NamedTuple` para objetos de valor, `frozen dataclass` quando houver métodos ou
muitos campos"). `Conversation` tem um método, então a regra admite os dois. Fica
`NamedTuple` por simetria com `SearchHit` e `Answer`, e a decisão é barata de reverter.

## Consequências

**Positivas**
- Uma camada a menos, e ela seria vazia.
- A janela de histórico vira testável sem nenhum dublê: uma lista entra, uma lista menor
  sai. O experimento do critério 6 do PRD fica barato de instrumentar.
- Imutabilidade por construção. Aplicar a janela não pode corromper a conversa original,
  o que elimina uma classe inteira de defeito num fluxo que já tem dois estágios de LLM.

**Negativas**
- Divergência do documento estrutural da trilha. Quem ler a guideline e depois o código vai
  encontrar uma diferença, e depende deste ADR para entendê-la.
- Se um projeto futuro precisar de conversa com estado no servidor (persistência, TTL,
  múltiplos usuários), o `ConversationMemory` volta a fazer sentido e este ADR precisará ser
  superado. A condição que o invalidaria é a mesma do [[ADR-002-conversa-fora-do-servidor]].

## Referências

- `../docs/guidelines/arquitetura-em-camadas.md`, seções 4 e 5
- `docs/domains/rag/hld.md`, "Componentes e responsabilidades"
- [[ADR-002-conversa-fora-do-servidor]]
