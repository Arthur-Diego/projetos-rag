"""Camada HTTP: serve o contrato compartilhado `../docs/contracts/rag-api.yaml`.

Existe porque o projeto expõe contrato (regra da seção 1 da guideline). O
modelo de injeção aqui é o container do FastAPI, não o `composition.py` da raiz:
container para o que é estável, construção explícita para o que depende do corpo
da requisição (regra 2.5).

`dependencies.py`, `descriptor.py`, `error_handlers.py`, `schemas.py` e
`routes/` entram na task_04, junto das quatro rotas do contrato.
"""
