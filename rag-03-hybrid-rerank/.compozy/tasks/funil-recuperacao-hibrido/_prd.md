# PRD: Funil de recuperação híbrido

## Overview

**O problema.** O pipeline de RAG herdado do Projeto 2 recupera trechos por um único
caminho: proximidade no espaço vetorial. Isso falha de um jeito específico e mensurável.
Embeddings capturam significado, e termos literais não têm significado semântico: um código
de erro, um artigo de norma, um nome próprio raro produzem vetores quase indistinguíveis
entre si. Quando a pergunta é sobre esse tipo de alvo, o trecho certo não entra na janela e
o sistema recusa.

O Projeto 2 mediu o tamanho do buraco: **cerca de um terço das perguntas factuais recebia
recusa apesar de haver, no corpus indexado, passagem que as respondia.** A recusa é honesta
em relação ao que foi recuperado, e é exatamente por isso que engana. Ela se parece com
ausência de informação quando é falha de recuperação, e nada na saída distingue os dois
casos.

A literatura confirma que não é anedota: em *EntityQuestions* (Sciavolino et al., EMNLP
2021), a acurácia de recuperação em top-20 para perguntas simples sobre entidades é de
**72,0% para BM25 contra 49,7% para recuperação densa**, e em certas relações o buraco chega
a 19,2 contra 85,0. O desempenho denso cai monotonicamente conforme a entidade fica mais
rara.

**Para quem é.** Para o autor-estudante que está construindo a trilha de dez projetos de
RAG e precisa entender, medindo, por que a recuperação falha e o que a conserta. E, por
extensão, para qualquer pessoa que leia este repositório procurando a resposta para "como
faço meu RAG parar de recusar coisas que ele tem indexadas".

**Por que vale.** Este é o projeto com a melhor relação ganho por esforço da trilha inteira.
Ele não troca o modelo de linguagem, não melhora o prompt e não muda a arquitetura: mexe em
um lugar só, o que entra na janela de contexto, e é ali que a maior parte da qualidade de um
RAG é decidida.

## Goals

O que o autor passa a conseguir fazer, e que hoje não consegue:

- Fazer uma pergunta sobre um termo literal presente no corpus e receber o trecho que o
  contém, em vez de uma recusa.
- Ver, para cada trecho recuperado, **por que ele está naquela posição**: qual caminho o
  encontrou, em que colocação, e o que a fusão e a reordenação fizeram com ele.
- Comparar três configurações de recuperação sobre as mesmas perguntas e obter uma tabela,
  reprodutível e produzida por comando, em vez de uma impressão.
- Atribuir latência ao estágio certo, e responder com número quanto custa ampliar a janela
  de candidatos.
- Trocar o corpus de estudo editando arquivos de dados, sem tocar em código.

O que o sistema passa a garantir:

- Um trecho encontrado pelos dois caminhos de busca é promovido em relação a um trecho
  encontrado por apenas um.
- A citação `[n]` continua apontando para o trecho correto mesmo depois de a reordenação ter
  mudado toda a ordem.
- Um índice mal preparado para busca por palavra exata é **detectado e reportado**, em vez de
  degradar em silêncio.
- Uma recusa nunca vem acompanhada de citação.

O que deixa de ser necessário:

- Aumentar o número de trechos recuperados na mão para tentar alcançar o trecho certo,
  enchendo a janela de contexto de material irrelevante.
- Reformular a pergunta até acertar o vocabulário do documento, o que exige já saber a
  resposta.

## User Stories

Catálogo canônico em [_user_stories.md](_user_stories.md). Índice por área:

- **US-001 a US-003 — Ingestão.** Indexação num índice único que atende os dois caminhos,
  relatório comparável ao do Projeto 2, e preservação do corpus de controle fora do índice.
- **US-004 a US-006 — Recuperação híbrida.** Dois caminhos independentes, fusão por posição,
  e recuperação de termos literais que hoje falham.
- **US-007 e US-008 — Reranking.** Reordenação por precisão antes da geração, e integridade
  da citação apesar da reordenação.
- **US-009 e US-010 — Parametrização e descoberta.** Ajuste dos parâmetros do funil sem
  alterar código, e descoberta dos controles pela interface.
- **US-011 e US-012 — Observabilidade.** Custo por estágio, e procedência por trecho.
- **US-013 e US-014 — Medição.** Produção da tabela das três configurações, e troca de corpus
  sem código.
- **US-015 e US-016 — Diagnóstico.** Aviso de índice mal mapeado, e distinção entre
  infraestrutura fora do ar e índice vazio.
- **US-017 — Compatibilidade.** Projetos 1 e 2 continuam funcionando sem alteração.

## Core Features

### 1. Recuperação por dois caminhos

Toda pergunta é buscada simultaneamente por significado e por palavra exata, sobre o mesmo
conjunto de trechos indexados. Cada caminho produz sua própria lista ordenada de candidatos.

Importa porque os dois erram coisas diferentes: o caminho semântico acerta o sinônimo e erra
o token; o caminho léxico acerta o token e erra o sinônimo. Isoladamente cada um tem um ponto
cego previsível; juntos, os pontos cegos não coincidem.

Requisitos funcionais: os dois caminhos operam sobre a mesma pergunta já resolvida pelo
estágio de reescrita; a quantidade de candidatos por caminho é configurável; a falha de um
caminho não impede o outro de contribuir.

### 2. Fusão por posição

Os dois rankings são combinados usando apenas a **colocação** de cada trecho, nunca o valor
bruto que cada caminho atribuiu.

Importa porque os valores são incomparáveis por natureza: uma escala é ilimitada e depende
da frequência dos termos no corpus, a outra é limitada e mede ângulo entre vetores. Não
existe normalização honesta entre elas, e qualquer tentativa torna o resultado de um trecho
dependente de quem mais foi recuperado junto com ele, o que quebra a reprodutibilidade que a
medição exige.

Requisitos funcionais: um trecho presente nos dois rankings acumula as duas contribuições e
é promovido; trechos repetidos contam uma vez, pela melhor colocação; a identidade do trecho
vem do documento indexado e não de um prefixo do seu texto; o parâmetro de amortecimento da
fusão é configurável e validado.

### 3. Reordenação por precisão

Os candidatos fundidos passam por um modelo que lê a pergunta **junto** de cada candidato,
numa única passada, e os reordena. Do resultado, apenas os primeiros seguem para a geração.

Importa porque a busca compara representações produzidas separadamente, enquanto este
estágio compara pergunta e documento em conjunto. É caro e não escala, e por isso opera sobre
poucas dezenas de candidatos e não sobre o corpus.

Requisitos funcionais: ligado por padrão em todos os caminhos de uso (ADR-001); o corte final
é configurável; o estágio termina **inteiramente antes** de os trechos saírem da recuperação,
para que nenhuma reordenação ocorra depois da numeração das citações; falha ao preparar o
modelo é reportada, nunca contornada em silêncio.

Ressalva registrada: reordenação **não melhora sempre**. No BEIR, o ganho médio é de cerca de
+11% em nDCG@10, com variação de −26% a +47% conforme o conjunto de dados. Existe corpus em
que ela piora o resultado, e é por isso que ela é um estágio comparável e desligável, não uma
verdade assumida.

### 4. Medição das três configurações

Um comando produz a tabela: 10 perguntas, sendo 5 conceituais e 5 sobre identificadores,
contra três configurações (só semântica, híbrida, híbrida com reordenação).

Importa porque **a tabela é o entregável do projeto**, não o código. Sem ela, "a busca
híbrida melhorou" é opinião.

Requisitos funcionais: acerto é definido contra páginas anotadas à mão (ADR-002); a taxa de
recusa é registrada ao lado, para comparação com o Projeto 2; perguntas e anotações vivem em
arquivo de dados; o resultado é reprodutível entre execuções; o harness declara no cabeçalho
que gasta chamadas pagas.

### 5. Observabilidade do funil

Cada resposta carrega o tempo de cada estágio separadamente e, por trecho, a procedência
completa.

Importa porque um funil de vários estágios medido como um número só não permite responder
onde o tempo foi gasto nem por que a ordem é a que é. Neste projeto isso não é conforto de
diagnóstico: é o instrumento principal.

Requisitos funcionais: tempos separados por reescrita, busca semântica, busca léxica, fusão,
reordenação e geração; estágio que não rodou aparece ausente e não zerado; procedência
exibida no terminal e no navegador (ADR-003); valores de escalas opostas nunca compartilham
o mesmo campo.

### 6. Diagnóstico de índice mal preparado

O sistema verifica que o campo de texto do índice está preparado para busca por termos, e
reporta quando não está.

Importa porque este é o modo de falha mais perigoso do projeto: se o campo estiver preparado
como valor único em vez de texto analisado, a busca léxica deixa de funcionar **sem erro
nenhum**. Metade do funil vira decoração, a tabela mostra "a híbrida não ajudou", e a
conclusão registrada seria falsa.

Requisitos funcionais: o preparo do índice é definido explicitamente pelo sistema na criação,
nunca inferido pelo motor; a verificação de saúde reporta divergência com instrução de
correção; a validação do projeto inclui uma verificação de fumaça que busca um termo literal
conhecido apenas pelo caminho léxico e exige resultado.

### Interação entre as features

As features 1, 2 e 3 formam uma cadeia estrita: nenhuma delas entrega valor sozinha. Fusão
sem dois caminhos não funde nada; reordenação sem candidatos não reordena nada. As features 4
e 5 são o que torna as três primeiras verificáveis, e a feature 6 é o que impede que a
feature 4 produza uma conclusão errada.

## Business Rules

**Invariantes**

- Uma resposta com recusa tem lista de citações vazia. Recusa com citação é defeito.
- O rótulo `[n]` de uma citação nunca é a posição do trecho na lista devolvida. A resolução
  passa por referência explícita.
- Nenhuma reordenação de trechos ocorre depois da numeração do contexto.
- O corpus de controle nunca é indexado.
- O índice é derivado: os documentos de origem são a fonte de verdade, e reindexar reconstrói
  tudo.

**Validação e resultado ao usuário**

- Parâmetro fora da faixa aceita recusa a execução com mensagem que nomeia o parâmetro, o
  valor recebido e a faixa válida. Não há coerção silenciosa para o padrão.
- Corte final maior que a janela de candidatos é contradição de configuração e é recusado.
- Pergunta vazia é recusada antes de qualquer busca.
- Valor de parâmetro malformado é recusado, e não convertido para o padrão em silêncio.

**Ciclo de vida do índice**

- Estados observáveis: inexistente, vazio, populado, mal preparado, motor indisponível.
- A reindexação descarta o índice anterior **antes** de ler os documentos. Falha no meio
  deixa o índice vazio, cujo sintoma é evidente, e nunca desatualizado, cujo sintoma não
  existe.
- A contagem de trechos descartados é feita antes da destruição.
- Índice vazio e motor indisponível produzem mensagens e efeitos distintos.

**Limites e padrões**

- Reordenação: **ligada** por padrão em todos os caminhos.
- Fusão: parâmetro de amortecimento com padrão 60, que é o valor de referência da literatura
  e o default do Elasticsearch, do LangChain e do Azure AI Search. Nenhum fornecedor publica
  curva de sensibilidade, então varrer esse valor é exercício de entendimento e não busca de
  ótimo.
- Janela de candidatos por caminho: padrão 20, configurável, com teto próprio e independente
  do teto do corte final.
- Corte final: padrão 4, mantendo continuidade com o Projeto 2.
- Cada parâmetro novo tem faixa própria. O teto existente do número de trechos finais não é
  reaproveitado para a janela de candidatos, que é de outra ordem de grandeza.

**Permissões e visibilidade**

- Não há autenticação nem autorização. O serviço escuta apenas em loopback e serve o usuário
  local. Está declarado fora de escopo.

## User Experience

**Personas e objetivos.** O autor-estudante quer enxergar o mecanismo; o operador da medição
quer resultado reprodutível; o consumidor do navegador quer confiar na citação; o operador de
infraestrutura quer saber onde está o defeito; os Projetos 1 e 2 querem não ser quebrados.

**Fluxo principal, terminal.** Sobe-se o motor de busca em container e aguarda-se o
healthcheck. Roda-se a ingestão, que informa quantas páginas leu, quantos trechos criou e
quantos descartou do índice anterior. Abre-se o REPL, que informa quantos trechos estão
indexados e com que parâmetros. Faz-se uma pergunta. A resposta vem com as citações, e
abaixo dela cada trecho recuperado aparece com sua procedência e a lista de tempos por
estágio. Faz-se uma pergunta de acompanhamento, e a reescrita do Projeto 2 continua
funcionando: a pergunta resolvida aparece ao lado da literal.

**Fluxo principal, navegador.** A interface carrega os controles a partir da descoberta de
capacidades, sem que o frontend saiba de antemão o que este projeto oferece. Ajusta-se a
configuração de recuperação e os parâmetros do funil por controles. Pergunta-se. Clica-se na
citação e confere-se a página. A procedência de cada trecho fica visível junto do trecho.

**Fluxo da medição.** Roda-se o harness. Ele lê o arquivo de perguntas anotadas, executa as
três configurações, e imprime a tabela com acertos por categoria e taxa de recusa ao lado. O
mesmo comando, no mesmo corpus, produz a mesma tabela.

**Descoberta.** Nenhum parâmetro novo exige documentação para ser encontrado: os controles
aparecem na interface e as opções de linha de comando aparecem na ajuda. O que precisa de
explicação é o significado da procedência, e ela é autoexplicativa pelo rótulo.

**Primeira execução.** É lenta e precisa avisar: o modelo de reordenação baixa cerca de
500 MB, e o motor de busca leva dezenas de segundos até aceitar conexão. Sem aviso, parece
travamento.

## High-Level Technical Constraints

- **Integração obrigatória com o contrato compartilhado do workspace.** A evolução é aditiva:
  todo campo novo é opcional e nenhum campo existente muda de significado. Os Projetos 1 e 2
  precisam continuar válidos sem alteração.
- **Integração obrigatória com o frontend compartilhado.** Ele serve os dez projetos e
  renderiza controles a partir da descoberta de capacidades. Informação que um projeto não
  publica simplesmente não é exibida.
- **Continuidade com o Projeto 2.** Reescrita ciente do histórico, citação verificável,
  ausência de estado de conversa no servidor e os quatro entrypoints permanecem. A feature
  substitui o estágio de recuperação e não a arquitetura.
- **Desempenho, da perspectiva de quem usa.** A reordenação em processador comum custa da
  ordem de segundos, não de centésimos. Não há meta de latência; há obrigação de **medir e
  publicar** o custo por estágio. Ampliar a janela de candidatos precisa ter custo visível.
- **Reprodutibilidade.** Mesma pergunta, mesmos parâmetros e mesmo índice produzem o mesmo
  ranking. Medição que não repete não mede.
- **Privacidade e custo.** O estágio de reordenação roda localmente: nenhum trecho do corpus
  sai da máquina nele. O único segredo é a chave da API de modelo de linguagem, mantida fora
  do controle de versão.
- **Recursos da máquina.** O motor de busca consome da ordem de gigabytes de memória e
  convive com containers dos projetos anteriores. Um serviço por vez.

## Non-Goals (Out of Scope)

- **Substituibilidade do armazém como critério de aceite** (ADR-004). O Projeto 2 provava a
  abstração trocando o banco vetorial em uma linha. Aqui existe um motor único que atende os
  dois caminhos, e trocá-lo por um que só faz busca densa mataria a feature. O que permanece
  cobrado é a contenção do vocabulário do motor dentro dos adaptadores.
- **Delegar a fusão ao motor de busca.** Fundir à mão é o entendimento que o projeto existe
  para produzir, e mantém a estratégia de fusão independente de onde os dados estão.
- **Segunda implementação de reordenação por serviço hospedado.** Fica preparada pelo
  desenho, mas comparar qualidade, latência e custo contra um fornecedor pago é trabalho
  seguinte.
- **Execução concorrente dos dois caminhos de busca.** Decisão registrada, com critério
  objetivo de reabertura. Em produção seria a escolha errada; aqui, otimizar antes de medir é
  o hábito que o projeto quer desencorajar.
- **Corpus com identificadores de verdade.** O corpus inicial é herdado do Projeto 2 e não
  tem códigos. É pendência de validação declarada, não mudança de escopo: trocá-lo não custa
  uma linha de código.
- **Múltiplos usuários, autenticação, deploy e persistência de conversa no servidor.**
  Herdado do escopo do Projeto 2.
- **Logging estruturado.** Pendência herdada do Projeto 2 e não resolvida aqui.
- **Melhorias de qualidade vindas de trocar o modelo de linguagem ou o prompt de resposta.**
  A feature mexe no que entra na janela de contexto, e só nisso, para que o ganho seja
  atribuível.

## Architecture Decision Records

- [ADR-001: Reranking ligado por padrão em todos os caminhos](adrs/adr-001.md) — a latência
  do estágio é tratada como dado a publicar, não como problema a esconder.
- [ADR-002: Acerto definido por golden set com página esperada](adrs/adr-002.md) — critério
  objetivo e reprodutível, com a taxa de recusa mantida ao lado para comparar com o
  Projeto 2.
- [ADR-003: Procedência exposta no terminal e no frontend](adrs/adr-003.md) — a ordem final
  precisa ser explicável nos dois lugares onde o sistema é usado.
- [ADR-004: Substituibilidade do armazém sai de escopo](adrs/adr-004.md) — o critério herdado
  do Projeto 2 perdeu o contexto quando o armazém passou a atender dois caminhos.

Decisões estruturais anteriores, tomadas no HLD do projeto e vinculantes para esta feature,
estão em `docs/adrs/generated/RAG/` (ADR-001 a ADR-006).

## Open Questions

- **O corpus inicial produzirá contraste suficiente?** Harry Potter tem nomes próprios raros,
  onde a evidência publicada mostra que a busca léxica ganha, mas não tem códigos. A previsão
  é contraste modesto na linha de identificadores. Fica em aberto até a primeira medição, e a
  resposta é dado, não opinião.
- **Qual o custo real da reordenação nesta máquina?** A estimativa de 1 a 3 segundos vem de
  extrapolação linear sobre um benchmark de 2021 com hardware não especificado. A primeira
  execução substitui a estimativa por medição, e o ADR-001 pode ser revisto com ela.
- **Um adaptador para um segundo motor chega a existir neste projeto?** O ADR-004 tira a
  demonstração de escopo mas não decide se algum código de adaptação alternativa sobrevive.
  Decisão de implementação.
- **A verificação de saúde do motor de busca precisa de endpoint próprio.** Responder na raiz
  não é evidência de estado saudável, e a verificação herdada do Projeto 2 aprovaria um
  cluster degradado. Precisa ser resolvido no desenho técnico.
