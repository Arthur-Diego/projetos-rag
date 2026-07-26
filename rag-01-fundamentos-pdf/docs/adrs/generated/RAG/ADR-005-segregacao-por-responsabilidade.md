# ADR-005: Segregação do pipeline em módulos por responsabilidade

- **Status:** aceito
- **Data:** 2026-07-25
- **Domínio:** RAG
- **Decisores:** arthu
- **Supersede:** [[ADR-003-scripts-independentes-sem-modulo-compartilhado]]

## Contexto

O ADR-003 estabeleceu dois scripts independentes, sem módulo compartilhado, com a
justificativa de que abstrair o pipeline antes de entendê-lo esconde o que o projeto
existe para tornar visível.

Com o pipeline implementado e validado, medimos o que de fato foi construído:

| Medida | Valor |
| --- | --- |
| Linhas de código efetivas | 235 (114 em `ingest.py`, 121 em `ask.py`) |
| Funções | 15 |
| Linhas idênticas entre os dois arquivos | 47 |

A análise das 47 linhas duplicadas mostra que elas são **encanamento**, não RAG: `log`,
`erro`, `verificar_chave`, `verificar_chroma`, imports e constantes. As etapas do pipeline
(carga, divisão, armazenamento, recuperação, montagem de prompt, geração) aparecem uma vez
cada, e portanto não constituem duplicação.

Essa medição foi apresentada junto com a recomendação de extrair apenas o encanamento,
mantendo o pipeline legível de ponta a ponta em cada script. O autor optou pela segregação
completa por responsabilidade.

**A razão declarada muda o objetivo do projeto**, e é isso que justifica superseder em vez
de emendar: praticar design arquitetural passa a ser um objetivo do repositório, ao lado
de aprender RAG. Sob o objetivo original (tornar o pipeline visível), o ADR-003 estava
certo. Sob dois objetivos, o trade-off é outro.

## Decisão

Segregar o pipeline em um pacote `rag/` com um módulo por responsabilidade, aplicando:

- **Responsabilidade única**: cada módulo tem uma razão para mudar.
- **Inversão de dependência**: `store`, `loading`, `chunking` e `generation` expõem
  `Protocol`, e as implementações concretas são injetadas.
- **Aberto/fechado**: trocar Chroma por outro armazém é escrever um novo adaptador, sem
  tocar em quem consome.
- **Segregação de interface**: protocolos pequenos, com os métodos que o consumidor usa.

Estrutura:

| Módulo | Responsabilidade | Razão para mudar |
| --- | --- | --- |
| `rag/erros.py` | Hierarquia de exceções do domínio | Surgir uma nova classe de falha |
| `rag/config.py` | Carregar e validar configuração | Mudar parâmetro ou fonte de config |
| `rag/preflight.py` | Verificar pré-condições externas | Mudar o que precisa estar no ar |
| `rag/loading.py` | Documento de entrada para `Document` | Suportar outro formato de arquivo |
| `rag/chunking.py` | `Document` para chunks | Mudar estratégia de divisão |
| `rag/store.py` | Persistir e consultar vetores | Trocar de armazém vetorial |
| `rag/retrieval.py` | Política de recuperação | Mudar `k`, ordenação, filtro |
| `rag/prompting.py` | Montagem do prompt | Mudar instrução ou formato do contexto |
| `rag/generation.py` | Chamada ao modelo de linguagem | Trocar de provedor ou modelo |
| `rag/reporting.py` | Saída e observabilidade | Mudar formato ou destino do diagnóstico |

`ingest.py` e `ask.py` permanecem como **composition roots**: montam as dependências
concretas, orquestram o fluxo e traduzem exceção em código de saída.

**Mudança de contrato interno**: os módulos levantam exceção da hierarquia `ErroDeRag` em
vez de chamar `sys.exit()`. Um módulo que encerra o processo não é reutilizável nem
testável, e manter `sys.exit()` espalhado esvaziaria a segregação. A tradução de exceção
para código de saída acontece exclusivamente nos entrypoints.

O comportamento observável não muda: mesmas mensagens, mesmos códigos de saída, mesma
separação entre stdout e stderr. Os oito critérios de aceite do FDD são reexecutados como
prova, porque refatoração que altera comportamento não é refatoração.

## Alternativas consideradas

### Manter o ADR-003 intacto

Rejeitada pelo autor. Continua sendo a recomendação técnica **se o único objetivo for
aprender RAG**: 235 linhas em dois arquivos legíveis de cima a baixo, sem indireção. O
argumento perde força quando praticar design entra como objetivo.

### Extração cirúrgica: apenas o encanamento em um `comum.py`

Rejeitada pelo autor. Era a recomendação apresentada. Elimina as 47 linhas de duplicação
real, mantém o pipeline visível em um arquivo por estágio temporal, e teria emendado o
ADR-003 em vez de superá-lo, já que o espírito daquele ADR era não abstrair o pipeline.

Fica registrada como o meio-termo que existia, para quem ler este ADR no futuro saber que
a escolha foi entre três opções, não entre duas.

## Consequências

**Positivas**
- Cada responsabilidade tem um lugar óbvio, e mudar uma não obriga a ler as outras.
- Os módulos passam a ser testáveis isoladamente, sem tocar em API paga: um fake de
  `ArmazemVetorial` e um de `Gerador` cobrem o pipeline inteiro.
- A duplicação de 47 linhas desaparece.
- Trocar o armazém vetorial nos projetos seguintes vira escrever um adaptador.
- Serve de exercício de design, que é agora um objetivo declarado do repositório.

**Negativas**
- Dez módulos para 235 linhas, cerca de 24 linhas por módulo. A razão entre estrutura e
  conteúdo é alta.
- O pipeline deixa de ser legível em um arquivo. Entender o fluxo completo passa a exigir
  navegar entre `ingest.py` e quatro ou cinco módulos.
- O `Protocol` de armazém vetorial **esconde as diferenças entre os bancos**, e conhecer
  essas diferenças é objetivo declarado da trilha ("vector store diferente em quase todo
  projeto, parte do objetivo é conhecer vários"). Consequência aceita: ao chegar no
  Projeto 2, comparar Qdrant com Chroma vai exigir ler os adaptadores, não o fluxo.
- Custo de navegação maior para quem lê o repositório pela primeira vez procurando
  entender RAG, que era o público-alvo original.

## Referências

- `docs/domains/rag/hld.md`, seção Componentes e responsabilidades
- `docs/domains/rag/features/pipeline-rag-pdf-fdd.md`, seção 11
- `docs/domains/rag/diagrams/c4/`
- [[ADR-003-scripts-independentes-sem-modulo-compartilhado]] (superado por este)
- [[ADR-001-chroma-como-servico-em-container]]
