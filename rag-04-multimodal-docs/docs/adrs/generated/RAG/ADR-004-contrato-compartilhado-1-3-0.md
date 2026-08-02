# ADR-004: Contrato compartilhado evoluído para 1.3.0, aditivo, com kind e content_html

- **Status:** aceito
- **Data:** 2026-08-01
- **Domínio:** RAG
- **Decisores:** arthu

## Contexto

O contrato `../docs/contracts/rag-api.yaml` é compartilhado pelos dez projetos e pelo
frontend genérico. O rag-03 o evoluiu para 1.2.0 de forma aditiva (`score`,
`provenance`, com um relaxamento declarado em `distance`). O rag-04 introduz fontes que
não são trechos de texto: uma resposta pode se apoiar numa tabela ou numa imagem, e o
contrato 1.2.0 não tem como dizer isso ao consumidor.

A regra do fluxo (contracts-fit) é que o consumidor nunca implementa rota fora do
contrato publicado, e divergência se reconcilia no contrato primeiro.

## Decisão

**O contrato evolui para 1.3.0 de forma estritamente aditiva.** Três acréscimos, todos
opcionais:

- `SearchHit.kind`: `texto | tabela | imagem`. O frontend passa a saber que tipo de
  fonte sustenta a resposta.
- `SearchHit.content_html`: presente quando `kind=tabela`, carrega o HTML da tabela
  original para o frontend renderizar a tabela de verdade. É a materialização visível
  do multi-vector: o usuário vê que chegou a tabela, não o resumo.
- Resposta do `/ingest` ganha a contagem `elements` por tipo (`textos`, `tabelas`,
  `imagens`), tornando a ingestão observável pelo cliente.

Semântica fixada sem mudança de esquema: quando `kind=tabela`, `excerpt` carrega o
resumo (foi ele que casou com a busca; é curto e exibível); quando `kind=imagem`,
carrega a descrição. `page` vale para os três tipos. `provenance` fica ausente neste
projeto (só há caminho denso; o enum existente já cobre).

Fora do escopo, declarado no contrato: servir o arquivo da imagem. Exigiria rota de
mídia (`GET /figures/{id}`) com preocupações próprias (path traversal, cache, content
negotiation) que não ensinam RAG. Na v1 a imagem participa como descrição textual;
clientes 1.2.0 continuam funcionando sem mudança.

## Alternativas consideradas

### Não evoluir o contrato e embutir o HTML no excerpt

Rejeitada. `excerpt` é definido como trecho para exibição; despejar HTML de tabela nele
quebraria a exibição de todo cliente existente, o oposto de aditivo. E perderia a
distinção de tipo, que é a informação nova real deste projeto.

### Versão nova com quebra (2.0.0), modelando fonte como união discriminada

Rejeitada por custo/benefício. A união discriminada (`TextSource | TableSource |
ImageSource`) é o desenho mais limpo, mas obrigaria os projetos 1 a 3 e o frontend a
migrar sem ganho funcional para eles. `kind` opcional dá a discriminação com
compatibilidade total.

### Servir a imagem já na v1

Rejeitada por escopo, registrada como decisão pendente no HLD. A rota de mídia é
ortogonal ao aprendizado do multi-vector e adiciona superfície de segurança.

## Consequências

**Positivas**

- Clientes 1.2.0 seguem funcionando sem tocar em nada; campos novos são opcionais.
- O frontend pode renderizar a tabela real, tornando o critério de sucesso do projeto
  ("chegou a tabela, não o resumo") visível na interface.
- `elements` dá observabilidade da ingestão ao consumidor, não só ao log do servidor.

**Negativas**

- `content_html` transporta payloads maiores por hit quando a fonte é tabela. Aceito:
  top-k é moderado e o transporte é loopback.
- Mais um degrau de versão para os projetos futuros carregarem (o custo permanente de
  contrato compartilhado, já pago pela trilha em 1.1.0 e 1.2.0).

## Referências

- `../docs/contracts/rag-api.yaml`
- `docs/domains/rag/hld.md`, "Interfaces públicas"
- ADR-005 do rag-03 (precedente de evolução aditiva do mesmo contrato)
