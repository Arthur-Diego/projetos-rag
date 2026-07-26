# ADR-002: OpenAI como provedor de LLM e de embeddings

- **Status:** aceito
- **Data:** 2026-07-25
- **Domínio:** RAG
- **Decisores:** arthu

## Contexto

O pipeline precisa de dois modelos: um de embeddings, que converte chunks e perguntas em
vetores, e um de linguagem, que gera a resposta a partir do contexto recuperado.

A escolha do modelo de **embeddings** é qualitativamente diferente da escolha do modelo de
linguagem, e essa assimetria é o que torna a decisão cara de reverter:

- Trocar o modelo de linguagem é mudar uma linha. O índice não é afetado.
- Trocar o modelo de embeddings **invalida o índice inteiro**. Os vetores de modelos
  distintos vivem em espaços distintos, frequentemente com dimensões distintas
  (`text-embedding-3-small` tem 1536, `nomic-embed-text` tem 768). Não existe migração:
  existe reindexação total.

O modo de falha é pior que o óbvio. Quando as dimensões diferem, o armazém costuma acusar
erro. Quando coincidem por acaso, **nada quebra**: a busca passa a retornar resultados sem
sentido, com scores de aparência normal. O guia da trilha registra isso como o erro nº 2
do Apêndice D.

Verificação do ambiente em 25/07/2026: nenhuma `OPENAI_API_KEY` definida e `ollama` não
instalado. Ou seja, os dois caminhos exigiam configuração; nenhum era o caminho de menor
resistência por já estar pronto.

## Decisão

Usar **OpenAI** para os dois papéis:

- Embeddings: `text-embedding-3-small`, 1536 dimensões.
- Geração: `gpt-4o-mini`, temperatura 0.

A chave vive exclusivamente em `.env`, carregada por `python-dotenv`, com `.env` no
`.gitignore` desde antes do primeiro `git add`. O script falha na primeira linha, com
mensagem explícita, se a chave estiver ausente.

A dimensão 1536 fica registrada aqui e no HLD como parte do contrato do índice. Qualquer
mudança de modelo de embeddings exige novo ADR e reconstrução completa da coleção.

## Alternativas consideradas

### Ollama local (`llama3.1:8b` + `nomic-embed-text`)

Rejeitada. Custo zero e nenhum dado saindo da máquina, o que é uma vantagem real. Rejeitada
por três motivos: cerca de 6 GB de download e consumo relevante de RAM sob WSL 2; qualidade
menor nas tarefas de raciocínio, que é exatamente onde os Projetos 5, 6 e 7 concentram a
dificuldade; e divergência do guia da trilha, que assume OpenAI em todos os exemplos,
obrigando a traduzir mentalmente cada trecho.

O custo estimado da alternativa paga é baixo o suficiente para não justificar essas trocas:
menos de US$ 0,20 neste projeto e entre US$ 3 e 8 na trilha inteira.

### Começar com OpenAI e migrar para Ollama depois

Rejeitada como decisão registrada, mantida como possibilidade. Só funciona se o código
isolar a instanciação dos modelos, e mesmo assim a troca exige reindexar todo o corpus por
causa da mudança de dimensão. Registrar a migração como planejada daria a impressão de que
ela é barata, e ela não é.

## Consequências

**Positivas**
- Zero divergência em relação ao guia da trilha: cada trecho de código roda como está
  escrito.
- Qualidade adequada nas tarefas de raciocínio que os projetos seguintes vão exigir.
- Nada a instalar nem a manter localmente.

**Negativas**
- Custo por uso, e dependência de conexão. Exige limite de gasto configurado na conta,
  feito hoje e não depois.
- O conteúdo dos chunks é enviado a um terceiro a cada consulta. Irrelevante para o corpus
  atual (obra literária e texto bíblico); precisa ser reavaliado se algum corpus futuro
  contiver dado pessoal ou confidencial.
- O índice fica atado à dimensão 1536. Mudar de modelo de embeddings é reconstruir, nunca
  migrar.
- Risco de reindexação repetida durante o experimento de chunking consumir mais crédito
  que o previsto. Mitigado experimentando sobre uma amostra do corpus.

## Referências

- `docs/domains/rag/hld.md`, seções Segurança e Riscos arquiteturais
- `docs/prd.md`, pré-requisito operacional
- `../README.md`, Apêndices C e D
- [[ADR-001-chroma-como-servico-em-container]]
