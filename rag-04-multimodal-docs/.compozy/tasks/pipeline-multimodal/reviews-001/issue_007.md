---
provider: manual
pr:
round: 1
round_created_at: 2026-08-02T20:17:51Z
status: resolved
file: rag-04-multimodal-docs/rag/service/image_description_service.py
line: 94
severity: low
author: claude-code
provider_ref:
---

# Issue 007: Leitura da figura fora do try - arquivo sumido vira excecao crua

## Review Comment

figure.read_bytes() roda na montagem dos prompts, antes do try que traduz falhas da API de visao. Figura apagada/ilegivel entre o roteamento e o enriquecimento levanta FileNotFoundError/OSError sem traducao (500 UNMAPPED, traceback na CLI) depois de os resumos de tabela ja terem sido pagos. Agrava: Path(unit.figure_path or '') no EnrichmentService mascara figure_path=None.

Correcao sugerida: ler/validar os arquivos dentro de try com mensagem propria de I/O, distinta de falha da API de visao.

## Triage

- Decision: `VALID`
- Notes: Confirmado: read_bytes na montagem dos prompts, fora do try. Fix: leitura dentro de bloco com traducao propria de I/O; figure_path None falha claro.
- Resolution: Corrigido: read_bytes movido para dentro de try com traducao propria de OSError (mensagem distingue I/O local de API de visao); EnrichmentService falha claro com PartitionFailedException quando figure_path=None em vez de Path('').
