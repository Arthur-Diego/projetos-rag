# PRD — rag-02-conversacional-citacoes

> Projeto 2 da trilha de estudo descrita em `../README.md`. Documento de produto: o
> porquê e o quê. O como fica no HLD (`docs/domains/rag/hld.md`).

## Problema

O projeto 1 quebra no segundo turno da conversa, e quebra de um jeito silencioso.

> — Quantos dias de férias eu tenho?
> — 30 dias corridos.
> — **E se eu vender dez?**

A terceira frase, embedada sozinha, produz um vetor sobre *vender coisas*. O retriever
traz lixo, o modelo responde em cima do lixo, e nada na saída indica que a busca falhou.
A correção não é buscar melhor: é **reescrever a pergunta usando o histórico antes de
buscar** — *history-aware retrieval*. É o padrão que mais gente esquece de implementar,
justamente porque a falha não aparece como erro.

Há um segundo problema, independente do primeiro. O projeto 1 imprime os chunks
recuperados ao lado da resposta, mas não amarra **qual afirmação veio de qual trecho**.
Numa resposta de três frases sintetizadas de quatro chunks, "as fontes estão logo abaixo"
não é procedência: é uma lista. Sem `[n]` colado à afirmação, verificar exige reler tudo,
e o que não é barato de verificar não é verificado.

Somados, os dois problemas produzem o caso pior: uma resposta a um follow-up mal
recuperado, apresentada com uma lista de fontes que parece corroborá-la. **Citação
inventada é a alucinação mais perigosa, porque parece verificada.**

## Usuário

Um único usuário: o autor do projeto, estudando. Não há segundo perfil, não há operação,
não há SLA. Autenticação, multi-tenancy e deploy estão fora de escopo por definição.

A API HTTP escuta em `127.0.0.1`, sem autenticação, e existe para servir o frontend local
do mesmo usuário. Não é um sistema multiusuário; é a mesma pessoa usando outra interface.

Consequência que **precisa** ficar registrada, porque este projeto introduz estado: como
há um único usuário, a conversa não exige isolamento entre pessoas. Isso barateia a
decisão de sessão (HLD) — mas é uma simplificação consciente, não um descuido. Um segundo
usuário invalidaria o modelo escolhido.

## Objetivo

Fazer o diálogo de três turnos funcionar, e fazer toda afirmação da resposta carregar uma
citação que se possa abrir e conferir.

O critério não é "a resposta ficou boa". É:

1. A pergunta ambígua vira uma pergunta autossuficiente, e **isso é visível** — a query
   reescrita é impressa ao lado da original.
2. A afirmação carrega `[n]`, e ao abrir a página `n` o trecho **realmente está lá**.

Como no projeto 1, o que se leva para o projeto 3 é o entendimento, não o código. Este
projeto é reescrito do zero sobre a estrutura da guideline de arquitetura em camadas do
workspace — herda a **forma**, não o código do projeto 1.

## Escopo

### Núcleo

- **Reescrita da pergunta com histórico** (`history-aware retrieval`): um prompt que não
  responde nada, só produz uma query de busca autossuficiente resolvendo pronomes e
  referências implícitas. No primeiro turno não há chamada — não se gasta LLM à toa.
- **Citação rastreável**: as fontes chegam ao modelo numeradas, junto do texto e do
  identificador (`fonte`, `página`), e o prompt exige `[n]` ao final de cada afirmação.
  Pedir a referência por número reduz a invenção, porque o modelo copia um rótulo em vez
  de gerar um nome.
- **Memória de conversa** mantida entre turnos, com o histórico alimentando tanto a
  reescrita quanto a geração.
- Ingestão de PDFs normativos de `pdfs/`, chunking, embeddings e geração via **OpenAI**
  (`text-embedding-3-small` + `gpt-4o-mini`).
- Persistência em **Qdrant em container**, acessado por HTTP.

### Interfaces

Paridade com o projeto 1: **CLI conversacional, API HTTP e o frontend genérico do
workspace**. As três superfícies sobre as mesmas facades, conforme a regra 2.2 da
guideline de arquitetura.

A API implementa o contrato compartilhado `../docs/contracts/rag-api.yaml`. O contrato
prevê a feature `history`, mas **não define onde a conversa mora entre requisições** —
essa é a decisão estrutural nova deste projeto e será registrada em ADR (HLD, passo 4).

### Escopo extra, confirmado na entrevista

| Item | Por que entra |
|---|---|
| **Corpus de controle** (`pdfs/fora-do-corpus/`, nunca indexado) | Herda o mecanismo do ADR-004 do projeto 1, com um teste novo — ver critério 4. |
| **Reescrita condicional** | A reescrita custa uma chamada de LLM por turno. Torná-la condicional e **medir** o custo evitado. Vira parâmetro em `/capabilities`. |
| **Janela de histórico** | Conversa longa estoura contexto e piora a reescrita. Vira parâmetro configurável e experimento em branch `exp/`. |
| **Troca de vector store** | Provar que trocar Qdrant por Chroma é uma linha, graças ao `Protocol VectorRepository`. Reforça que o banco não define a qualidade do RAG. |

## Corpus

**Indexado:** texto normativo com remissões cruzadas — CLT ou regulamento jurídico
equivalente. A escolha é deliberada: norma é o gênero em que o follow-up nasce sozinho
("e nesse caso?", "e se for o contrário?", "e se eu vender dez?"), porque as regras se
referem umas às outras. Narrativa não produz isso naturalmente.

**Corpus de controle, fora do índice:** um segundo texto normativo que o `gpt-4o-mini`
conheça bem do treino (Código de Defesa do Consumidor, Constituição, ou equivalente) e
que **nunca** seja indexado. É o incentivo máximo para alucinar: ausente da busca,
presente na memória do modelo, e do mesmo gênero do corpus real — então a pergunta não
"parece" fora de escopo.

## Fora de escopo

| Item | Onde entra |
|---|---|
| Busca híbrida, BM25, reranking | Projeto 3 |
| Tabelas, imagens, PDF escaneado | Projeto 4 |
| Agente, ciclos, autocorreção | Projeto 5 |
| Roteamento multi-fonte, SQL | Projeto 6 |
| Avaliação sistemática com RAGAS | Projeto 3 em diante |
| Persistência da conversa entre execuções do processo | Fora — a menos que o HLD conclua que a API HTTP a exige |
| Múltiplos usuários, autenticação, isolamento de sessão por pessoa | Nenhum — ver Usuário |
| Deploy, testes automatizados contra API paga | Nenhum — não é o objetivo |
| Módulo compartilhado com o `rag-01` | Descartado; herda a guideline, não o código |

## Critérios de aceite

1. **O diálogo de três turnos funciona.** A sequência férias → "e se eu vender dez?"
   devolve resposta correta sobre venda de férias, e não sobre comércio.

2. **A reescrita é visível.** A CLI e a resposta HTTP expõem a query reescrita ao lado da
   pergunta original. Ver a pergunta ambígua virar uma pergunta completa é metade do
   aprendizado deste projeto — se ficar escondida, o projeto ensina menos.

3. **A citação confere.** Toda afirmação vem com `[n]`; abrir a página citada mostra o
   trecho. Conferido **à mão, ao menos cinco vezes** — não por amostragem automática, que
   é justamente o que não existe ainda nesta altura da trilha.

4. **A recusa sobrevive ao histórico.** Pergunta sobre o corpus de controle tem que
   receber a frase de escape — e continuar recebendo depois de um follow-up
   ("e nesse caso?", "mas e o artigo seguinte?"). Este é o critério mais importante e o
   que é **novo** em relação ao projeto 1: o histórico é contexto extra que empurra o
   modelo a responder do que já sabe, e a reescrita pode transformar uma pergunta
   fora-de-corpus numa pergunta que "parece" dentro. Um RAG que recusa no turno 1 e cede
   no turno 3 não recusa: adia.

5. **O custo da reescrita foi medido.** A reescrita condicional foi comparada com a
   reescrita sempre-ligada, com o número de chamadas economizadas anotado, e ao menos um
   caso em que a condição errou (deixou de reescrever algo que precisava) foi registrado.

6. **A janela de histórico foi experimentada.** Mesma conversa com janelas diferentes, com
   a degradação observada e anotada em `exp/`.

7. **A troca de vector store foi feita.** Qdrant → Chroma alterando apenas a linha do
   composition root, com o resultado idêntico registrado. Se exigir mais que isso, a
   fronteira `VectorRepository` vazou e o ADR correspondente precisa dizer por quê.

## Resultado esperado

Uma conversa de vários turnos sobre um texto normativo em que se possa apontar, para cada
frase da resposta, o artigo que a sustenta — e um sistema que não desiste de dizer "não
sei" só porque a conversa ficou longa.

## Pré-requisito operacional

Chave da OpenAI com crédito, em `.env` (modelo em `.env.example`), e limite de gasto
mensal configurado na conta. Custo estimado: abaixo de US$ 0,50 — maior que o do projeto
1, porque a reescrita acrescenta uma chamada por turno (motivo do critério 5).
