# ADR-002: A conversa vive no cliente; o backend não guarda sessão

- **Status:** aceito
- **Data:** 2026-07-27
- **Domínio:** RAG
- **Decisores:** arthu

## Contexto

Este é o primeiro projeto da trilha com estado entre interações. O contrato HTTP
compartilhado (`../docs/contracts/rag-api.yaml`) prevê a feature `history` na lista de
capacidades, mas **não diz onde o histórico mora**. Era a única decisão estrutural
genuinamente nova do Projeto 2, e ela determina a assinatura do caso de uso, a
testabilidade e a forma da camada HTTP.

O problema concreto: `POST /ask` é sem estado por natureza do HTTP, e o REPL do terminal é
com estado por natureza do processo. Alguma das duas pontas precisa carregar a conversa, e
a escolha se propaga para tudo.

## Decisão

**O cliente é dono da transcrição. O servidor recebe, usa e esquece.**

- A CLI (`chat.py`) mantém a conversa em memória do processo.
- O frontend mantém a dele no navegador.
- Ambos enviam a transcrição em `options.history` a cada `POST /ask`.
- O servidor não tem dicionário de sessão, cache de conversa nem identificador de cliente.

A **janela de histórico**, porém, é aplicada no servidor: dos turnos recebidos, a
`QueryFacade` usa os N mais recentes. Isso é deliberado e pode parecer contraditório. A
razão: a janela é o objeto do experimento do critério 6 do PRD, e um parâmetro exposto em
`/capabilities` pode ser variado de um lugar só, sem tocar em dois clientes. O cliente
manda tudo o que tem; o servidor decide quanto disso importa.

## Alternativas consideradas

### `conversation_id` com dicionário em memória no servidor

Rejeitada. Era a alternativa mais convencional e cabe no contrato sem esforço
(`conversation_id` é string, e string cabe em `ParameterSpec`). Três custos a derrubaram:

- Estado mutável global no processo do servidor, que cresce sem limite e não tem quem o
  limpe. Num serviço real isso pede TTL, eviction e um teste para cada; aqui seria
  cerimônia sem contrapartida.
- A `QueryFacade` passaria a depender de um repositório de conversa, e a facade deixaria
  de ser função do que recebe. A regra 2.2 da guideline sobreviveria na letra e não no
  espírito.
- O ganho real (payload menor) resolve um problema que não existe: um usuário, em
  `127.0.0.1`.

### Persistir a conversa em SQLite ou no payload do Qdrant

Rejeitada. Contraria o "fora de escopo" explícito do PRD e acrescenta um armazém que o
projeto não precisa para ensinar reescrita e citação. Retomar conversa entre execuções não
é objetivo de aprendizado deste projeto.

### Memória gerenciada por abstração do LangChain

Rejeitada, e é a alternativa mais tentadora, porque o framework oferece pronto. O motivo
da recusa é pedagógico e vale registrar: num projeto cujo produto é o entendimento do
mecanismo, memória implícita gerenciada pelo framework esconde exatamente o que se quer
ver. A pergunta "o que foi parar no prompt de reescrita?" precisa ter resposta olhando
para uma assinatura de função, não para a documentação de uma biblioteca.

## Consequências

**Positivas**
- A `QueryFacade` continua sendo função pura dos seus argumentos. A mesma instância serve
  CLI e HTTP sem nada global, e a regra 2.2 da guideline fica intacta.
- Testar a matriz de recusa vira trivial: construir uma `Conversation` e chamar. Não há
  estado a preparar nem a limpar entre casos, o que importa porque essa matriz é o critério
  4 do PRD e vai ser executada muitas vezes.
- Nada vaza entre requisições. Nada morre no restart, porque nada vivia lá.
- A memória aparece na assinatura do caso de uso, visível.

**Negativas**
- A transcrição trafega inteira a cada turno. Irrelevante em `127.0.0.1` com um usuário, e
  seria a decisão errada com rede real e múltiplos usuários. **É a premissa que sustenta o
  ADR: se ela mudar, este ADR precisa ser revisto, não contornado.**
- O frontend genérico passa a ter responsabilidade de estado. Ele precisa saber que a
  feature `history` significa "guarde a transcrição e a envie de volta", o que é
  conhecimento novo, ainda que declarado no contrato.
- Um cliente malfeito pode mandar histórico inconsistente com o que de fato aconteceu. Sem
  cópia no servidor, não há como detectar. Aceito: um usuário, dois clientes conhecidos.

## Referências

- `docs/domains/rag/hld.md`, "Arquitetura geral" e "Fluxo de requisições e de dados"
- `docs/prd.md`, seção "Usuário" e critério de aceite 6
- [[ADR-003-conversa-como-objeto-de-valor]]
- [[ADR-005-contrato-compartilhado-1-1-0]]
