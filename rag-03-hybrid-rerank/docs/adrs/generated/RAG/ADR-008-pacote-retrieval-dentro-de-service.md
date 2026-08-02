# ADR-008: O funil de recuperação mora em um pacote próprio dentro de `service/`

- **Status:** aceito
- **Data:** 2026-07-28
- **Domínio:** RAG
- **Decisores:** arthu
- **Diverge de:** `../docs/guidelines/arquitetura-em-camadas.md`, seção 6

## Contexto

A seção 6 da guideline do workspace descreve a instanciação em Python com
`service/` **plano**: um arquivo por serviço, sem subpacotes. Foi assim nos
Projetos 1 e 2, e funcionou, porque `service/` tinha poucos arquivos e todos
mudavam junto.

Este projeto acrescentou três serviços (`RetrievalService`, `FusionService`,
`RerankService`) e `service/` passou a ter oito arquivos planos. O problema não é
a contagem: é que os oito **não são iguais em natureza**.

A observação que motivou esta decisão, e ela é do autor: olhando a trilha de dez
projetos, **a recuperação é praticamente a única coisa que muda de um projeto
para o outro.** Ingestão, montagem de prompt, geração e resolução de citação são
quase idênticas nos dez. A recuperação não:

| Projeto | O que a recuperação vira |
| --- | --- |
| 1 fundamentos | kNN denso puro |
| 3 híbrido (este) | funil denso + BM25, fusão RRF, reordenação |
| 4 multimodal | multi-vector: indexa resumo, devolve original |
| 5 agêntico | grafo de estado decide e refaz a busca |
| 6 roteador | escolhe entre vetorial e SQL |
| 7 GraphRAG | consulta a grafo de conhecimento |

Com `service/` plano, a resposta para "o que este projeto faz de diferente?"
exige garimpar três arquivos entre oito irmãos que não mudaram.

## Decisão

**Os três serviços do funil moram em `rag/service/retrieval/`**, com um
`__init__.py` que explica por que o pacote existe.

```
rag/service/
├── retrieval/                  o que muda de projeto para projeto
│   ├── retrieval_service.py    orquestra o funil, dono da política
│   ├── fusion_service.py       funde por posição, função pura
│   └── rerank_service.py       reordena por precisão, Protocol
├── chunking_service.py         igual nos dez projetos
├── citation_resolver.py
├── generation_service.py
├── health_checker.py
├── prompt_builder.py
└── query_rewrite_service.py
```

**A fronteira, e ela é o ponto delicado desta decisão.**

Entra em `retrieval/` o que decide **o que chega ao modelo**. Fica fora tudo o
mais, mesmo terminando em `_service`.

Em particular, **`query_rewrite_service` NÃO entra**, apesar do sufixo e da
aparência de vizinho. Ele é o estágio da **pergunta**, não o da recuperação: o
funil recebe uma query já resolvida e nunca vê a conversa. Essa separação é do
Projeto 2 e está registrada lá; trazê-lo para cá faria a política de reescrita
ter dois donos, e é exatamente o tipo de agrupamento por semelhança de nome que
produz pastas sem critério.

**Os repositórios continuam em `repository/`.** A fronteira deles é de camada,
não de assunto: eles adaptam o motor de busca, e um `retrieval/` que os
engolisse estaria misturando o eixo "qual camada" com o eixo "qual assunto".

## Alternativas consideradas

### Manter `service/` plano, como a guideline prescreve

Rejeitada pelo autor. É a opção que não exige ADR nenhum, e a consistência com os
Projetos 1 e 2 tem valor real para quem lê os três em sequência.

Recusada porque o custo aparece justamente na leitura comparada: quem abrir o
Projeto 3 depois do 2 quer saber o que mudou, e a resposta some entre arquivos
que não mudaram. A guideline foi escrita quando `service/` tinha quatro arquivos
homogêneos; a condição que a justificava deixou de valer.

### Agrupar todas as camadas por assunto, e não só esta

Rejeitada. Seria coerente levar a ideia até o fim: `ingestion/`, `answering/`,
`retrieval/`, cada um com seus serviços.

Recusada por não haver evidência de que ajude. `retrieval/` se justifica por um
fato observável, que é variar a cada projeto da trilha; os outros agrupamentos
seriam simetria pela simetria. Estrutura criada por simetria e não por
necessidade é a que apodrece primeiro, e a seção 4 da própria guideline avisa
sobre isso ao proibir `Helper` e `Util`.

### Promover o funil a uma camada própria, irmã de `service/`

Rejeitada. Seria a leitura de que recuperação é um conceito de primeira classe,
merecendo `rag/retrieval/` ao lado de `rag/service/`.

Recusada porque quebraria a regra de dependência descendente que organiza o
projeto inteiro: os três continuam sendo serviços, chamados pela facade e
chamando repositórios. Uma camada nova exigiria responder onde ela entra no grafo,
e a resposta seria "no mesmo lugar que `service/`", que é o sinal de que ela não é
uma camada.

## Consequências

**Positivas**

- "O que este projeto faz de diferente?" vira um diretório, e o `__init__.py`
  responde em prosa.
- O acoplamento fica visível: os três se importam entre si e quase nada mais
  importa deles, o que é a definição de um módulo bem recortado.
- Os projetos seguintes da trilha herdam um lugar óbvio para a substituição
  deles, em vez de decidir de novo a cada vez.

**Negativas**

- Divergência do documento estrutural da trilha, a segunda deste projeto depois
  do [[ADR-003-fusionservice-e-searchhit-com-procedencia]]. Quem ler a guideline e
  depois o código encontra uma pasta que ela não previu, e depende deste ADR.
- Um nível a mais de import (`from ...domain.models` dentro do pacote). Custo
  cosmético, pago uma vez.
- Cria precedente para subpacotes em `service/`. O critério de admissão está
  escrito acima e é estreito de propósito: varia por projeto **e** decide o que
  chega ao modelo. Semelhança de sufixo não basta.

## Referências

- `../docs/guidelines/arquitetura-em-camadas.md`, seções 4, 5 e 6
- `rag/service/retrieval/__init__.py`, que carrega a justificativa junto do código
- [[ADR-003-fusionservice-e-searchhit-com-procedencia]]
