"""Camada de repositório: tudo que fala com o mundo externo.

São DOIS armazéns neste projeto (ADR-001), e é a novidade estrutural em relação
aos projetos 1 a 3:

- `vector_repository.py` — representações no Chroma (porta 8002), com `doc_id`,
  `kind` e página no metadado. Índice DERIVADO: reconstruível a partir do
  docstore sem rodar `hi_res` de novo.
- `docstore_repository.py` — originais num `LocalFileStore` em `data/docstore/`,
  atrás da interface `BaseStore`. FONTE DE VERDADE dos conteúdos.

Invariante de gravação, do FDD: o original entra no docstore ANTES da
representação no índice, nunca o inverso. A ordem garante que um hit no índice
sempre encontre o original.

Ambos entram na task_03. Este pacote existe desde já porque a estrutura de
camadas é criada inteira (checklist da seção 8 da guideline de arquitetura).
"""
