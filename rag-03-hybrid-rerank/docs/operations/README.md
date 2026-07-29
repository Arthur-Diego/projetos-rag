# Runbooks

Scripts que produziram a evidência de validação e podem ser rodados de novo.
Cada um diz no cabeçalho se gasta chamada paga.

## Pré-requisitos

```bash
docker compose up -d elasticsearch     # leva ~30 s ate aceitar conexao
python ingest.py                       # GASTA API: embeda 617 chunks
```

## `tabela-medicao.py` — o entregável do projeto

**GASTA API.** 10 perguntas contra 3 configurações.

```bash
python docs/operations/tabela-medicao.py --sem-geracao        # so recuperacao
python docs/operations/tabela-medicao.py                      # + taxa de recusa
python docs/operations/tabela-medicao.py --reranker <modelo>  # troca o reordenador
```

As perguntas e as páginas esperadas vivem em `perguntas.json`. As páginas foram
ancoradas por **busca literal no texto do PDF**, com `pypdf`, e nunca pelo
sistema medido: usar a recuperação para descobrir a página certa tornaria a
medição circular, e o sistema acertaria por definição.

---

## Resultado com o corpus de identificadores (28/07/2026, segunda rodada)

Corpus: **Manual de Orientação do Contribuinte da NF-e, Anexo I** (CONFAZ), 153
páginas, 553 chunks. Acerto medido por **âncora textual no trecho**, não por
página. Reordenador multilíngue, `k=4`, `candidates=20`, `rrf_k=60`.

| | só densa | híbrida | híbrida+rerank |
|---|---|---|---|
| Conceituais (5) | 2/5 | 2/5 | 2/5 |
| **Identificadores (5)** | **0/5** | 2/5 | **5/5** |
| **Total (10)** | 2/10 | 4/10 | **7/10** |
| **Recusas (10)** | 9/10 | 8/10 | **6/10** |
| Latência média | 2,12 s | 1,78 s | 2,56 s |

### A hipótese do projeto se confirmou

**A busca densa acertou ZERO das cinco perguntas de identificador.** Não é
"acertou menos": é falha total, e é a falha estrutural que o projeto existe para
demonstrar. Um embedding não distingue `229` de `234`, e as descrições que os
acompanham diferem por uma palavra:

```
229 Rejeição: IE do emitente não informada
230 Rejeição: IE do emitente não cadastrada
231 Rejeição: IE do emitente não vinculada ao CNPJ
232 Rejeição: IE do destinatário não informada
```

As quatro ocupam quase o mesmo ponto do espaço vetorial. O corpus anterior, de
ficção, não produzia essa condição: nomes próprios narrativos vêm cercados de
contexto rico, o que os torna semanticamente densos.

### O achado fino: a fusão sozinha não basta, o rerank é que fecha

Repare na progressão da linha de identificadores: **0/5 → 2/5 → 5/5**.

O BM25 traz o trecho certo para o conjunto de candidatos, mas a fusão por posição
nem sempre o promove ao top-4: ele disputa com 19 outros candidatos do caminho
denso, que estão errados mas bem colocados. **É o cross-encoder que reconhece qual
dos ~30 candidatos responde a pergunta.**

Ou seja, os dois estágios são necessários e nenhum é suficiente. É exatamente o
desenho de funil que o projeto propôs, e a tabela mostra cada etapa contribuindo.

### As duas métricas voltaram a concordar

Na primeira rodada, acerto subia e recusa piorava, e isso denunciava que a
medição por página estava otimista. Com âncora por trecho as duas andam juntas:
acertos 2 → 4 → 7, recusas 9 → 8 → 6. A medição parou de mentir.

### O que continua fraco, e é honesto registrar

**As conceituais ficaram em 2/5 nas três configurações.** Três falham em todas:
contingência (C2), duplicidade (C4) e dígito verificador (C5). Duas explicações
possíveis, e não as separei:

1. As âncoras conceituais podem estar mal escolhidas. `Contingência EPEC` aparece
   5 vezes no documento, e a passagem que de fato *explica* o mecanismo pode não
   ser a que contém a string.
2. O documento é uma tabela de regras de validação, não um texto explicativo. Ele
   **lista** o que rejeita; não **ensina** como funciona. Pergunta conceitual pode
   simplesmente não ter resposta aqui.

A segunda hipótese é a mais provável, e tem consequência: este corpus é excelente
para a metade de identificadores e fraco para a metade conceitual. Um corpus
ideal teria as duas, e ele não existe entre os que testei.

**A taxa de recusa é alta em termos absolutos** (6/10 na melhor configuração). O
modelo recebe fragmentos de tabela e é conservador. Não é defeito do funil: nas
seis recusas da melhor configuração, o trecho certo estava presente em cinco.

### Pendências

1. **Separar as duas hipóteses das conceituais**: reescrever as âncoras
   conceituais ou aceitar que este corpus não responde pergunta conceitual.
2. **Um terceiro corpus para nome próprio raro sem código.** A Bíblia seria boa
   para isso (Melquisedeque, Zorobabel), com a ressalva de que a referência
   `João 3:16` normalmente não aparece como token junto do versículo no PDF,
   então o BM25 não teria o que casar. Testaria a metade de entidade rara, não a
   de código.
3. **Logging estruturado**, herdado do Projeto 2.

---

## Primeira rodada, com corpus de ficção (mantida como contraste)

Corpus: *Harry Potter e a Pedra Filosofal*, 274 páginas, 617 chunks.
Parâmetros: `k=4`, `candidates=20`, `rrf_k=60`. Medida: acerto de recuperação.

### O achado principal, e ele não estava previsto

**O reordenador em inglês estava destruindo recuperação correta.**

| Reordenador | só densa | híbrida | híbrida+rerank | latência média |
|---|---|---|---|---|
| `ms-marco-MiniLM-L-6-v2` (inglês) | 8/10 | 7/10 | **5/10** | 1,85 s |
| `mmarco-mMiniLMv2-L12-H384-v1` (multilíngue) | 8/10 | 7/10 | **8/10** | 1,66 s |

Na linha de identificadores, o inglês entregava **3/5** e o multilíngue entrega
**5/5**. Tudo o mais é idêntico: mesmo corpus, mesmas perguntas, mesmos
parâmetros, mesmo índice. A única variável trocada foi o modelo.

O guia da trilha indica o `ms-marco-MiniLM-L-6-v2`, e ele é treinado no MS MARCO,
que é em inglês. Este projeto indexa português. Medindo os pares isoladamente, o
modelo inglês **até funciona** em português: separa relevante de irrelevante por
cerca de 17,5 pontos, contra 20,7 em inglês. O problema não é ele deixar de
distinguir; é a margem menor virar decisão errada quando se corta 4 de 30
candidatos. Ele não era só mais fraco: **expulsava do top-4 trechos corretos que
a fusão já tinha acertado.**

### Correção de um número que publiquei errado

A primeira versão deste runbook registrou 3,45 s de latência média para a
configuração com reordenação. **Estava inflado pelo carregamento do modelo**, que
acontece uma vez por processo e foi cobrado da rodada inteira. A medição repetida,
com o modelo já em disco, dá **1,66 s**.

O número de regime é ainda menor, e foi medido em separado pela API HTTP: a
primeira requisição de um processo gastou `rerank_s` de **6,036 s**, e a segunda,
com o modelo já em memória, **0,238 s**. O funil completo em regime custa cerca de
0,8 s por turno nesta máquina.

Isso valida a mitigação registrada no ADR-001 da feature: o cache de modelo em
nível de módulo é a diferença entre 6 s e 0,2 s por requisição. Sem ele, cada
`/ask` recarregaria meio gigabyte.

O preço do modelo multilíngue continua existindo (L12 contra L6), mas é bem menor
do que a primeira medição sugeria.

### A tabela completa, com a taxa de recusa

Reordenador multilíngue, `k=4`, `candidates=20`, `rrf_k=60`:

| | só densa | híbrida | híbrida+rerank |
|---|---|---|---|
| Conceituais (5) | 3/5 | 2/5 | 3/5 |
| Identificadores (5) | 5/5 | 5/5 | **5/5** |
| **Acertos (10)** | 8/10 | 7/10 | **8/10** |
| **Recusas (10)** | 3/10 | **2/10** | **5/10** |
| Latência média | 2,68 s | 2,23 s | 3,03 s |

### O achado incômodo: as duas métricas DISCORDAM

**A recuperação melhora com reordenação e a recusa piora.** Acertos vão de 7/10
para 8/10, e recusas vão de 2/10 para 5/10. As duas colunas não podem estar
medindo a mesma coisa.

A explicação, e ela é uma limitação da MEDIÇÃO e não do sistema: o acerto é
medido por **página**, e os trechos têm 1000 caracteres. Uma página rende vários
trechos. O reordenador escolhe trechos que falam *sobre* a entidade sem conter a
frase que a responde; a página bate com a anotação, o acerto é contado, e o modelo
**corretamente** recusa porque o trecho não sustenta resposta nenhuma.

Confirmado na conferência de citação do critério 11: `I4` (plataforma nove e meia)
e `I5` (Olivaras) aparecem como acerto na tabela e **recusaram** quando
perguntados com geração.

Portanto: **a métrica de acerto por página superestima o sucesso.** Ela mede "o
funil chegou perto", não "o funil trouxe a resposta". A taxa de recusa é a métrica
mais honesta das duas, e é justamente ela que o ADR-002 mandou manter ao lado.

Isso reforça a pendência do golden set: a anotação precisa descer de página para
**trecho**, ou o acerto precisa exigir que o texto da resposta esteja no trecho
recuperado, e não apenas que a página coincida.

### O que a tabela diz sobre a busca híbrida, e o que ela não diz

A coluna híbrida (7/10) fica **abaixo** da densa pura (8/10) neste corpus. Isso
**não** é defeito de implementação, e há evidência disso:

- **Critério de aceite 8 passou.** Cinco termos raros (`Quadribol`,
  `Nicolau Flamel`, `Grifinória`, `trasgo`, `Dumbledore`) buscados APENAS pelo
  caminho léxico retornam trechos. O BM25 rodou.
- **Critério de aceite 7 passou.** O mapping conferido no motor tem `text` com
  analisador `brazilian` e `dense_vector` de 1536 com `cosine`.

A explicação que sobra é a **pendência declarada desde o PRD**: este corpus não
tem identificadores de verdade. Nomes próprios de ficção aparecem em contexto
narrativo rico ("Nicolau Flamel" vem cercado de "pedra filosofal", "alquimista",
"elixir"), o que os torna semanticamente densos. A busca densa vai bem neles. Não
existe `E-4021` em Harry Potter, e é o `E-4021` que a busca híbrida existe para
resolver.

**Portanto a tabela ainda não responde a pergunta do projeto.** Ela responde uma
outra, que não estava sendo feita e é útil: reordenar na língua errada custa três
acertos em dez.

### Pendências de validação

1. **A anotação do golden set precisa descer de página para trecho.** É a
   pendência mais importante, e a tabela acima é a evidência: acerto por página
   conta como sucesso um trecho que não sustenta resposta nenhuma. Enquanto isso
   não mudar, a coluna de acertos é otimista e só a de recusas é confiável.
2. **Trocar o corpus** por documentação técnica em português densa em
   identificadores (CID-10, NCM, manual com códigos de erro). Não muda uma linha
   de código: troca o PDF em `pdfs/` e o `perguntas.json`. É o experimento que
   finalmente responde se a busca híbrida ajuda.
3. **`C1` falha nas três configurações**, o que cheira a âncora imprecisa e não a
   recuperação ruim. Vale conferir a página do chapéu seletor à mão.
4. **Logging estruturado**, pendência herdada do Projeto 2 e não resolvida aqui.
