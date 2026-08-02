# ADR-008: `content_html` só com HTML estrutural

## Status

Aceito (2026-08-02, pós-implementação; refina ADR-002 e ADR-004)

## Contexto

O `hi_res` pode detectar uma tabela sem conseguir estruturá-la: o modelo de
layout marca a região, o Table Transformer não devolve `text_as_html`. O
roteamento preserva a unidade usando `element.text` como fallback (perder a
tabela inteira seria pior), mas esse conteúdo é texto plano — a "sopa de
números" dos projetos 1 a 3. O contrato 1.3.0 define `content_html` como "o
HTML da tabela ORIGINAL"; publicar texto plano nele faria o frontend renderizar
sopa de números como se fosse tabela estruturada (rodada de revisão 001, issue
008).

## Decisão

A promessa "hit `kind=tabela` carrega `content_html`" passa a ser "hit
`kind=tabela` E com HTML estrutural carrega `content_html`". A unidade ganha a
marca `content_is_html` (calculada no roteamento: `text_as_html` presente e não
vazio), persistida no docstore; a consulta só publica `content_html` quando a
marca é verdadeira. Sem ela, o hit degrada para `excerpt` — o mesmo caminho de
degradação que o frontend já trata para `content_html` ausente (EC-3 da
US-010). Registros gravados antes do campo existir releem como `true`: o
comportamento de uma ingestão já paga não muda na releitura.

## Alternativas consideradas

### Descartar a tabela não estruturada

- Rejeitada: o resumo em linguagem natural ainda torna o conteúdo buscável;
  descartar apagaria informação recuperável para proteger um campo.

### Publicar o texto plano em `content_html` mesmo assim

- Rejeitada: viola a definição do campo no contrato e transfere ao consumidor a
  tarefa de adivinhar se o "HTML" tem estrutura.

### Detectar estrutura no frontend (heurística no cliente)

- Rejeitada: a informação de origem ("o Table Transformer estruturou?") existe
  no produtor; recalculá-la por heurística no consumidor é fragilidade gratuita.

## Consequências

- Positivas: `content_html` volta a significar exatamente o que o contrato diz;
  a inspeção pós-partição (`inspeciona-tabelas.py`) já marca essas unidades
  como suspeitas, fechando o ciclo operacional do risco 1.
- Negativas: um campo a mais no modelo persistido (`content_is_html`), com
  default de compatibilidade na releitura.

## Referências

- FDD, seções 4 e 5; contrato `docs/contracts/rag-api.yaml` (`content_html`)
- `rag/domain/models.py`, `rag/service/routing_service.py`, `rag/service/retrieval/retrieval_service.py`
- Rodada de revisão `.compozy/tasks/pipeline-multimodal/reviews-001/issue_008.md`
