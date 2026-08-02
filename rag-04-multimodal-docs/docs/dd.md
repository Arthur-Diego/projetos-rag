# Configuração do fluxo DD

- board: nenhum

Herdado da decisão de 25/07/2026 tomada no `rag-01-fundamentos-pdf` e mantida nos
projetos 2 e 3: os projetos da trilha não usam Trello. Os workflows `dd-*` seguem
normalmente e apenas anotam no resumo final que não houve card.

O registro do trabalho vive nos próprios documentos: o HLD do domínio, os ADRs em
`docs/adrs/generated/` e os FDDs em `docs/domains/<dominio>/features/`.

Este projeto também **não tem `docs/prd.md`**, pela mesma regra fixada no rag-03: o
porquê do projeto é capturado na entrevista de HLD, e o único PRD do fluxo é o PRD
**por feature**, criado dentro do `dd-feature` em `.compozy/tasks/<slug>/_prd.md`.
