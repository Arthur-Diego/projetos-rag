"""rag-02-conversacional-citacoes.

Pipeline de RAG conversacional com reescrita ciente do histórico e citação
verificável, organizado em camadas conforme
`../docs/guidelines/arquitetura-em-camadas.md`.

O grafo de dependências é estritamente descendente:

    entrypoint -> facade -> service -> repository -> domain
                                                      ^
                                                  exceptions

Nenhuma camada importa outra acima dela. `domain` e `exceptions` são folhas.
"""
