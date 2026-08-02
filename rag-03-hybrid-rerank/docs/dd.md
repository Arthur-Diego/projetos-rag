# Configuração do fluxo DD

- board: nenhum

Herdado da decisão de 25/07/2026 tomada no `rag-01-fundamentos-pdf` e mantida no
`rag-02-conversacional-citacoes`: os projetos da trilha não usam Trello. Os workflows
`dd-*` seguem normalmente e apenas anotam no resumo final que não houve card.

O registro do trabalho vive nos próprios documentos: o HLD do domínio, os ADRs em
`docs/adrs/generated/` e os FDDs em `docs/domains/<dominio>/features/`.

## Diferença em relação aos projetos 1 e 2

Este projeto **não tem `docs/prd.md`**. Os dois anteriores têm, por terem nascido antes
de o fluxo DD fixar que não existe PRD de produto: o porquê do projeto é capturado na
entrevista de HLD, e o único PRD do fluxo é o PRD **por feature**, criado dentro do
`dd-feature` em `.compozy/tasks/<slug>/_prd.md`.

Os `docs/prd.md` do rag-01 e do rag-02 ficam onde estão — são registro histórico daqueles
projetos, não modelo a copiar.
