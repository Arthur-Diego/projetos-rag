# Task Memory: task_06.md

Keep only task-local execution context here. Do not duplicate facts that are obvious from the repository, task file, PRD documents, or git history.

## Objective Snapshot

Medição por classe de alvo + runbook. Entregue: `docs/operations/perguntas.json`
(14 perguntas: 5 tabela, 4 texto, 3 imagem, 2 negativo),
`docs/operations/tabela-medicao.py`, `docs/operations/README.md` com a rodada de
02/08/2026, e `tests/test_medicao.py` (T6.1, T6.2, T6.3 — 20 casos).

## Important Decisions

- **Âncoras de tabela são NÚMEROS, não frases.** A comparação acontece contra o
  HTML reconstruído pelo `hi_res`, cujo OCR erra o texto das células (`RS
  milhdes`, `6leo`) mas preserva os dígitos. Cada âncora foi escolhida para
  existir numa célula e em nenhum parágrafo — assim acerto de classe `tabela` só
  pode ter vindo da tabela. (Exceção descoberta na rodada: T3 tem parágrafo
  redundante arredondado; ver Learnings.)
- **T1 e T2 são a mesma célula em duas formulações, de propósito.** T1 é a forma
  nua do guia. Medir só a formulação boa esconderia o achado do risco 3.
- **`classe=negativo` sob `--sem-geracao` é `None`, não `False`.** Acerto dessa
  classe é a recusa, que exige geração; reportar zero seria reprovar o que não
  foi medido. Sai como `n/a` na tabela.
- **`QueryFacade.retrieve()` virou método público** (`rag/facade/query_facade.py`)
  em vez de a medição alcançar `facade._retrieval` como o rag-03 fazia. Medir só
  a recuperação é uso legítimo; consumidor que precisa furar encapsulamento
  denuncia método faltando.
- Classe desconhecida em `perguntas.json` levanta `ValueError`, não vira acerto
  zero silencioso (erro de digitação em `classe` publicaria número errado).

## Learnings

- **O gargalo do rag-04 é RANKING, não indexação.** Tabela vai de 1/5 (`k=8`)
  para 5/5 (`k=20`), sempre via `content_html`. As tabelas certas ficam em 16º a
  20º. Causa: os nove resumos começam com a mesma abertura (`A tabela
  apresenta...`), e o prefixo comum domina o embedding; e 36 trechos de prosa
  competem com 9 resumos em busca densa.
- **Formulação vale 15 posições**: T1 (nua) → tabela em 18º; T2 (com empresa e
  unidade) → 3º. Mesmo índice, mesma célula.
- **Modo de falha caro pego pela terceira métrica**: T3 respondeu certo sem a
  âncora — o valor veio do parágrafo que arredonda (`US$ 3,8 bilhões`), não da
  célula `3.773`. A seção `RESPOSTA SEM ÂNCORA` do script existe para isso; nem
  acerto nem recusa pegariam.
- **Imagem confirmou o adr-003 na prática**: 3/3 de direção correta, 1/3 de valor
  correto. G1 e G3 trocaram uma barra por outra (as séries `realizado` e `sem
  eventos exclusivos` estão lado a lado na mesma figura).
- Controle negativo (BCB) recusou 2/2 **inclusive com `k=20`**, com 20 trechos
  irrelevantes no contexto.
- `kind[0]` colapsaria `texto` e `tabela` na mesma letra: a sigla do ranking usa
  caixa (`t`/`T`/`i`) e é um dicionário explícito.

## Files / Surfaces

- Criados: `docs/operations/perguntas.json`, `docs/operations/tabela-medicao.py`,
  `docs/operations/README.md`, `tests/test_medicao.py`.
- Alterados: `rag/facade/query_facade.py` (`retrieve()` público), `CLAUDE.md`
  (bloco de estado).
- Evidência da rodada: `ask.py "Qual foi a receita no 3T24?" --k 20` responde
  `R$ 129,582 bilhões [18]`, com `[18]` sendo a tabela p.5 (2964 chars de HTML).

## Errors / Corrections

- Primeira versão do detalhe imprimia `kind[0]`, que confundia texto com tabela;
  corrigido antes da rodada publicada.
- Primeira rodada paga com `k=8` foi descartada: rodou antes da seção `RESPOSTA
  SEM ÂNCORA` existir, e sem ela o caso T3 ficaria invisível. Os números batem
  com a rodada publicada.

## Ready for Next Run

- Pendências registradas no README: multi-representação por tabela (contingência
  do risco 3), resumo com o título da tabela na primeira frase (experimento mais
  barato), `k` default do contrato (4) menor que o que a medição usa, e nenhuma
  pergunta cobrando tabela + gráfico juntos.
- **Fechamento dd-feature não foi executado nesta task**: validar a seção 9 do
  FDD ponta a ponta e rodar `dd-doc-sync` continua pendente para quem fechar o
  ciclo.
