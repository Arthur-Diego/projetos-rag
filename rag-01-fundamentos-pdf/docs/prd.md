# PRD — rag-01-fundamentos-pdf

> Projeto 1 da trilha de estudo descrita em `../README.md`. Documento de produto: o
> porquê e o quê. O como fica no HLD (`docs/domains/rag/hld.md`).

## Problema

RAG é explicado em toda parte e entendido em quase nenhuma. A literatura descreve o
pipeline — carregar, dividir, embedar, buscar, gerar — mas ler a descrição não produz a
intuição de por que cada etapa existe, nem qual parâmetro estraga tudo quando está
errado. Sem ter feito funcionar uma vez, os problemas que os projetos seguintes resolvem
(busca que erra código de erro, pergunta que depende do turno anterior, busca que traz
lixo) são abstratos: não dá para consertar um problema que você nunca viu acontecer.

Existe ainda um problema específico dos corpora disponíveis, tratado em Critérios de
aceite: o modelo já conhece os dois textos do treino, então "respondeu certo" não prova
que o RAG funcionou.

## Usuário

Um único usuário: o autor do projeto, estudando. Não há segundo perfil, não há operação,
não há SLA. Isso é uma restrição deliberada — autenticação, multi-tenancy e deploy estão
fora de escopo por definição.

A API HTTP acrescentada pelo ADR-008 não muda isso: ela escuta em `127.0.0.1`, sem
autenticação, e existe para servir um frontend local do mesmo usuário. Não é um sistema
multiusuário; é a mesma pessoa usando outra interface.

## Objetivo

Ter um RAG **mínimo, funcional e verificável** sobre um PDF próprio, cujo pipeline caiba
inteiro na cabeça — e que sirva de base **conceitual** para os projetos 2 a 10.

"Base conceitual" é uma decisão consciente: o que se leva para o Projeto 2 é o
entendimento, não o código. Cada projeto seguinte é reescrito do zero, e a reescrita é
parte do aprendizado. Não haverá camada de abstração reutilizável — abstrair o pipeline
antes de entendê-lo esconde exatamente aquilo que se quer aprender.

## Escopo

- Ingestão de PDFs de `pdfs/` (hoje: `j-k-rowling-1-harry-potter-e-a-pedra-filosofal.pdf`,
  274 páginas, texto extraível). `pdfs/fora-do-corpus/` **não** é indexado — ver
  Critérios de aceite.
- Chunking com `RecursiveCharacterTextSplitter`, parâmetros visíveis e ajustáveis.
- Embeddings e geração via **OpenAI** (`text-embedding-3-small` + `gpt-4o-mini`).
- Persistência em **Chroma como serviço** (`chromadb/chroma:1.5.9` em container), acessado
  por HTTP na porta 8000.
- Três entrypoints sobre as mesmas facades: `ingest.py` (roda uma vez), `ask.py`
  (roda sempre) e `serve.py` (HTTP).
- Prompt com instrução de escape explícita e preservação de `source` e `page` nos
  metadados.
- **API HTTP** (`serve.py`) implementando o contrato compartilhado, e um frontend
  React genérico no workspace. Acrescentado pelo ADR-008: era fora de escopo no
  texto original, e a exclusão foi revista quando o frontend entrou como objetivo.
  Não acrescenta comportamento de RAG, é superfície sobre as facades existentes.
- Impressão dos chunks recuperados junto da resposta — sem isso não há como diagnosticar
  uma resposta errada, e o diagnóstico é o produto deste projeto.

## Fora de escopo

| Item | Onde entra |
|---|---|
| Memória de conversa e citações `[n]` | Projeto 2 |
| Busca híbrida, BM25, reranking | Projeto 3 |
| Tabelas, imagens, PDF escaneado | Projeto 4 |
| Agente, ciclos, autocorreção | Projeto 5 |
| Avaliação sistemática com RAGAS | Projeto 3 em diante |
| Deploy, autenticação, testes automatizados contra API paga | Nenhum — não é o objetivo |
| Módulo reutilizável entre projetos | Descartado por decisão de escopo |

## Critérios de aceite

1. `python ingest.py` indexa o PDF e reporta quantas páginas viraram quantos chunks.
2. `python ask.py "<pergunta>"` responde a partir do PDF e imprime os chunks usados.
3. **Teste positivo — a resposta veio da busca, não da memória.** O `gpt-4o-mini`
   conhece Harry Potter do treino, então "respondeu certo sobre o enredo" não prova
   nada. As perguntas de verificação devem ser sobre **esta edição em PDF**, não sobre a
   história: em que página aparece determinada passagem, o que está no sumário, a grafia
   exata de um trecho nesta tradução. Se ele acertar isso, veio da recuperação.
4. **Teste negativo — o corpus de controle.** `pdfs/fora-do-corpus/53_1Cor.pdf`
   (Primeira Carta aos Coríntios, tradução *ad experimentum*, 36 páginas) fica
   deliberadamente **fora do índice**. Toda pergunta sobre ele é ausente da busca e
   presente na memória do modelo — o incentivo máximo para alucinar. O sistema tem que
   devolver a frase de escape. Se responder, o grounding falhou, e isso está provado, não
   suspeitado.

   Este é o critério mais importante do projeto. Um RAG que nunca diz "não sei" não é um
   RAG: é um gerador de alucinação com uma etapa de busca decorativa.
5. O experimento de chunking foi feito ao menos uma vez: mesma pergunta com
   `chunk_size` 200, 1000 e 4000, com a diferença observada e anotada.

## Resultado esperado

O pipeline rodando ponta a ponta, e a capacidade de olhar uma resposta errada e dizer se
o problema foi a busca ou a geração. O guia é explícito: quando a resposta vem errada, a
busca quase sempre já tinha trazido lixo — o LLM raramente é o culpado.

## Pré-requisito operacional

Chave da OpenAI com crédito, em `.env` (modelo em `.env.example`). Configure também um
limite de gasto mensal na conta antes do primeiro `ingest.py`. Custo estimado deste
projeto: menos de US$ 0,20.
