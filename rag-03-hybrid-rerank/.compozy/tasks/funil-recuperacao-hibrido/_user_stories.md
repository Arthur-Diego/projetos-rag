# User Stories: Funil de recuperação híbrido

Catálogo canônico de comportamento da feature. Companion de `_prd.md`; consumido pelo FDD
(`docs/domains/rag/features/`) para mapeamento de componentes e pela matriz de testes.

## Personas

- **Autor-estudante** — o autor único do projeto, usando `ask.py` e `chat.py` no terminal
  para entender o mecanismo de recuperação. Precisa enxergar por que cada trecho chegou ali,
  não só qual trecho chegou. É quem paga a latência e quem julga se ela vale.
- **Operador da medição** — o mesmo autor com outro chapéu, rodando o harness que produz a
  tabela de 10 perguntas por 3 configurações. Precisa de resultado reprodutível: mesma
  entrada, mesma saída, sem julgamento humano no meio.
- **Consumidor do navegador** — quem usa o frontend compartilhado do workspace. Faz
  perguntas, lê a resposta e confere citação clicando. Não conhece o funil e não deveria
  precisar conhecer para confiar na citação.
- **Operador de infraestrutura** — o mesmo autor subindo e derrubando containers,
  reindexando e diagnosticando falha. Precisa distinguir "o pipeline está errado" de "a
  infraestrutura está fora do ar ou mal configurada".
- **Integrador do contrato** — os Projetos 1 e 2, que consomem o mesmo
  `docs/contracts/rag-api.yaml` e o mesmo frontend. Não participa desta feature e não pode
  ser quebrado por ela.

## Story Index

| ID | Feature Area | Persona | Story |
|---|---|---|---|
| US-001 | Ingestão | Operador de infraestrutura | Indexar o corpus num índice que atende os dois caminhos de busca |
| US-002 | Ingestão | Operador de infraestrutura | Receber relatório de ingestão comparável ao do Projeto 2 |
| US-003 | Ingestão | Operador de infraestrutura | Ter o corpus de controle preservado fora do índice |
| US-004 | Recuperação híbrida | Autor-estudante | Recuperar por dois caminhos independentes |
| US-005 | Recuperação híbrida | Autor-estudante | Ter os dois rankings fundidos por posição |
| US-006 | Recuperação híbrida | Autor-estudante | Ver o trecho de identificador exato ser recuperado |
| US-007 | Reranking | Autor-estudante | Ter os candidatos reordenados por precisão antes da geração |
| US-008 | Reranking | Consumidor do navegador | Continuar podendo confiar na citação depois da reordenação |
| US-009 | Parametrização | Autor-estudante | Ajustar os parâmetros do funil sem alterar código |
| US-010 | Parametrização | Consumidor do navegador | Descobrir os controles disponíveis sem ler documentação |
| US-011 | Observabilidade | Autor-estudante | Saber quanto custou cada estágio |
| US-012 | Observabilidade | Autor-estudante | Saber por que cada trecho está na posição em que está |
| US-013 | Medição | Operador da medição | Produzir a tabela das três configurações |
| US-014 | Medição | Operador da medição | Trocar o corpus sem tocar em código |
| US-015 | Diagnóstico | Operador de infraestrutura | Ser avisado quando o índice está mal mapeado |
| US-016 | Diagnóstico | Operador de infraestrutura | Distinguir infraestrutura fora do ar de índice vazio |
| US-017 | Compatibilidade | Integrador do contrato | Continuar funcionando sem alteração |

---

## Ingestão

### US-001: Indexar o corpus num índice que atende os dois caminhos

**Como** operador de infraestrutura, **quero** rodar a ingestão uma vez e obter um índice
que serve tanto a busca por significado quanto a busca por palavra exata, **para que** não
existam dois armazéns a manter sincronizados.

Acceptance criteria:

- AC-1: Dado o corpus em `pdfs/`, quando a ingestão roda até o fim, então cada trecho fica
  recuperável tanto por uma pergunta parafraseada quanto por um termo literal que aparece
  nele.
- AC-2: Dado que a ingestão terminou, quando se consulta o estado do índice, então o número
  de trechos indexados é único e não há dois totais divergentes a conciliar.
- AC-3: Dado um índice já existente, quando a ingestão roda de novo, então o índice anterior
  é descartado antes da leitura, e falha no meio deixa o índice vazio e não desatualizado.

Edge cases:

- EC-1 (Empty): pasta de PDFs vazia → a ingestão recusa antes de destruir o índice
  existente, com mensagem dizendo que não há o que indexar.
- EC-2 (Invalid input): PDF ilegível ou corrompido no meio do corpus → a página é
  descartada, o descarte é contado no relatório, e a ingestão continua.
- EC-3 (Interruption): processo interrompido no meio da escrita → o índice fica vazio ou
  parcial, e a consulta seguinte informa que é preciso reindexar, em vez de responder com
  corpus incompleto sem avisar.
- EC-4 (Repetition): ingestão rodada duas vezes seguidas sem mudança no corpus → o segundo
  resultado é equivalente ao primeiro, sem duplicar trechos.
- EC-5 (Scale): corpus com zero páginas úteis após descarte → relatório informa zero trechos
  e a consulta seguinte informa índice vazio.
- EC-6 (Concurrency): duas ingestões disparadas ao mesmo tempo → comportamento não é
  garantido; o projeto é de usuário único e isto fica registrado como limitação conhecida,
  não como caso tratado.

### US-002: Receber relatório de ingestão comparável ao do Projeto 2

**Como** operador de infraestrutura, **quero** que o relatório de ingestão mantenha os
mesmos números do Projeto 2, **para que** eu consiga comparar os dois projetos sobre o mesmo
corpus.

Acceptance criteria:

- AC-1: Dada uma ingestão bem sucedida, quando o relatório é exibido, então ele informa
  páginas lidas, páginas descartadas, trechos criados, trechos descartados do índice
  anterior, os parâmetros de divisão usados e o tempo total.
- AC-2: Dado um índice anterior com N trechos, quando a reindexação ocorre, então o número
  de trechos descartados reportado é N, contado antes da destruição.

Edge cases:

- EC-1 (Empty): primeira ingestão, sem índice anterior → trechos descartados é zero, e não
  um erro.
- EC-2 (Limits): parâmetros de divisão fora da faixa aceita → a ingestão recusa com
  mensagem que nomeia o parâmetro e a faixa, antes de tocar o índice.

### US-003: Ter o corpus de controle preservado fora do índice

**Como** operador de infraestrutura, **quero** que a pasta de controle nunca seja indexada,
**para que** o teste negativo de recusa continue significando alguma coisa.

Acceptance criteria:

- AC-1: Dado que existe documento na pasta de controle, quando a ingestão roda, então esse
  documento não aparece em nenhuma busca posterior.
- AC-2: Dada uma pergunta que só o documento de controle responderia, quando ela é feita em
  qualquer das três configurações, então o sistema recusa.

Edge cases:

- EC-1 (Ordering): documento movido para dentro da pasta principal por engano → passa a ser
  indexado, e o teste negativo falha de forma visível na medição, não em silêncio.
- EC-2 (Empty): pasta de controle vazia → a ingestão roda normalmente; o teste negativo é
  que fica sem material e deve reportar isso.

---

## Recuperação híbrida

### US-004: Recuperar por dois caminhos independentes

**Como** autor-estudante, **quero** que toda pergunta seja buscada por significado e por
palavra exata ao mesmo tempo, **para que** o acerto de um cubra a falha do outro.

Acceptance criteria:

- AC-1: Dada uma pergunta qualquer, quando a recuperação acontece, então dois conjuntos de
  candidatos são produzidos, um por caminho, cada um com sua própria ordem.
- AC-2: Dada uma pergunta cujo alvo é um termo literal presente no corpus, quando a
  recuperação acontece, então o caminho de palavra exata retorna o trecho que contém o
  termo.
- AC-3: Dada uma pergunta parafraseada, sem coincidência de vocabulário com o documento,
  quando a recuperação acontece, então o caminho por significado retorna o trecho
  pertinente.

Edge cases:

- EC-1 (Empty): um dos caminhos não retorna nada → a fusão prossegue com o outro, sem erro.
- EC-2 (Empty): nenhum dos caminhos retorna nada → o sistema recusa, e a recusa não carrega
  citação.
- EC-3 (Invalid input): pergunta vazia ou só com espaços → rejeitada antes da busca, com
  mensagem clara.
- EC-4 (Limits): pergunta muito longa → o comportamento é o mesmo de uma pergunta normal;
  se houver limite, ele é declarado e imposto, não implícito.
- EC-5 (Interruption): o motor de busca cai entre os dois caminhos → a requisição falha
  informando indisponibilidade de serviço, e não devolve resultado pela metade.
- EC-6 (Scale): corpus com um único trecho → os dois caminhos retornam o mesmo trecho e a
  fusão o entrega uma vez só.

### US-005: Ter os dois rankings fundidos por posição

**Como** autor-estudante, **quero** que os dois rankings sejam combinados pela posição e não
pelo valor, **para que** escalas incomparáveis não distorçam o resultado.

Acceptance criteria:

- AC-1: Dados dois rankings, quando a fusão ocorre, então o resultado depende apenas da
  posição de cada trecho em cada ranking, e não do valor bruto que cada caminho atribuiu.
- AC-2: Dado um trecho presente nos dois rankings, quando a fusão ocorre, então ele recebe
  a soma das duas contribuições e é promovido em relação a trechos presentes em um só.
- AC-3: Dado o mesmo par de rankings, quando a fusão roda de novo, então o resultado é
  idêntico.

Edge cases:

- EC-1 (Repetition): o mesmo trecho aparecendo duas vezes dentro do mesmo ranking → conta
  uma vez, pela melhor posição.
- EC-2 (Empty): os dois rankings vazios → resultado vazio, sem erro.
- EC-3 (Limits): parâmetro de amortecimento da fusão fora da faixa aceita → recusado com
  mensagem que nomeia o parâmetro e a faixa.
- EC-4 (Ordering): rankings de tamanhos diferentes → fundidos normalmente; o mais curto
  simplesmente contribui com menos entradas.
- EC-5 (Invalid input): dois trechos distintos com texto inicial idêntico → contados como
  distintos, porque a identidade vem do documento e não do prefixo do texto.

### US-006: Ver o trecho de identificador exato ser recuperado

**Como** autor-estudante, **quero** que perguntas sobre nomes próprios raros e termos
literais parem de falhar, **para que** eu veja o problema medido no Projeto 2 sendo
resolvido.

Acceptance criteria:

- AC-1: Dada uma pergunta sobre um termo raro presente no corpus, quando ela é feita na
  configuração só densa e depois na híbrida, então a híbrida recupera o trecho correto em
  pelo menos um caso em que a densa não recuperou.
- AC-2: Dado o conjunto de perguntas de identificador, quando as três configurações são
  comparadas, então o número de acertos da híbrida é maior ou igual ao da só densa.

Edge cases:

- EC-1 (Empty): termo perguntado que não existe no corpus → recusa, sem citação, nas três
  configurações.
- EC-2 (Scale): termo que aparece em dezenas de trechos → os candidatos são limitados pela
  janela configurada, e o corte é reportado e não silencioso.

---

## Reranking

### US-007: Ter os candidatos reordenados por precisão antes da geração

**Como** autor-estudante, **quero** que um modelo leia a pergunta junto de cada candidato e
reordene, **para que** o modelo de geração receba poucos trechos bem escolhidos em vez de
muitos trechos próximos.

Acceptance criteria:

- AC-1: Dada uma lista de candidatos fundidos, quando o reranking ocorre, então a ordem
  final reflete a pontuação do reordenador e não a ordem de entrada.
- AC-2: Dado o corte configurado, quando o reranking termina, então exatamente essa
  quantidade de trechos segue para a geração, ou menos, se houver menos candidatos.
- AC-3: Dado que o reranking está ligado por padrão, quando qualquer entrypoint é usado sem
  configuração explícita, então o estágio roda.

Edge cases:

- EC-1 (Empty): nenhum candidato após a fusão → o estágio é pulado e o sistema recusa.
- EC-2 (Limits): corte maior que o número de candidatos → entrega todos os candidatos, sem
  erro.
- EC-3 (Interruption): falha ao carregar o modelo de reordenação → a requisição informa
  indisponibilidade com mensagem que diz o que fazer, em vez de responder silenciosamente
  sem reordenar.
- EC-4 (Repetition): mesma pergunta e mesmos candidatos duas vezes → mesma ordem final.
- EC-5 (Scale): janela de candidatos ampliada ao máximo permitido → funciona, e o custo
  aparece medido em vez de travar sem explicação.
- EC-6 (Concurrency): duas requisições simultâneas ao serviço HTTP → cada uma recebe a
  própria ordenação, sem mistura de resultados.

### US-008: Continuar podendo confiar na citação depois da reordenação

**Como** consumidor do navegador, **quero** que o número da citação continue apontando para
o trecho certo mesmo com o funil reordenando tudo, **para que** conferir a fonte continue
significando alguma coisa.

Acceptance criteria:

- AC-1: Dada uma resposta com citações, quando cada citação é aberta, então a fonte e a
  página mostradas correspondem ao trecho que sustenta aquela afirmação.
- AC-2: Dada uma resposta de recusa, quando ela é exibida, então não há nenhuma citação
  junto.
- AC-3: Dado que o reranking alterou a ordem dos trechos, quando as citações são resolvidas,
  então nenhuma delas muda de alvo por causa da reordenação.

Edge cases:

- EC-1 (Invalid input): o modelo cita um número que não existe entre os trechos enviados →
  o rótulo é reportado como não resolvido, sem inventar fonte.
- EC-2 (Ordering): dois trechos da mesma página entre os finais → cada citação aponta para o
  trecho correto, e não para o primeiro da página.
- EC-3 (Empty): resposta sem nenhuma citação, mas sem recusa → aceito, e a ausência é
  visível.

---

## Parametrização e descoberta

### US-009: Ajustar os parâmetros do funil sem alterar código

**Como** autor-estudante, **quero** mudar a janela de candidatos, o amortecimento da fusão e
o corte final por linha de comando ou por requisição, **para que** varrer parâmetros seja
barato.

Acceptance criteria:

- AC-1: Dado qualquer dos três parâmetros do funil, quando informado no terminal ou na
  requisição, então ele é aplicado naquela execução e o valor usado é observável na saída.
- AC-2: Dado um valor fora da faixa aceita, quando informado, então a execução é recusada
  com mensagem que nomeia o parâmetro, o valor recebido e a faixa válida.
- AC-3: Dado nenhum valor informado, quando a execução ocorre, então o padrão declarado é
  usado, e é o mesmo padrão publicado na descoberta de capacidades.

Edge cases:

- EC-1 (Invalid input): valor não numérico onde se espera número → recusado com mensagem, e
  não convertido em silêncio para o padrão.
- EC-2 (Limits): valor no limite exato da faixa → aceito; a faixa é inclusiva e isso é
  declarado.
- EC-3 (Limits): corte final maior que a janela de candidatos → recusado, porque pedir mais
  finais do que candidatos é contradição de configuração.
- EC-4 (Ordering): parâmetro do funil informado numa chamada de ingestão, onde não se aplica
  → ignorado ou recusado de forma declarada, nunca aplicado por engano.

### US-010: Descobrir os controles disponíveis sem ler documentação

**Como** consumidor do navegador, **quero** que a interface mostre sozinha os controles do
funil, **para que** eu compare configurações sem editar arquivo nenhum.

Acceptance criteria:

- AC-1: Dado o serviço no ar, quando a interface carrega, então os controles dos parâmetros
  do funil aparecem, com rótulo legível, ajuda curta, padrão e faixa.
- AC-2: Dada a escolha da configuração de recuperação, quando ela é alterada na interface,
  então a próxima pergunta usa a configuração escolhida.
- AC-3: Dado um limite declarado na descoberta, quando um valor acima dele é enviado, então
  o serviço recusa, e não apenas a interface.

Edge cases:

- EC-1 (Interruption): motor de busca fora do ar → a descoberta de capacidades continua
  respondendo, porque ela não depende da infraestrutura de dados.
- EC-2 (Permissions): não se aplica; o serviço é local, sem autenticação, e isso está
  declarado como fora de escopo.

---

## Observabilidade

### US-011: Saber quanto custou cada estágio

**Como** autor-estudante, **quero** o tempo de cada estágio separado, **para que** eu
atribua a lentidão ao estágio certo e responda quanto custa ampliar a janela.

Acceptance criteria:

- AC-1: Dada uma resposta, quando os tempos são exibidos, então há valor separado para
  reescrita, busca densa, busca por palavra exata, fusão, reordenação e geração.
- AC-2: Dado que um estágio não rodou naquela configuração, quando os tempos são exibidos,
  então o valor daquele estágio está ausente, e não zerado como se tivesse rodado
  instantaneamente.
- AC-3: Dada uma janela de candidatos ampliada, quando a mesma pergunta é repetida, então a
  diferença de custo aparece no tempo do estágio de reordenação.

Edge cases:

- EC-1 (Interruption): falha no meio do turno → os tempos dos estágios que completaram
  continuam disponíveis no erro, quando possível, ou a ausência é explícita.
- EC-2 (Empty): recusa por ausência de candidatos → os tempos dos estágios que rodaram são
  reportados normalmente.

### US-012: Saber por que cada trecho está na posição em que está

**Como** autor-estudante, **quero** ver a procedência de cada trecho recuperado, **para que**
a ordem final seja explicável em vez de mágica.

Acceptance criteria:

- AC-1: Dado um trecho entre os finais, quando ele é exibido no terminal ou no navegador,
  então mostra de qual caminho ou caminhos veio, a posição em cada ranking, o valor da fusão
  e o valor da reordenação.
- AC-2: Dado um trecho encontrado pelos dois caminhos, quando ele é exibido, então essa
  condição é distinguível de um trecho encontrado por um só.
- AC-3: Dada a configuração só densa, quando os trechos são exibidos, então a informação de
  proximidade continua com o mesmo significado que tinha no Projeto 2.

Edge cases:

- EC-1 (Empty): configuração sem reordenação → o valor de reordenação está ausente e a
  interface não mostra campo vazio.
- EC-2 (Invalid input): valor de proximidade e valor de fusão têm escalas opostas, uma em
  que menor é melhor e outra em que maior é melhor → nunca são exibidos no mesmo campo, e o
  rótulo de cada um diz qual é qual.

---

## Medição

### US-013: Produzir a tabela das três configurações

**Como** operador da medição, **quero** rodar um comando e obter a tabela pronta, **para
que** o entregável do projeto exista sem trabalho manual repetido.

Acceptance criteria:

- AC-1: Dado o conjunto de perguntas anotadas, quando o harness roda, então ele produz a
  tabela com as 10 perguntas divididas entre conceituais e de identificador, contra as três
  configurações.
- AC-2: Dada uma pergunta e uma configuração, quando o resultado é computado, então acerto
  significa que um trecho de página esperada apareceu entre os finais entregues ao modelo.
- AC-3: Dada a tabela, quando ela é lida, então a taxa de recusa aparece ao lado dos
  acertos, permitindo comparação com o Projeto 2.
- AC-4: Dado o mesmo corpus e as mesmas perguntas, quando o harness roda de novo, então a
  tabela é a mesma.

Edge cases:

- EC-1 (Empty): arquivo de perguntas vazio → o harness recusa com mensagem, e não imprime
  tabela vazia como se fosse resultado.
- EC-2 (Invalid input): pergunta anotada com página que não existe no PDF → o harness
  reporta a anotação inválida e não conta a pergunta como erro do sistema.
- EC-3 (Interruption): falha no meio da varredura → o resultado parcial é identificado como
  parcial, nunca apresentado como tabela completa.
- EC-4 (Limits): o harness gasta chamadas pagas → o cabeçalho declara isso antes de rodar.
- EC-5 (Scale): conjunto de perguntas ampliado para muito além de 10 → funciona; o número 10
  é do exercício, não do harness.

### US-014: Trocar o corpus sem tocar em código

**Como** operador da medição, **quero** que trocar o PDF e as perguntas seja edição de
arquivo de dados, **para que** a pendência do corpus sem códigos seja resolvível depois sem
retrabalho.

Acceptance criteria:

- AC-1: Dado um corpus novo e um arquivo de perguntas novo, quando a ingestão e o harness
  rodam, então a tabela é produzida sem nenhuma alteração de código.
- AC-2: Dado que as perguntas vivem em arquivo de dados, quando o arquivo é aberto, então é
  legível e editável sem conhecimento do código.

Edge cases:

- EC-1 (Invalid input): arquivo de perguntas malformado → recusado com mensagem que aponta a
  linha ou entrada problemática.
- EC-2 (Ordering): corpus trocado sem reindexar → a medição roda contra o índice antigo; o
  harness deve tornar isso perceptível, comparando o que está indexado com o que deveria
  estar.

---

## Diagnóstico

### US-015: Ser avisado quando o índice está mal mapeado

**Como** operador de infraestrutura, **quero** que o sistema me avise se o campo de texto do
índice não estiver preparado para busca por palavra exata, **para que** eu não conclua que a
busca híbrida não ajuda quando na verdade metade dela nunca rodou.

Acceptance criteria:

- AC-1: Dado um índice cujo campo de texto não está preparado para análise de termos, quando
  a verificação de saúde roda, então ela reporta a divergência com mensagem que diz como
  corrigir.
- AC-2: Dado um índice corretamente preparado, quando a verificação roda, então ela passa
  sem ruído.
- AC-3: Dado o índice recém criado pela ingestão, quando ele é inspecionado, então o
  preparo do campo foi definido explicitamente pelo sistema, e não inferido pelo motor.

Edge cases:

- EC-1 (Empty): índice inexistente → não é erro de mapeamento; é índice vazio, e a mensagem
  correspondente é a de índice vazio.
- EC-2 (Ordering): índice criado por outra ferramenta, fora da ingestão → a verificação
  detecta e reporta, porque é exatamente o caso que ela existe para pegar.
- EC-3 (Invalid input): busca por termo literal conhecido do corpus não retorna nada → sinal
  de mapeamento errado, e a validação do projeto inclui essa verificação de fumaça.

### US-016: Distinguir infraestrutura fora do ar de índice vazio

**Como** operador de infraestrutura, **quero** que falha de serviço e ausência de dados
tenham mensagens e efeitos diferentes, **para que** eu não procure defeito no lugar errado.

Acceptance criteria:

- AC-1: Dado o motor de busca fora do ar, quando uma pergunta é feita, então a resposta
  informa indisponibilidade de serviço e diz como subir o container.
- AC-2: Dado o motor no ar e o índice vazio, quando uma pergunta é feita, então a resposta
  informa que é preciso indexar, e é distinguível do caso anterior.
- AC-3: Dado o motor no ar mas degradado, quando a verificação de saúde roda, então ela não
  aprova o estado como saudável.

Edge cases:

- EC-1 (Interruption): o motor cai no meio da requisição, depois de a verificação ter
  passado → a resposta informa indisponibilidade, e não índice vazio.
- EC-2 (Invalid input): dimensão do modelo de embedding divergente da do índice → reportado
  como configuração inconsistente, com a receita de reindexação.
- EC-3 (State transitions): índice apagado enquanto o serviço está no ar → a próxima
  pergunta informa índice vazio, e não erro genérico.

---

## Compatibilidade

### US-017: Continuar funcionando sem alteração

**Como** integrador do contrato, isto é, os Projetos 1 e 2, **quero** que a evolução do
contrato compartilhado e do frontend não me quebre, **para que** eu continue rodando e
servindo de linha de base para comparação.

Acceptance criteria:

- AC-1: Dado o contrato atualizado, quando os Projetos 1 e 2 são executados sem alteração,
  então eles continuam válidos contra ele.
- AC-2: Dado o frontend atualizado, quando ele é apontado para os Projetos 1 ou 2, então ele
  renderiza normalmente e omite a informação de funil que aqueles projetos não publicam.
- AC-3: Dado um campo que existia antes, quando ele continua sendo publicado por um projeto
  antigo, então seu significado não mudou.

Edge cases:

- EC-1 (Empty): projeto que não publica nenhum campo novo → nenhuma coluna ou seção vazia
  aparece na interface.
- EC-2 (State transitions): campo marcado como obsoleto → continua aceito e continua
  documentado com o significado que sempre teve, em vez de removido.
