"""Pipeline RAG multimodal: partição hi_res, multi-vector e dois armazéns.

A estrutura de camadas segue `../docs/guidelines/arquitetura-em-camadas.md`:
`api/ -> facade/ -> service/ -> repository/ -> domain/`, com `presenter/` para
saída. `domain` e `exceptions` são folhas.
"""
