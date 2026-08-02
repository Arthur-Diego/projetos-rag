# ADR-001: Dois armazéns ligados por doc_id: Chroma em container para representações, LocalFileStore para originais

- **Status:** aceito
- **Data:** 2026-08-01
- **Domínio:** RAG
- **Decisores:** arthu

## Contexto

O padrão multi-vector separa o que se indexa do que se entrega: o resumo de uma tabela
embeda bem e é o que a busca deve encontrar; o HTML íntegro da tabela é o que o LLM
precisa receber. Isso exige dois armazenamentos com papéis diferentes: um vetorial para
as representações e um de chave-valor para os originais, ligados por `doc_id`.

Duas escolhas independentes precisavam ser feitas: onde ficam os vetores e onde ficam os
originais. O guia sugere Chroma embarcado e `InMemoryStore`, e o próprio guia declara o
`InMemoryStore` inaceitável no exercício 1: a ingestão deste projeto custa minutos de
`hi_res` mais chamadas pagas de resumo, e perder tudo no fim do processo torna o
pipeline inutilizável.

## Decisão

**Chroma em container** (`chromadb/chroma:1.5.9`, porta 8002, healthcheck e volume
próprios) para as representações, e **`LocalFileStore` em `data/docstore/`**, atrás da
interface `BaseStore`, para os originais.

O container mantém o padrão dos projetos 1 a 3 (decisão explícita do autor: seguir o
padrão da trilha, não o embarcado do guia). A porta 8002 é a primeira livre: 8000 e
8001 pertencem aos Chroma dos projetos 1 e 2.

Entre as duas metades, **o docstore é a fonte de verdade**: o Chroma é índice derivado,
reconstruível a partir do docstore sem rodar `hi_res` de novo (só re-embedar). Perder o
Chroma custa minutos; perder o docstore custa a ingestão inteira.

## Alternativas consideradas

### InMemoryStore (o ponto de partida do guia)

Rejeitada de saída. Perde os originais ao fim do processo, e a ingestão é cara demais
para ser descartável. O próprio guia manda trocar no exercício 1; aqui a troca acontece
antes de existir código.

### Guardar os originais como metadado no próprio Chroma

Rejeitada, e é a alternativa mais forte: um armazém só, atomicidade de graça, nenhuma
dessincronia possível. Recusada por dois motivos. Originais grandes (HTML de tabela
inteiro) inflam o banco vetorial e degradam operações que não precisam deles. E o
objetivo pedagógico do projeto é aprender o padrão multi-vector com docstore separado,
que é a forma que escala para originais que não cabem em metadado.

### Object storage (S3/MinIO) ou chave-valor dedicado (Redis) para os originais

Rejeitada por escopo. É a resposta certa em produção (durabilidade, concorrência,
transação), mas exigiria um segundo container competindo por atenção e RAM com o
Chroma, contra a regra da trilha de um serviço por projeto. O requisito real aqui é um
só: sobreviver ao restart do processo. `LocalFileStore` atende por inteiro, e a
interface `BaseStore` (`mget`/`mset`) torna a troca futura uma linha na composição.

### Chroma embarcado (sem container)

Rejeitada pelo autor na entrevista de HLD: os projetos 1 a 3 rodam o vector store em
container com healthcheck e volume, e a consistência do padrão vale mais que a
simplicidade do embarcado.

## Consequências

**Positivas**

- Ingestão cara sobrevive a restart; iterar no código não repaga a ingestão.
- Padrão da trilha preservado: compose com healthcheck, volume descartável, um serviço
  por projeto.
- A troca do docstore por object storage em produção é localizada (interface `BaseStore`).

**Negativas**

- O índice tem duas metades que precisam andar juntas: apagar uma sem a outra deixa
  `doc_id` órfão ou original inalcançável. Mitigado pelo `/health` (denuncia contagens
  divergentes) e pelo comando único de reset. Modo de falha novo na trilha, documentado
  no HLD como risco 4.
- Um container a mais rodando; a máquina já hospeda os serviços dos projetos anteriores.
  Regra herdada: subir um serviço por vez.

## Referências

- `docs/domains/rag/hld.md`, "Arquitetura geral" e "Modelo de dados"
- `../README.md`, seção "Projeto 4", exercício 1
- [[ADR-003-doc-id-deterministico]]
- [[ADR-005-cache-da-particao-bruta]]
