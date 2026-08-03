# Runbooks

Scripts que produziram a evidência de validação e podem ser rodados de novo.
Cada um diz no cabeçalho se gasta chamada paga.

## Pré-requisitos

```bash
docker compose up -d chroma                    # sobe o Chroma na 8002
curl localhost:8002/api/v2/heartbeat           # {"nanosecond heartbeat": ...}
.venv/bin/python ingest.py                     # GASTA API na PRIMEIRA vez
```

A ingestão é idempotente (ADR-003): com o corpus inalterado ela reporta zero
unidades novas e não repaga nada. Confira antes de medir:

```bash
curl -s localhost:8080/health                  # com o serve.py no ar
```

## Os três scripts, e o que cada um custa

| Script | Custa API? | Para quê |
|---|---|---|
| `inspeciona-tabelas.py` | **não** (só CPU) | ver o que o `hi_res` detectou como tabela, ANTES de gastar |
| `tabela-medicao.py --sem-geracao` | uma embedagem por pergunta | acerto de recuperação por classe |
| `tabela-medicao.py` | + uma geração por pergunta | acima, mais taxa de recusa e julgamento qualitativo |
| `../../reset.py` | não, mas **custa depois** | zera os dois armazéns; a próxima ingestão repaga tudo |

### `inspeciona-tabelas.py` — a mitigação do risco 1, antes do dinheiro

**Não faz uma única chamada de API.** Lê o cache de partição de `data/partition/`
(ADR-005) ou particiona localmente, e lista o que virou tabela, com página e
preview do HTML. Tabela detectada mas não estruturada (HTML sem `<td>`) sai
marcada como suspeita.

```bash
.venv/bin/python docs/operations/inspeciona-tabelas.py
.venv/bin/python docs/operations/inspeciona-tabelas.py --preview 400
```

Rode-o **antes da primeira ingestão de um corpus novo**. O modo de falha que ele
existe para tornar visível é o pior de todos: o `hi_res` conclui sem erro, não
detecta tabela nenhuma, a ingestão resume só textos, tudo "funciona" — e a
conclusão do projeto vira "multi-vector não ajudou" quando a verdade é que nunca
houve tabela no índice. Listagem vazia com `PARTITION_STRATEGY=fast` não diz
nada: o `fast` não detecta tabela por construção.

### `tabela-medicao.py` — o entregável do projeto

**GASTA API.** 14 perguntas em quatro classes de alvo.

```bash
.venv/bin/python docs/operations/tabela-medicao.py --sem-geracao     # só recuperação
.venv/bin/python docs/operations/tabela-medicao.py --k 8             # + recusa e qualitativo
.venv/bin/python docs/operations/tabela-medicao.py --k 20
```

As perguntas e as âncoras vivem em `perguntas.json`, separadas por **classe de
alvo** — `tabela`, `texto`, `imagem`, `negativo` —, porque as três primeiras têm
promessas diferentes (adr-003) e uma nota única as mistura até virar ruído.

As âncoras foram extraídas do PDF com `pypdf`, **nunca pelo `unstructured` do
sistema medido**: usar a recuperação para descobrir o que a recuperação deveria
achar tornaria a medição circular, e o sistema acertaria por definição. A regra é
herdada do rag-03, e um teste da suíte (`tests/test_medicao.py`) reabre o PDF pelo
caminho independente e cobra que cada âncora esteja lá.

Âncora é **trecho literal**, nunca página — a correção de 28/07 do rag-03: acerto
por página conta como sucesso um trecho vizinho que não responde nada.

### `reset.py` — zera os dois armazéns

```bash
.venv/bin/python reset.py
```

Não gasta API, mas **custa dinheiro depois**: preserva o cache de partição
(ADR-005), então o `hi_res` não é repago, mas desfaz a idempotência do ADR-003 e
a próxima ingestão paga de novo um resumo por tabela e uma descrição por imagem.
Use quando a dessincronia denunciada pelo `/health` não tiver conserto local.

---

## Resultado da primeira rodada (02/08/2026)

Corpus: **Relatório de Desempenho Petrobras 3T24**, 19 páginas, 50 unidades
indexadas (36 textos, 9 tabelas, 5 imagens). `text-embedding-3-small`,
`gpt-4o-mini`, `PARTITION_STRATEGY=hi_res`. Acerto por âncora literal em algum hit
recuperado; para tabela, também dentro do `content_html`.

| | k=8 | k=20 |
|---|---|---|
| **Tabela (5)** | **1/5** | **5/5** |
| Texto (4) | 4/4 | 4/4 |
| Imagem (3) — recuperação | 3/3 | 3/3 |
| Controle negativo (2) — recusou | 2/2 | 2/2 |
| **Âncora no `content_html` (5)** | **1/5** | **5/5** |
| Recusas em tabela (5) | 3/5 | 0/5 |
| Recusas em texto/imagem (7) | 0/7 | 0/7 |
| Latência média | 1,49 s | 1,42 s |

### O critério do guia passou, e o HTML é que respondeu

```
$ .venv/bin/python ask.py "Qual foi a receita no 3T24?" --k 20

A receita de vendas no 3T24 foi de R$ 129,582 bilhões [18].

[contexto] 20 trecho(s), 3 tabela(s) em HTML, 20908 caractere(s) enviados ao modelo
  18. [tabela] petrobras-desempenho-3t24.pdf p.5 | similaridade 0.3808 | HTML de 2964 caractere(s)
```

O número `129.582` existe numa **célula** da Tabela 1 e em nenhum parágrafo do
relatório. A citação `[18]` é a tabela em HTML íntegro, resolvida no docstore. É
exatamente a limitação que o projeto existe para atacar: com `PyPDFLoader` essa
célula chegaria ao índice como sopa de números, e a resposta seria recusa ou
invenção.

### O achado principal: o gargalo é o RANKING, não a indexação

A linha de tabela vai de **1/5 para 5/5** só mudando o `k` de 8 para 20. Nenhuma
tabela estava faltando no índice — **todas as cinco estavam lá o tempo todo**, e
todas as cinco respostas vieram do `content_html`. O que falha é a posição:

| Pergunta | Alvo | Posição da tabela certa no ranking |
|---|---|---|
| T1 (critério do guia, forma nua) | Tabela 1, p.5 | **18º** |
| T2 (mesma célula, formulação rica) | Tabela 1, p.5 | **3º** |
| T3 (investimento em E&P) | Tabela 3, p.9 | **20º** |
| T4 (dívida no mercado bancário) | Tabela 6, p.14 | **16º** |
| T5 (depreciação e amortização) | Tabela 7, p.15 | **19º** |

Duas causas, e elas se somam:

1. **Os resumos não se distinguem entre si.** Os nove começam com a mesma
   abertura — oito com *"A tabela apresenta..."* e o nono com *"A tabela
   extraída..."* — e esse prefixo comum domina o embedding. Nas cinco perguntas de tabela o topo do ranking é
   quase sempre a mesma Tabela 1, independentemente de qual tabela responde. O
   índice sabe que aquilo é *uma tabela financeira da Petrobras*; não sabe que é
   *a tabela de endividamento*.
2. **Texto narrativo ganha de resumo em busca densa.** A pergunta é uma frase em
   linguagem natural, e o corpus tem 36 trechos de prosa contra 9 resumos. Os
   trechos falam a mesma língua da pergunta; o resumo é uma descrição em terceira
   pessoa de uma grade de números.

**É o risco 3 do FDD, confirmado com número.** A contingência declarada lá é
multi-representação por original (o modelo 1-para-N já comporta): indexar, além
do resumo, uma linha por métrica da tabela. A hipótese testável é que
`Dívida bruta 3T24 59.132` como representação própria resolve T4 sem `k=20`.

### A formulação da pergunta vale 15 posições

T1 e T2 pedem **a mesma célula**. T1 é a forma nua do guia (*"Qual foi a receita
no 3T24?"*) e cai em 18º; T2 nomeia a empresa e a unidade (*"receita de vendas da
Petrobras... em milhões de reais"*) e sobe para 3º. É o mesmo índice, o mesmo
embedding e a mesma tabela: a única variável é o enunciado.

Isso é honesto registrar como limitação, e não como truque de demonstração. Um
sistema que só acerta quando o usuário já sabe o nome da linha da tabela está
transferindo para ele o trabalho que deveria ser do resumo.

### As duas métricas concordam, e uma terceira pegou o que elas não pegam

Em `k=8`, tabela dá 1/5 de acerto e 3/5 de recusa: o sistema **recusou** três das
quatro que errou, em vez de inventar. As duas métricas andam juntas, que é o sinal
de que a medição não está otimista (na primeira rodada do rag-03 elas
discordavam, e o culpado era a âncora por página).

Sobrou um caso, e ele é o modo de falha mais perigoso de um RAG — respondeu sem a
evidência:

```
T3: Quanto a Petrobras investiu em Exploração & Produção no 3T24, em US$ milhões?
    âncora esperada : 3.773
    resposta        : A Petrobras investiu US$ 3,8 bilhões em Exploração e Produção
                      no 3T24, o que equivale a 3.800 milhões de dólares [2].
```

A resposta está **substancialmente certa e formalmente sem evidência**: o valor
veio do parágrafo da página 9, que arredonda para "US$ 3,8 bilhões", e não da
célula `3.773` da Tabela 3. Foi o texto que salvou, não a tabela. O critério de
âncora é estrito quanto à **procedência**, de propósito: se o corpus não tivesse o
parágrafo redundante, essa pergunta seria uma recusa. A seção `RESPOSTA SEM
ÂNCORA` do script existe para que casos assim nunca sumam dentro de uma fração.

### Imagem: a promessa qualitativa se sustentou; a quantitativa não, como previsto

As três perguntas de gráfico recuperaram a descrição da imagem (`kind=imagem` no
topo em duas delas) e as três respostas acertaram a **direção**:

- **G2 acertou inteiro**: *"o resultado líquido realizado no 2T24 foi negativo,
  com valor aproximado de -2,6 bilhões"*. Sinal e ordem de grandeza corretos, com
  a ressalva de precisão explícita ("aproximado").
- **G1 e G3 acertaram a direção e erraram um valor cada.** G1 (EBITDA
  *realizado*) deu 3T24 = 63,7, que está certo, e 2T24 = 62,3, que é a barra
  *sem eventos exclusivos* — o realizado do 2T24 é 49,7. G3 (EBITDA *sem eventos
  exclusivos*) deu 62,3 → 63,7 onde o gráfico mostra 62,3 → 64,4. Nos dois casos
  o modelo de visão trocou uma barra por outra: as duas séries estão lado a lado
  na mesma figura, e ele leu a errada.

**É exatamente o que o adr-003 previu** ao dividir a promessa por tipo de
evidência, com base na taxa de acerto conhecida dos modelos GPT-4o em gráficos
(~54%) contra tabelas (~68%). Resultado negativo em valor exato de gráfico é
resultado válido e publicável, não defeito a corrigir.

Vale registrar o que só a metade visual entrega: **G3 pergunta pelo rótulo "sem
eventos exclusivos", que não existe em lugar nenhum do texto do PDF** — o `pypdf`
não o extrai, e nenhum dos projetos 1 a 3 poderia responder essa pergunta de
forma alguma. Aqui ela foi respondida, ainda que com o valor trocado.

### O controle negativo se manteve

As duas perguntas cujo alvo só existe no Relatório de Inflação do BCB (meta do
CMN, periodicidade do Copom) receberam recusa explícita nas duas rodadas, **e
inclusive em `k=20`**, quando 20 trechos irrelevantes entram no contexto. A
honestidade herdada dos projetos 2 e 3 sobreviveu ao contexto maior.

### Pendências

1. **Multi-representação por tabela** (contingência do risco 3, já declarada no
   FDD). É a correção apontada pelo achado principal, e não muda o modelo de
   dados: o `doc_id` já liga N representações a um original.
2. **Resumo com o TÍTULO da tabela no começo.** Antes de multi-representação, um
   experimento mais barato: os resumos começam todos iguais porque o prompt não
   pede o rótulo ("Tabela 6 – Indicadores de endividamento") na primeira frase.
3. **O `k` default do contrato é 4, e a medição publicada usa 8 e 20.** Enquanto o
   ranking não melhorar, o default entrega menos do que o sistema é capaz. Mexer
   nele é decisão de contrato, não de operação.
4. **Nenhuma pergunta cobra tabela e gráfico na mesma resposta.** O golden set
   mede as classes isoladas; a pergunta que exige as duas evidências juntas ainda
   não foi escrita.
