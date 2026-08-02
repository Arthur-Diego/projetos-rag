# ADR-003: doc_id determinístico por hash de conteúdo, não uuid4

- **Status:** aceito
- **Data:** 2026-08-01
- **Domínio:** RAG
- **Decisores:** arthu

## Contexto

O `doc_id` é a chave que liga as duas metades do índice: o vetor da representação no
Chroma e o original no docstore. O código do guia gera `str(uuid.uuid4())` por
elemento, o que funciona numa ingestão única e descartável, mas cria dois problemas num
projeto onde a ingestão é cara e será repetida durante o desenvolvimento: cada
reingestão gera ids novos e **duplica** o índice inteiro em silêncio, e cada reingestão
**repaga** resumo e embedding de conteúdo que não mudou.

## Decisão

**O `doc_id` é um hash determinístico do conteúdo do elemento** (mais o suficiente de
contexto para desambiguar: origem e tipo). O mesmo elemento produz sempre o mesmo id.

Duas propriedades derivam disso:

1. **Idempotência**: reingerir o mesmo PDF não duplica entradas; escrever sob a mesma
   chave sobrescreve com o mesmo conteúdo.
2. **Economia**: elemento cujo id já existe no docstore não é resumido nem embedado de
   novo. O cache da partição ([[ADR-005-cache-da-particao-bruta]]) economiza o tempo do
   `hi_res`; esta decisão economiza o dinheiro das chamadas pagas.

Consequência de segurança, registrada no HLD: os nomes de arquivo do docstore e das
figuras derivam do `doc_id`, que é gerado pelo próprio sistema. Nenhum nome de arquivo
deriva de conteúdo do PDF nem de entrada do usuário, o que neutraliza path traversal
por construção.

## Alternativas consideradas

### uuid4, como no código do guia

Rejeitada. Aleatório por definição: reingestão duplica o índice e repaga tudo. Serve ao
guia porque o exemplo dele ingere uma vez e joga fora; não serve a um projeto que
declara a iteração sobre a ingestão como parte do trabalho.

### Id sequencial por posição no documento

Rejeitada. Estável só enquanto o documento e o particionador não mudam: uma tabela a
mais detectada (ou uma versão nova do modelo de layout) desloca todos os ids seguintes,
e o índice inteiro desalinha sem aviso. O hash de conteúdo só muda onde o conteúdo mudou.

## Consequências

**Positivas**

- Reingestão vira operação segura e barata, executável quantas vezes o desenvolvimento
  pedir.
- Deduplicação de graça: dois elementos idênticos no corpus colapsam no mesmo id.
- Path traversal neutralizado por construção.

**Negativas**

- Elemento cujo conteúdo mudou vira id novo, e o id antigo fica órfão até o próximo
  reset. Aceitável no corpus fixo da v1; o comando único de reset resolve.
- O hash precisa ser estável entre execuções (mesma serialização do elemento antes de
  hashear), o que é uma responsabilidade de implementação que o uuid4 não tinha.

## Referências

- `docs/domains/rag/hld.md`, "Considerações de escalabilidade" e "Segurança"
- [[ADR-001-dois-armazens-ligados-por-doc-id]]
- [[ADR-005-cache-da-particao-bruta]]
