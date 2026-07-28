# ADR-004: Cross encoder local atrás de `Protocol`, com Cohere prevista como segunda implementação

- **Status:** aceito
- **Data:** 2026-07-28
- **Domínio:** RAG
- **Decisores:** arthu

## Contexto

O último estágio do funil reordena os candidatos fundidos com um **cross encoder**. A
distinção que justifica o estágio:

- **Bi encoder** (a busca): embeda pergunta e documento **separadamente** e compara os dois
  vetores. Rápido, escala para milhões de documentos, menos preciso. É o que a busca densa
  faz.
- **Cross encoder** (o rerank): processa pergunta e documento **juntos**, numa passada pela
  rede. Lento, não escala, muito mais preciso.

Daí o formato de funil: o bi encoder escolhe 20 entre dezenas de milhares, o cross encoder
escolhe 4 entre 20. Rodar o cross encoder sobre o corpus inteiro seria inviável; rodá lo
sobre 20 candidatos é barato.

Existem duas formas de obter o cross encoder: um modelo local via `sentence-transformers`,
ou uma API de rerank hospedada, sendo a da Cohere a mais conhecida. O exercício 2 do guia
pede explicitamente a comparação entre as duas em qualidade, latência e custo.

## Decisão

**A implementação é local:** `cross-encoder/ms-marco-MiniLM-L-6-v2`, executado na CPU via
`sentence-transformers` 5.6.1.

**O `RerankService` é `Protocol`**, com essa implementação como a concreta. A guideline do
workspace já o nomeia assim na seção 5, e o `Protocol` existe por um motivo datado: a API da
Cohere entra depois como **segunda implementação**, trocada por configuração, sem reescrita
de nada acima dela. É o exercício 2 do guia, e ele deixa de ser reescrita para virar um
arquivo novo em `service/` mais uma linha na composition root.

O modelo é carregado **uma vez por processo**, nunca por consulta.

## Alternativas consideradas

### API de rerank da Cohere como implementação primária

Rejeitada. Não exige download de 500 MB, não consome CPU local e a qualidade é
reconhecidamente alta.

Recusada por três motivos. O guia é explícito ao dizer que o reranker deste projeto roda
local e não gasta API, e essa é uma propriedade pedagógica: mostra que nem toda melhoria de
RAG custa chamada paga. Acrescentaria um segundo fornecedor pago e uma segunda chave a
gerir, num projeto cujo custo total até aqui ficou abaixo de um dólar. E introduziria
latência de rede em todo turno, contaminando exatamente a medição de latência por estágio
que o exercício 3 pede.

### Implementar as duas desde o início, escolhidas por configuração

Rejeitada. Entregaria a comparação do exercício 2 junto com a tabela de medição principal.
Recusada por dobrar o escopo da primeira feature sem necessidade: o `Protocol` já garante
que a segunda implementação caiba depois sem custo de reescrita, então antecipar só antecipa
trabalho.

### Não usar `Protocol`, instanciar o cross encoder direto no `RetrievalService`

Rejeitada. Acoplaria o serviço de política a `sentence-transformers` e a `torch`, tornando
qualquer teste do funil dependente de carregar meio gigabyte de modelo. A guideline exige
inversão nas fronteiras externas, e um modelo de meio giga é fronteira externa mesmo rodando
no mesmo processo.

## Consequências

**Positivas**

- Custo zero de API no estágio de rerank, que é o estágio que mais melhora a qualidade.
- **Reduz superfície de dados.** Nenhum trecho do corpus sai da máquina no rerank. É
  consequência colateral da escolha, e vale registrá la porque vira argumento real caso o
  corpus um dia seja sensível.
- O exercício 2 fica preparado, não prometido: falta uma implementação, não um refactor.
- O funil inteiro é testável com um dublê de `RerankService`, sem carregar modelo.

**Negativas**

- Cerca de 500 MB de download (modelo mais `torch`) na primeira execução, sem progresso
  óbvio. A primeira execução parece travada. Mitigado por aviso explícito no primeiro
  carregamento e por nota nas notas de ambiente do `CLAUDE.md`.
- Latência de CPU proporcional ao número de candidatos. Pontuar 50 pares custa mais que o
  dobro de 20, por causa da carga. Mitigado por `candidates` ser parâmetro exposto e por
  `rerank_s` ser medido em separado, de modo que o custo seja visível e atribuível em vez de
  sentido.
- O projeto passa a depender de `torch`, que é a maior dependência da trilha até aqui.

## Referências

- `docs/domains/rag/hld.md`, "Componentes e responsabilidades" e "Riscos arquiteturais"
- `../docs/guidelines/arquitetura-em-camadas.md`, seção 5
- `../README.md`, seção "Projeto 3", subseção "O núcleo, reranking", e exercício 2
- `docs/guidelines/README.md`, "Stack confirmada"
