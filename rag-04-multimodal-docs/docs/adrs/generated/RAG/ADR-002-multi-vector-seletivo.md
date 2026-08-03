# ADR-002: Multi-vector seletivo: texto narrativo indexado direto, resumo só para tabela e imagem

- **Status:** aceito
- **Data:** 2026-08-01
- **Domínio:** RAG
- **Decisores:** arthu

## Contexto

O diagrama do guia manda resumir os três tipos de elemento antes de indexar: texto,
tabela e imagem. Resumir tabela e descrever imagem é o núcleo do projeto, porque essas
representações cruas embedam mal (tabela é número sem contexto; imagem nem tem texto).
Mas resumir texto narrativo é outra conversa: o texto já embeda bem por natureza, e a
pergunta era se ele também deveria passar pelo LLM na ingestão.

## Decisão

**Texto narrativo é indexado direto**: o próprio texto é embedado e é também o seu
"original". **Resumo e descrição ficam reservados a tabelas e imagens**, cujos originais
vão ao docstore.

O critério que a decisão fixa: **resumo é remédio para representação ruim, não pipeline
padrão**. Aplica-se a quem embeda mal (tabela, imagem, e no futuro blocos longos ou
ruidosos como transcrições), não a um tipo de elemento por definição.

## Alternativas consideradas

### Resumir tudo, seguindo o diagrama do guia à risca

Rejeitada. Três custos sem ganho correspondente. Custo direto: uma chamada de LLM por
bloco de texto, dobrando o custo de ingestão e crescendo linearmente com o corpus.
Perda de informação: o embedding do texto original preserva tudo; o resumo preserva o
que o modelo achou importante, e a pergunta específica frequentemente casa com o
detalhe descartado. Superfície de falha: resumo alucinado na ingestão fica congelado no
índice, envenenando todas as buscas futuras sem ninguém olhar para ele de novo. O
diagrama do guia resume tudo por simplicidade expositiva, não por recomendação de
engenharia.

### Indexar a tabela crua, sem resumo

Rejeitada. É exatamente a falha que o projeto existe para demonstrar: o embedding de
uma tabela em HTML é dominado por números e markup, e não casa com pergunta nenhuma em
linguagem natural.

## Consequências

**Positivas**

- Metade do custo de ingestão a menos em corpus dominados por texto, que é o caso comum.
- O índice fica com representação fiel onde a fidelidade funciona, e com representação
  fabricada só onde a original era inutilizável.
- O modelo de dados 1 original para N representações continua aberto: a extensão
  profissional (indexar também perguntas hipotéticas ou a tabela crua além do resumo)
  entra sem migração. É o exercício 2 do guia, deixado como pendência declarada.

**Negativas**

- O índice fica heterogêneo: vetores de textos originais convivendo com vetores de
  resumos. O metadado `kind` existe para isso não virar confusão de diagnóstico.
- Diverge do diagrama do guia, o que pode confundir quem compara o código com o
  material de estudo. Este ADR existe para responder essa pergunta.

## Referências

- `docs/domains/rag/hld.md`, "Fluxo de requisições e de dados"
- `../README.md`, seção "Projeto 4", diagrama e exercício 2
- [[ADR-001-dois-armazens-ligados-por-doc-id]]
