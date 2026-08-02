---
schema_version: "compozy.tasks/v2"
workflow: pipeline-multimodal
graph:
  nodes:
    - id: task_01
      file: task_01.md
    - id: task_02
      file: task_02.md
    - id: task_03
      file: task_03.md
    - id: task_04
      file: task_04.md
    - id: task_05
      file: task_05.md
    - id: task_06
      file: task_06.md
  edges:
    - from: task_01
      to: task_03
    - from: task_02
      to: task_03
    - from: task_03
      to: task_04
    - from: task_02
      to: task_05
    - from: task_04
      to: task_06
---

# Pipeline Multimodal Task List

| ID | Título | Tipo | Complexidade | Depende de |
|---|---|---|---|---|
| task_01 | Setup nativo, infra local e fundações do projeto | infra | medium | — |
| task_02 | Contrato compartilhado 1.3.0 | docs | low | — |
| task_03 | Pipeline de ingestão de ponta a ponta | backend | high | task_01, task_02 |
| task_04 | Consulta, saúde e presenters | backend | high | task_03 |
| task_05 | Frontend 1.3.0 | frontend | medium | task_02 |
| task_06 | Medição e runbook de operações | test | medium | task_04 |

Fonte: seção 11 (Build Order) do `_techspec.md` (FDD). Etapas 1+3 → task_01;
etapa 2 → task_02; etapas 4 a 7 → task_03; etapas 8 e 9 → task_04; etapa 10 →
task_05; etapa 11 → task_06. Sem `_tests.md`: os casos de teste estão inline em
cada task, derivados da seção 9 do FDD e dos ACs de `_user_stories.md`.
