# PRD: Pipeline multimodal de ponta a ponta

## Overview

**O problema.** Nos projetos 1 a 3 da trilha, a ingestão usa `PyPDFLoader`: tabelas
viram texto sem estrutura ("sopa de números" sem cabeçalho) e imagens são ignoradas por
completo. Num relatório financeiro real, metade da informação vive exatamente aí — a
receita do trimestre está numa célula de tabela, a tendência de produção está num
gráfico. Perguntas cujo alvo é esse conteúdo são irrespondíveis por melhor que seja a
recuperação: o rag-03 melhorou o ranking do que estava no índice; **não se acha o que
nunca foi indexado**.

**Para quem é.** Para o autor-estudante da trilha de RAG, que consulta o Relatório de
Desempenho 3T24 da Petrobras pelo frontend genérico e opera o pipeline pela linha de
comando — e, por extensão, para quem lê o repositório procurando a resposta para "como
faço meu RAG responder perguntas sobre tabelas e gráficos de PDFs reais".

**Por que vale.** Este projeto ataca a causa raiz que os anteriores contornaram: o que
existe no índice e o que chega ao LLM. A ingestão passa a separar texto, tabela e imagem
(`unstructured hi_res`), enriquecer o que embeda mal (resumo de tabela, descrição de
imagem) e aplicar o padrão multi-vector: **o que busca bem é indexado; o que responde
bem é entregue**. A tabela chega ao LLM como HTML íntegro, e ao usuário como tabela
renderizada de verdade.

A pesquisa de mercado confirma o desenho: o consenso sobre multi-vector é resumir apenas
tabelas e imagens (texto direto); a extração de tabelas do `unstructured hi_res` detecta
bem a presença mas produz HTML imperfeito em tabelas complexas (expectativa calibrada no
risco 1 do HLD); e nenhum produto de referência re-renderiza a tabela original como
evidência — fazê-lo é diferencial deliberado desta entrega.

## Goals

O que passa a ser possível quando isto embarcar:

- Perguntar valor que só existe em célula de tabela ("qual foi a receita no 3T24?") e
  receber a resposta correta, com evidência de que a tabela HTML íntegra — não o resumo
  — chegou ao LLM. Este é o "funcionou se" do guia.
- Perguntar sobre tendências e comparações que vivem em gráficos e receber resposta
  qualitativa baseada na descrição da imagem.
- Ver, no frontend, a tabela-fonte renderizada com linhas e colunas, e o tipo de cada
  evidência (texto, tabela, imagem) em cada fonte.
- Reingerir o corpus quantas vezes for preciso sem duplicar entradas nem repagar
  enriquecimento do que não mudou; iterar em prompts sem repagar a partição.
- Confiar no `/health` para denunciar dessincronia entre os dois armazéns, e zerar tudo
  com um comando quando necessário.

O que o sistema garante: recusa honesta quando o corpus não sustenta (controle negativo
BCB fora do corpus permanece recusado); contrato 1.3.0 estritamente aditivo — nenhum
consumidor existente quebra.

## User Stories

Catálogo canônico em [_user_stories.md](_user_stories.md):

- US-001–US-005 — Ingestão multimodal: partição com separação por tipo, cache da
  partição, idempotência, relatório `elements`, inspeção de tabelas pré-API.
- US-006–US-009 — Consulta: valor de célula de tabela, gráfico qualitativo, recusa por
  grounding, `kind` por hit.
- US-010–US-011 — Frontend: tabela renderizada sanitizada, `elements` no relatório.
- US-012–US-014 — Operação: saúde/sincronia dos dois armazéns, reset único, medição por
  classe de alvo.

## Core Features

**1. Ingestão multimodal com partição `hi_res`.** Um comando (`ingest.py` /
`POST /ingest`) particiona o PDF separando texto narrativo, tabelas (HTML estruturado) e
imagens (arquivos extraídos). A partição bruta — o estágio de minutos de CPU — é
cacheada por hash do conteúdo do PDF; só o que mudou é reprocessado. A resposta reporta
contagens por tipo. Interação: alimenta a indexação dupla (feature 2) e a inspeção
(feature 5).

**2. Indexação dupla multi-vector (seletiva).** Cada elemento gera um original íntegro
no docstore e uma representação buscável no índice vetorial, ligados por `doc_id`
determinístico. Texto narrativo é indexado direto; tabela é indexada pelo resumo em
linguagem natural (entidades, métricas, período, nomes de coluna); imagem é indexada
pela descrição gerada por modelo de visão. Enriquecimento pago roda apenas para o que
mudou. Requisito funcional central: **o resumo busca; o original responde**.

**3. Consulta com entrega do original íntegro.** `POST /ask` busca as representações,
resolve os `doc_id`s no docstore e monta o prompt com os originais — a tabela entra como
HTML completo. Cada hit da resposta carrega `kind`; quando `kind=tabela`, `excerpt`
traz o resumo (o que casou com a busca) e `content_html` traz a tabela original. Recusa
por grounding herdada dos projetos 2 e 3. Pergunta única — sem histórico (ADR-002 da
sessão).

**4. Frontend com evidência tabular real.** A fonte com `kind=tabela` renderiza o
`content_html` como tabela de verdade, sempre sanitizada antes do DOM; cada fonte ganha
selo de tipo; o relatório de ingestão mostra as contagens por elemento. Campos ausentes
degradam para o comportamento atual (padrão `Procedencia`): projetos 1–3 continuam
funcionando no mesmo frontend.

**5. Operação e medição.** Script de inspeção pós-partição (contagem e preview das
tabelas detectadas, sem custo de API — validação do risco 1 antes de qualquer gasto);
`/health` reportando os dois armazéns e a sincronia entre eles; comando único de reset;
script de medição com golden set separado por classe de alvo (texto, tabela, imagem),
com âncoras literais extraídas do PDF por caminho independente do pipeline.

## Business Rules

- Toda tabela e toda imagem indexada tem exatamente um original no docstore e ao menos
  uma representação no índice vetorial, ligados pelo mesmo `doc_id`; o docstore é a
  fonte de verdade (invariante do ADR-001 do projeto).
- `doc_id` deriva de hash do conteúdo (+ origem/tipo): mesmo conteúdo, mesmo id, em
  qualquer execução. Reingestão é idempotente — não duplica, não repaga.
- Roteamento por tipo é fixo: texto narrativo → indexado direto; tabela → resumo;
  imagem → descrição. Nunca se resume texto narrativo (ADR-002 do projeto).
- Semântica do hit por `kind`: `tabela` → `excerpt`=resumo, `content_html`=HTML
  original; `imagem` → `excerpt`=descrição, sem `content_html`; `texto` →
  `excerpt`=trecho, sem `content_html`. HTML nunca viaja dentro de `excerpt`.
- Valor exato é promessa apenas para tabela. Pergunta cujo valor exato só existe num
  gráfico recebe resposta aproximada com marcação explícita, ou recusa (ADR-003 da
  sessão).
- Pergunta sem sustentação no corpus recebe recusa explícita (`refused=true`); o
  controle negativo (BCB, `pdfs/fora-do-corpus/`) jamais entra no índice — a seleção de
  arquivos de ingestão não desce em subdiretórios.
- Contrato 1.3.0 é estritamente aditivo: campos novos são opcionais; opcional ausente é
  omitido do JSON, nunca `null`. Consumidores 1.2.0 não quebram.
- HTML de documento nunca entra cru no navegador: sanitização obrigatória antes de
  qualquer `content_html` ir ao DOM.
- Enriquecimento pago respeita `max_concurrency=5`; nenhuma chamada paga acontece antes
  de o serviço de índice estar acessível e o estágio local estar concluído.
- Truncamento de contexto, se necessário, é por tabela e documentado — nunca silencioso;
  o tamanho do contexto é logado por consulta.
- Limites e defaults exatos (top-k, timeout do `/ingest`, limiares) são fixados no
  FDD/techspec dentro das faixas do contrato; o `/capabilities` os expõe ao frontend.

## User Experience

**Persona consulente** (frontend genérico): seleciona o rag-04, pergunta em linguagem
natural; a resposta vem em prosa com fontes; cada fonte mostra origem, página e selo de
tipo; fonte-tabela expande a tabela renderizada (com rolagem horizontal própria quando
larga). Perguntas sem resposta no corpus recebem recusa clara. Aba de conversa não é
oferecida (pergunta única, ADR-002 da sessão).

**Persona operador** (linha de comando): fluxo de primeira ingestão — instala
dependências nativas, roda partição (avisado de que leva minutos), inspeciona as tabelas
detectadas contra o PDF aberto (sem custo), então libera o enriquecimento pago e a
indexação. Ciclo de iteração — cache de partição faz a reingestão custar segundos;
idempotência faz custar centavos. Medição — script com aviso de custo e modo sem
geração; resultados datados em `docs/operations/`.

Acessibilidade/UX: a tabela renderizada é HTML semântico (herda a legibilidade nativa do
navegador); selos seguem o padrão visual dos badges existentes; nenhuma rolagem lateral
de página inteira.

## High-Level Technical Constraints

- Seis ADRs estruturais vigentes em `docs/adrs/generated/RAG/` (dois armazéns por
  `doc_id`; multi-vector seletivo; `doc_id` determinístico; contrato 1.3.0 aditivo sem
  HTML no `excerpt` e sem rota de mídia; cache de partição por hash do PDF;
  descritor de imagens atrás de `Protocol`). Nenhuma pode ser contrariada sem novo ADR.
- HLD v1.0 (`docs/domains/rag/hld.md`): monólito em camadas com raiz de composição;
  ordem de implementação ditada pelos riscos — setup nativo + smoke test de partição
  primeiro; inspeção de tabelas antes de qualquer resumo pago.
- Stack fixada em `docs/guidelines/README.md` (unstructured[pdf] 0.24.1, langchain
  1.3.14, langchain-classic 1.0.8, fastapi 0.141.1); Chroma em container na porta 8002;
  API em `127.0.0.1:8080`; segredo único `OPENAI_API_KEY` via `.env`.
- Contrato compartilhado `../docs/contracts/rag-api.yaml` evolui 1.2.0→1.3.0 **antes**
  da implementação do consumidor (regra contracts-fit); frontend genérico é o segundo
  consumidor da entrega.
- Ingestão síncrona com timeout generoso documentado; ingestão assíncrona é pendência
  declarada do HLD.
- Desempenho na perspectiva do usuário: consulta em segundos (dominada pela geração);
  primeira ingestão em minutos (comunicado); reingestão sem mudança em segundos.
- Privacidade/segurança: corpus 100% público; risco de injeção via corpus aceito e
  documentado no HLD para a v1 (corpus escolhido pelo autor), com delimitação do
  conteúdo no prompt; sanitização obrigatória no frontend é a contrapartida do lado do
  navegador.

## Non-Goals (Out of Scope)

- **Conversa com histórico** — pergunta única na v1; histórico não exercita o objeto de
  estudo (ADR-002 da sessão).
- **Servir o arquivo da imagem ao frontend** — rota de mídia traria path traversal e
  cache que não ensinam RAG; a imagem participa como descrição textual (ADR-004 do
  projeto; pendência declarada para v2).
- **Valor exato lido de gráfico como promessa** — limitação conhecida dos modelos de
  visão; evidência de imagem é qualitativa (ADR-003 da sessão).
- **Streaming de resposta** — não anunciado em `capabilities`.
- **Sanitização do corpus contra injeção na ingestão** — risco aceito na v1 (corpus do
  autor); seria obrigatório em produção, registrado no HLD.
- **Multi-representação por original** (perguntas hipotéticas, tabela crua além do
  resumo) — o modelo 1→N já comporta; fica para o exercício 2 / branch `exp/`.
- **Ingestão assíncrona e troca do modelo de layout** — pendências declaradas do HLD,
  acionadas apenas se a validação exigir.

## Architecture Decision Records

Decisões desta sessão de PRD (escopo de produto):

- [ADR-001: Frontend genérico evolui na mesma entrega do contrato 1.3.0](adrs/adr-001.md) — tabela renderizada sanitizada, selo `kind`, `elements`; critério de sucesso demonstrável na interface.
- [ADR-002: Pergunta única — sem conversa com histórico na v1](adrs/adr-002.md) — `capabilities` sem `history`; foco no objeto de estudo.
- [ADR-003: Evidência de imagem é qualitativa](adrs/adr-003.md) — valor exato só se promete para tabela; medição separada por classe de alvo.

Decisões estruturais pré-existentes do projeto (contexto vinculante): ADR-001 a ADR-006
em `docs/adrs/generated/RAG/` — ver High-Level Technical Constraints.

## Open Questions

- A qualidade do HTML das tabelas do corpus real (risco 1 do HLD) só será conhecida na
  inspeção pós-partição; se a detecção falhar, o plano de contingência é trocar o modelo
  de layout ou o corpus — decisão adiada por desenho até a evidência existir.
- Biblioteca de sanitização no frontend e limites exatos (top-k, timeout do `/ingest`)
  são decisões de techspec/FDD, dentro das regras já fixadas aqui.
