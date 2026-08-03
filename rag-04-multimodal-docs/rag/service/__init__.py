"""Camada de serviço: uma responsabilidade cada.

O que este projeto acrescenta em relação ao rag-03 (seção 5 da guideline de
arquitetura em camadas): `PartitionService` (hi_res com cache),
`TableSummaryService` e `ImageDescriptionService` — este último atrás do
`Protocol` `ImageDescriptor` (ADR-006), porque um modelo de visão local é a
segunda implementação prevista.

Todos entram nas tasks 03 e 04.
"""
