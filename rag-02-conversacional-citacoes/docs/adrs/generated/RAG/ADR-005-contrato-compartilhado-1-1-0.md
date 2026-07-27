# ADR-005: Evoluir o contrato compartilhado para 1.1.0 com três campos opcionais

- **Status:** aceito
- **Data:** 2026-07-27
- **Domínio:** RAG
- **Decisores:** arthu

## Contexto

O contrato `../docs/contracts/rag-api.yaml` é compartilhado pelos projetos da trilha, e
existe para que um frontend que o fale converse com qualquer projeto sem conhecer nenhum
deles. O mecanismo de desacoplamento é `GET /capabilities`: o backend descreve os
parâmetros que aceita e o frontend renderiza os controles.

O Projeto 2 produz três informações que o contrato 1.0.0 não tem lugar para:

- a transcrição da conversa, que o cliente precisa **enviar** ([[ADR-002-conversa-fora-do-servidor]]);
- as citações resolvidas ([[ADR-004-citacao-resolvida-por-referencia-explicita]]);
- a pergunta reescrita, que o critério 2 do PRD exige tornar visível.

O contrato traz a própria regra de evolução: **acrescente campos opcionais, nunca altere
os obrigatórios.** E traz um `meta` livre no `Answer`, declarado como "extras do projeto",
que é o esconderijo natural para tudo isso sem mexer em nada.

A pergunta é se essas três informações são extras deste projeto ou parte do contrato.

## Decisão

**São parte do contrato.** Versão 1.1.0, com três acréscimos, todos opcionais:

| Onde | Campo | O quê |
| --- | --- | --- |
| `POST /ask`, dentro de `options` | `history` | Lista de turnos `{question, answer}` já ocorridos |
| `Answer` | `citations` | Lista de `{label, source, page, excerpt}` |
| `Answer` | `rewritten_question` | A query efetivamente buscada, e a decisão que a produziu |

Nenhum campo obrigatório muda. O Projeto 1 continua conforme sem alteração de código: ele
simplesmente não emite os campos novos, e `required` não os inclui.

`features` ganha `history` em uso real. O valor já existia no enum do contrato 1.0.0 sem
nenhum backend que o declarasse; este é o primeiro.

O raciocínio que decide entre contrato e `meta`: **nenhuma das três é idiossincrasia do
Projeto 2.** Citação e conversa são o que os projetos 3 a 10 vão querer — o 3 rerankeia e
precisa dizer de onde veio, o 5 e o 6 têm ciclos e rotas e precisam dizer o que
perguntaram de fato. Um campo em `meta` não pode ser renderizado por um frontend genérico
sem que alguém ensine o frontend caso a caso, e esse ensino caso a caso é exatamente o
acoplamento que o contrato existe para evitar. Esconder em `meta` seria barato agora e
cobrado nove vezes depois.

`meta` continua existindo e continua sendo o lugar certo para o que **é** específico de um
projeto: ciclos do grafo no 5, rota escolhida no 6, saltos no 7.

## Alternativas consideradas

### Tudo em `meta`, sem tocar no contrato

Rejeitada, pelo argumento acima. A favor dela: nenhum bump de versão, nenhum risco de
invalidar o Projeto 1, decisão reversível. Contra, e decisivo: transfere o custo para o
frontend, nove vezes, na forma de conhecimento específico por projeto.

### Contrato 2.0.0, com os campos obrigatórios

Rejeitada. Tornar `citations` obrigatório invalidaria o Projeto 1 e forçaria uma alteração
nele por causa de uma decisão do Projeto 2. O contrato proíbe isso na sua própria regra de
evolução, e a proibição está certa.

### Contrato por projeto, abandonando o compartilhado

Rejeitada. Resolveria a tensão eliminando a restrição, e destruiria o frontend genérico,
que é o ativo que a restrição produz.

## Consequências

**Positivas**
- O frontend genérico passa a renderizar citação e pergunta reescrita para qualquer projeto
  que as emita, sem alteração por projeto.
- A feature `history` do contrato deixa de ser uma promessa e ganha semântica definida:
  o cliente guarda a transcrição e a devolve.
- Os projetos 3 a 10 herdam os campos prontos.

**Negativas**
- Mexe num arquivo compartilhado a partir de um projeto. Exige cuidado para não quebrar o
  Projeto 1, e o cuidado é verificável: se algum campo novo entrar em `required`, quebrou.
- O frontend precisa ser atualizado para exercitar os campos. É trabalho fora do diretório
  do Projeto 2, e entra no escopo da primeira feature.
- `history` viaja dentro de `options`, junto de parâmetros escalares como `k`. Não é
  elegante: `options` foi pensado para `ParameterSpec`, e uma lista de turnos não é
  descritível ali. Alternativa seria promover `history` a campo de primeiro nível do corpo
  de `/ask`. Fica em `options` por compatibilidade com o backend que ignora chaves
  desconhecidas, e a inelegância fica registrada como dívida, não como descuido.

## Referências

- `../docs/contracts/rag-api.yaml`
- `docs/domains/rag/hld.md`, "Interfaces públicas"
- [[ADR-002-conversa-fora-do-servidor]]
- [[ADR-004-citacao-resolvida-por-referencia-explicita]]
