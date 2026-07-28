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

## Resultado da validação de 28/07/2026

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

1. **Trocar o corpus** por documentação técnica em português densa em
   identificadores (CID-10, NCM, manual com códigos de erro). Não muda uma linha
   de código: troca o PDF em `pdfs/` e o `perguntas.json`. É o experimento que
   finalmente responde se a busca híbrida ajuda.
2. **Conferir o golden set.** As páginas foram ancoradas por co-ocorrência de
   termos, o que garante não-circularidade mas não garante que a passagem
   ancorada seja a melhor resposta. `C1` falha nas três configurações, o que
   cheira mais a âncora imprecisa do que a recuperação ruim.
3. **Taxa de recusa não foi medida.** Todas as execuções usaram `--sem-geracao`.
   Falta rodar sem a flag para obter a coluna comparável com o Projeto 2.
4. **Conferência de citação à mão** (critério 11) contra a página real do PDF.
