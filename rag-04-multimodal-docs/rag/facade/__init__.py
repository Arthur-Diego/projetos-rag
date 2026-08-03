"""Camada de facade: casos de uso, um método público por operação.

`IngestionFacade` orquestra partição -> enriquecimento -> indexação dupla;
`QueryFacade` orquestra retrieval -> prompt -> geração. Nenhuma das duas tem
lógica própria, e nenhuma conhece o mundo de fora: nada de `print`, `argparse`
ou vocabulário HTTP aqui (regra 2.2 da guideline). É essa ausência que permite
ao mesmo caso de uso servir a CLI e a API.

Entram nas tasks 03 e 04.
"""
