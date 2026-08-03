# User Stories: Pipeline multimodal de ponta a ponta

Catálogo canônico de comportamento do pipeline multimodal do rag-04. Companheiro do
`_prd.md`; consumido pelo FDD/techspec (mapeamento de componentes) e pela decomposição
de tasks (matriz de cobertura).

## Personas

- **Autor-consulente** — o autor da trilha usando o frontend genérico para perguntar
  sobre o relatório da Petrobras. Precisa de respostas corretas com evidência visível,
  inclusive quando a resposta vive numa célula de tabela ou num gráfico.
- **Autor-operador** — o mesmo autor operando o pipeline pela linha de comando: ingere o
  corpus, inspeciona o que a partição detectou, mede o resultado, zera e reingere.
  Paga as chamadas de API do próprio bolso — custo repetido é dor direta.

## Story Index

| ID     | Feature Area | Persona | Story |
|--------|--------------|---------|-------|
| US-001 | Ingestão multimodal | Autor-operador | Ingerir o PDF separando texto, tabela e imagem |
| US-002 | Ingestão multimodal | Autor-operador | Reaproveitar a partição já feita (cache) |
| US-003 | Ingestão multimodal | Autor-operador | Reingerir sem duplicar nem repagar (idempotência) |
| US-004 | Ingestão multimodal | Autor-operador | Ver a contagem de elementos por tipo no relatório |
| US-005 | Ingestão multimodal | Autor-operador | Inspecionar as tabelas detectadas antes de gastar API |
| US-006 | Consulta | Autor-consulente | Perguntar valor que só existe em célula de tabela |
| US-007 | Consulta | Autor-consulente | Perguntar sobre conteúdo de gráfico (qualitativo) |
| US-008 | Consulta | Autor-consulente | Receber recusa quando o corpus não sustenta |
| US-009 | Consulta | Autor-consulente | Ver de onde veio cada trecho da resposta (kind) |
| US-010 | Frontend | Autor-consulente | Ver a tabela de verdade renderizada na fonte |
| US-011 | Frontend | Autor-consulente | Ver o relatório de ingestão com elementos por tipo |
| US-012 | Operação | Autor-operador | Saber se os dois armazéns estão saudáveis e em sincronia |
| US-013 | Operação | Autor-operador | Zerar tudo com um comando e reingerir do zero |
| US-014 | Operação | Autor-operador | Medir o acerto por tipo de alvo com o golden set |

## Ingestão multimodal

### US-001: Ingerir o PDF separando texto, tabela e imagem

**As a** Autor-operador, **I want** ingerir `pdfs/petrobras-desempenho-3t24.pdf` com um
comando (`ingest.py` ou `POST /ingest`) que separa texto, tabelas e imagens, **so that**
o índice contenha o que o `PyPDFLoader` dos projetos 1–3 destruía ou ignorava.

Acceptance criteria:

- AC-1: Given o corpus em `pdfs/`, when a ingestão roda, then cada elemento é
  classificado como texto, tabela ou imagem; tabelas são preservadas como HTML
  estruturado e imagens são extraídas para arquivo.
- AC-2: Given a ingestão concluída, when se examinam os dois armazéns, then cada
  original está no docstore sob um `doc_id` e sua representação buscável está no índice
  vetorial com o mesmo `doc_id` e o `kind` no metadado.
- AC-3: Given um elemento de texto narrativo, when é indexado, then o texto entra
  direto (sem resumo); given uma tabela ou imagem, then o que entra no índice é o
  resumo/descrição em linguagem natural, e o original fica íntegro no docstore.
- AC-4: Given a ingestão em andamento, when cada estágio conclui, then o log estruturado
  registra elementos por categoria e página, acertos de cache, quantidade de
  resumos/descrições e vetores/originais gravados.

Edge cases:

- EC-1: PDF ausente ou caminho errado → falha clara antes de qualquer chamada paga, com
  mensagem indicando o caminho esperado.
- EC-2: PDF em `pdfs/fora-do-corpus/` → nunca entra na ingestão (o controle negativo não
  pode vazar para o índice); a seleção de arquivos não desce em subdiretórios.
- EC-3: Partição não detecta nenhuma tabela → a ingestão conclui, mas o relatório e o
  log denunciam `tabelas: 0` (é o sinal do risco 1, não uma falha silenciosa).
- EC-4: Serviço de índice (Chroma) fora do ar → falha antes do estágio pago, com erro
  de serviço indisponível; nada é gravado pela metade nos dois armazéns.
- EC-5: Falha da API da OpenAI no meio do enriquecimento → a ingestão para com erro
  claro; a reexecução retoma sem repagar o que já foi enriquecido e gravado.
- EC-6: Duas ingestões simultâneas → fora de escopo declarado (autor único, execução
  sequencial); comportamento não definido não é prometido.

### US-002: Reaproveitar a partição já feita (cache)

**As a** Autor-operador, **I want** que a partição `hi_res` (minutos de CPU) seja
gravada em cache e reutilizada, **so that** iterar em prompts e indexação não repague o
estágio mais lento.

Acceptance criteria:

- AC-1: Given a primeira ingestão de um PDF, when a partição conclui, then o resultado
  bruto é gravado em `data/partition/` chaveado pelo hash do conteúdo do PDF.
- AC-2: Given o cache existente e o PDF inalterado, when a ingestão roda de novo, then a
  partição é lida do cache (segundos, não minutos) e o log registra o acerto de cache.
- AC-3: Given o PDF alterado (hash diferente), when a ingestão roda, then a partição é
  refeita e o cache antigo não é usado.

Edge cases:

- EC-1: Cache corrompido/ilegível → a partição é refeita do zero e o cache é
  regravado; o log denuncia o descarte.
- EC-2: `data/partition/` inexistente (primeira execução) → criado automaticamente.
- EC-3: Mesmo PDF com nome de arquivo diferente → o cache acerta mesmo assim (a chave é
  o hash do conteúdo, não o nome).

### US-003: Reingerir sem duplicar nem repagar (idempotência)

**As a** Autor-operador, **I want** rodar a ingestão repetidas vezes sem duplicar
entradas nem repagar resumo/descrição/embedding do que não mudou, **so that** o ciclo de
desenvolvimento não custe dinheiro a cada iteração.

Acceptance criteria:

- AC-1: Given uma ingestão concluída, when a mesma ingestão roda de novo, then a
  contagem de itens nos dois armazéns não muda e nenhuma chamada de enriquecimento é
  feita para elementos já processados.
- AC-2: Given o mesmo conteúdo, when o `doc_id` é calculado, then ele é idêntico entre
  execuções (derivado de hash de conteúdo + origem/tipo, nunca aleatório).

Edge cases:

- EC-1: Reingestão após falha parcial (metade gravada) → completa o que falta sem
  duplicar o que já está.
- EC-2: Dois elementos com conteúdo idêntico no mesmo PDF (ex.: rodapé repetido) → um
  único `doc_id`; o sistema não trata como erro.

### US-004: Ver a contagem de elementos por tipo no relatório

**As a** Autor-operador, **I want** que a resposta do `/ingest` traga a contagem de
elementos por tipo (textos, tabelas, imagens), **so that** eu saiba imediatamente se a
extração multimodal funcionou antes de fazer qualquer pergunta.

Acceptance criteria:

- AC-1: Given a ingestão concluída via API, when o relatório retorna, then ele contém as
  contagens por tipo além dos campos obrigatórios do contrato (`pages`, `chunks`,
  `seconds`).
- AC-2: Given o contrato 1.3.0, when um consumidor 1.2.0 lê o relatório, then nada
  quebra (campos novos são opcionais e aditivos).

Edge cases:

- EC-1: Nenhuma imagem no PDF → `imagens: 0` presente no relatório (zero explícito, não
  campo ausente).

### US-005: Inspecionar as tabelas detectadas antes de gastar API

**As a** Autor-operador, **I want** um script de inspeção pós-partição que mostre
contagem e preview das tabelas HTML detectadas, **so that** eu valide a detecção (risco
1 do HLD) com o PDF aberto ao lado, antes de pagar qualquer resumo.

Acceptance criteria:

- AC-1: Given o cache de partição existente, when o script roda, then ele lista cada
  tabela detectada com página e um preview legível do HTML, sem nenhuma chamada de API.
- AC-2: Given a saída do script, when comparada com o PDF, then é possível decidir se a
  detecção está boa o suficiente para prosseguir (decisão humana, evidência do sistema).

Edge cases:

- EC-1: Cache de partição ausente → o script instrui a rodar a partição primeiro (ou a
  executa localmente), deixando claro que é o estágio lento e não pago.
- EC-2: Tabela detectada com HTML vazio ou malformado → aparece na listagem marcada como
  suspeita, não é escondida.

## Consulta

### US-006: Perguntar valor que só existe em célula de tabela

**As a** Autor-consulente, **I want** perguntar "qual foi a receita no 3T24?" e receber
a resposta correta, **so that** perguntas tabulares — irrespondíveis nos projetos 1–3 —
passem a funcionar.

Acceptance criteria:

- AC-1: Given o corpus ingerido, when pergunto valor que vive numa célula de tabela,
  then a resposta contém o valor correto e cita a fonte.
- AC-2: Given a resposta, when examino os hits, then o hit da tabela tem `kind=tabela`,
  `excerpt` com o resumo (o que casou com a busca) e `content_html` com a tabela
  original íntegra.
- AC-3: Given a consulta processada, when examino o log/contexto, then há evidência de
  que o que chegou ao LLM foi a tabela HTML íntegra, não o resumo (critério de sucesso
  do guia).

Edge cases:

- EC-1: Pergunta ambígua entre duas tabelas → a resposta usa as tabelas recuperadas e
  cita ambas as fontes; não inventa consolidação que o corpus não dá.
- EC-2: Tabela grande estourando o limite de contexto → truncamento documentado por
  tabela, nunca silencioso (risco 5 do HLD); o log registra o tamanho do contexto.
- EC-3: Pergunta cujo termo está no HTML mas não no resumo (drift resumo↔conteúdo) → se
  a busca não recupera a tabela, é recusa honesta; o caso alimenta a medição (US-014) e
  a pendência de multi-representação, não é mascarado.

### US-007: Perguntar sobre conteúdo de gráfico (qualitativo)

**As a** Autor-consulente, **I want** perguntar sobre tendências e comparações que vivem
num gráfico do relatório, **so that** informação visual — ignorada nos projetos 1–3 —
participe das respostas.

Acceptance criteria:

- AC-1: Given o corpus ingerido, when pergunto sobre tendência/comparação visível num
  gráfico, then a resposta reflete a descrição da imagem e o hit tem `kind=imagem` com a
  descrição no `excerpt`.
- AC-2: Given uma pergunta de valor exato cuja resposta só existe num gráfico, when o
  sistema responde, then a resposta é aproximada com marcação explícita ("cerca de") ou
  é recusa — nunca um número preciso inventado.

Edge cases:

- EC-1: Imagem decorativa (logo, foto) descrita → pode ser indexada; a descrição honesta
  ("logotipo da empresa") não deve casar com perguntas factuais.
- EC-2: Pergunta sobre imagem que o modelo de visão descreveu mal → recusa ou resposta
  qualitativa; o caso entra na medição por classe (US-014) como limitação conhecida.

### US-008: Receber recusa quando o corpus não sustenta

**As a** Autor-consulente, **I want** que perguntas sem resposta no corpus recebam
recusa explícita, **so that** o sistema continue honesto (herança dos projetos 2 e 3).

Acceptance criteria:

- AC-1: Given uma pergunta cuja resposta só existe no relatório do BCB (nunca indexado),
  when pergunto, then a resposta é recusa explícita, sem inventar.
- AC-2: Given a recusa, when examino a resposta da API, then `refused=true` e os campos
  do contrato se mantêm válidos.

Edge cases:

- EC-1: Pergunta fora de domínio por completo ("qual a capital da França?") → recusa.
- EC-2: Índice vazio (nada ingerido) → o `/ask` falha com erro claro de índice ausente
  (precedente rag-03: falhar antes de chamada paga), não com recusa disfarçada.

### US-009: Ver de onde veio cada trecho da resposta (kind)

**As a** Autor-consulente, **I want** ver, em cada fonte da resposta, se ela é texto,
tabela ou imagem, **so that** eu entenda que tipo de evidência sustenta a resposta.

Acceptance criteria:

- AC-1: Given uma resposta com hits, when a API responde, then cada hit carrega
  `kind ∈ {texto, tabela, imagem}`.
- AC-2: Given `kind=tabela`, then `excerpt` = resumo e `content_html` = tabela original;
  given `kind=imagem`, then `excerpt` = descrição; given `kind=texto`, then `excerpt` =
  o próprio trecho e `content_html` ausente.

Edge cases:

- EC-1: Consumidor do contrato 1.2.0 (projetos anteriores, frontend antigo) → ignora
  `kind`/`content_html` sem quebrar (aditividade do ADR-004).
- EC-2: `provenance` → ausente em todos os hits (só há caminho denso neste projeto);
  o frontend não mostra badges de procedência.

## Frontend

### US-010: Ver a tabela de verdade renderizada na fonte

**As a** Autor-consulente, **I want** que, no frontend, a fonte com `kind=tabela` mostre
a tabela renderizada de verdade (linhas e colunas), **so that** a evidência tabular seja
legível — o critério de sucesso do guia na interface.

Acceptance criteria:

- AC-1: Given uma resposta com hit `kind=tabela`, when a fonte é exibida, then o
  `content_html` aparece como tabela HTML renderizada (não tags escapadas, não texto
  corrido), após sanitização.
- AC-2: Given qualquer `content_html`, when vai ao DOM, then passou por sanitização —
  HTML de documento nunca entra cru no navegador.
- AC-3: Given um hit `kind=texto` ou `kind=imagem`, when a fonte é exibida, then o
  comportamento atual se mantém (excerpt como texto), com o selo de `kind` no cabeçalho.
- AC-4: Given uma resposta de um projeto anterior (sem `kind`), when exibida no mesmo
  frontend, then nada muda para ela (campo ausente = selo ausente, padrão Procedencia).

Edge cases:

- EC-1: `content_html` malformado (tabela quebrada do unstructured) → o navegador
  renderiza o que der após sanitização; a UI não quebra nem esconde o hit.
- EC-2: Tabela larga demais para a coluna de fontes → contêiner com rolagem horizontal
  própria; a página não ganha rolagem lateral.
- EC-3: `kind=tabela` sem `content_html` (inconsistência do backend) → exibe o excerpt
  como texto, sem erro na UI.

### US-011: Ver o relatório de ingestão com elementos por tipo

**As a** Autor-consulente, **I want** que a aba de ingestão do frontend mostre as
contagens de textos, tabelas e imagens, **so that** o resultado da extração multimodal
seja visível sem abrir o console.

Acceptance criteria:

- AC-1: Given uma ingestão pelo frontend contra o rag-04, when o relatório chega, then
  as três contagens aparecem junto dos campos atuais.
- AC-2: Given um relatório de projeto anterior (sem `elements`), when exibido, then as
  linhas novas simplesmente não aparecem (aditividade preservada).

Edge cases:

- EC-1: Ingestão longa (minutos de `hi_res` na primeira vez) → o frontend não estoura
  timeout na cara do usuário; o tempo esperado é comunicado (timeout generoso
  documentado no HLD).

## Operação

### US-012: Saber se os dois armazéns estão saudáveis e em sincronia

**As a** Autor-operador, **I want** que o `/health` reporte índice vetorial, docstore e
a sincronia entre eles, **so that** o risco de `doc_id` órfão (metade do índice morta)
seja denunciado antes de aparecer como resposta errada.

Acceptance criteria:

- AC-1: Given os dois armazéns populados e consistentes, when consulto `/health`, then
  `status=ok` com as contagens de cada armazém.
- AC-2: Given dessincronia (contagens incompatíveis ou `doc_id` sem original), when
  consulto `/health`, then `status=degraded` com a evidência da dessincronia.

Edge cases:

- EC-1: Chroma fora do ar → `/health` responde (não trava) e denuncia o componente
  indisponível.
- EC-2: Docstore vazio com índice populado → `degraded`, com instrução de reset.

### US-013: Zerar tudo com um comando e reingerir do zero

**As a** Autor-operador, **I want** um comando único que limpe os dois armazéns, **so
that** nunca fique metade viva (índice sem docstore ou vice-versa).

Acceptance criteria:

- AC-1: Given os dois armazéns populados, when rodo o reset, then ambos ficam vazios na
  mesma operação e o `/health` volta a reportar estado consistente.
- AC-2: Given o reset, when decido preservar o cache de partição, then o cache de
  `data/partition/` sobrevive por padrão (zerar armazéns ≠ repagar `hi_res`).

Edge cases:

- EC-1: Reset com um dos armazéns já vazio → conclui sem erro (idempotente).
- EC-2: Reset interrompido no meio → o estado resultante é denunciado pelo `/health`
  como dessincronia; rodar o reset de novo conserta.

### US-014: Medir o acerto por tipo de alvo com o golden set

**As a** Autor-operador, **I want** um script de medição com golden set separado por
tipo de alvo (texto, tabela, imagem), **so that** o ganho do pipeline multimodal seja
demonstrado com números, no padrão dos projetos anteriores.

Acceptance criteria:

- AC-1: Given o golden set em arquivo de dados (`perguntas.json`), when o script roda,
  then reporta acerto de recuperação e taxa de recusa por classe de alvo, e as âncoras
  de acerto são trechos literais extraídos do PDF por caminho independente do pipeline
  (anticircularidade — nunca pelo `unstructured` do próprio sistema).
- AC-2: Given a pergunta-critério do guia ("qual foi a receita no 3T24?"), when medida,
  then o resultado inclui a evidência de que a tabela HTML chegou ao prompt.
- AC-3: Given o script, when invocado, then o cabeçalho avisa que gasta chamadas pagas e
  há um modo `--sem-geracao` para medir só recuperação.

Edge cases:

- EC-1: Resultado pior que o esperado numa classe → é resultado válido e publicável
  (padrão da trilha), registrado em `docs/operations/` com data.
- EC-2: Âncora presente em mais de um elemento → o acerto conta se qualquer hit
  recuperado contém a âncora (critério literal, precedente rag-03).
