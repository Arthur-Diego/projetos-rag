### FDD: Pipeline de RAG sobre PDF

Versão: 1.0
Data: 2026-07-25
Responsável: arthu

PRD de referência: [`docs/prd.md`](../../../prd.md)
HLD do domínio: [`docs/domains/rag/hld.md`](../hld.md)

---

### 1. Contexto e motivação técnica

O domínio `rag` existe hoje apenas como documentação. Esta feature entrega o código que
realiza o pipeline descrito no HLD: carregar PDFs, dividir em chunks, gerar embeddings,
persistir na coleção do Chroma, recuperar por similaridade e gerar resposta fundamentada.

O problema técnico não é fazer o pipeline funcionar, e sim tornar cada estágio
observável. Um RAG que responde certo sem que se saiba de onde veio a resposta é
indistinguível de um modelo respondendo de memória. A feature precisa produzir, a cada
consulta, evidência suficiente para responder: a busca trouxe o material certo? A geração
usou esse material?

Encaixe no HLD: implementa os dois componentes clientes (`ingest.py` e `ask.py`) contra o
serviço Chroma já declarado em `docker-compose.yml`. Não introduz componente novo na
arquitetura.

**Atores**
- Usuário único, operando por linha de comando.
- Serviço Chroma, na porta 8000 do host.
- API da OpenAI, para embeddings e geração.

**Restrições herdadas de ADRs** (nenhuma pode ser violada sem novo ADR)
- ADR-001: acesso ao Chroma por `chromadb.HttpClient`, nunca `PersistentClient`.
- ADR-002: `text-embedding-3-small` (1536 dimensões) e `gpt-4o-mini` (temperatura 0).
- ADR-003: dois scripts independentes, sem módulo compartilhado entre eles.
- ADR-004: glob `pdfs/*.pdf` não recursivo. `pdfs/fora-do-corpus/` jamais indexado.
- HLD: sem limiar de similaridade nesta entrega (decisão adiada para o Projeto 5).

**Suposições**
- O serviço Chroma está no ar antes de qualquer script rodar. Os scripts verificam e
  falham cedo, mas não sobem o container.
- O corpus cabe em memória durante a ingestão (274 páginas, cerca de 800 chunks).

---

### 2. Objetivos técnicos

- **Indexação completa e reprodutível.** `ingest.py` processa todos os PDFs de `pdfs/` e
  reporta a razão páginas para chunks. Invariante: duas execuções seguidas com os mesmos
  parâmetros produzem a mesma contagem de chunks, nunca o dobro.
- **Recuperação com procedência.** Toda resposta vem acompanhada dos chunks usados, com
  arquivo de origem, página e distância. Invariante: o número de chunks exibidos é igual
  ao `k` efetivo da consulta.
- **Diagnóstico por estágio.** Latência de busca e latência de geração medidas e exibidas
  separadamente, permitindo atribuir lentidão ao estágio certo.
- **Recusa verificável.** Pergunta sem cobertura no índice produz a frase de escape
  exata, não uma resposta plausível. Invariante: a frase de escape é literal e única, de
  modo que sua presença possa ser verificada por comparação de string.
- **Falha antes do custo.** Toda pré-condição (chave, serviço, corpus) é verificada antes
  da primeira chamada paga à API.

---

### 3. Escopo e exclusões

**Incluído**
- `ingest.py` com `--chunk-size` (default 1000) e `--chunk-overlap` (default 150).
- `ask.py` com `--k` (default 4), em dois modos: REPL sem argumento, resposta única com
  argumento posicional.
- Recriação da coleção a cada ingestão, com aviso de quantos chunks foram descartados.
- Preservação de `source` e `page` nos metadados de cada chunk.
- Exibição de chunks recuperados com distância e das latências por estágio.
- Verificações de pré-voo com mensagens acionáveis.
- Prompt com instrução de fundamentação e frase de escape literal.

**Excluído**
- Limiar de similaridade (HLD, decisão adiada para o Projeto 5).
- Memória de conversa entre perguntas e citações numeradas (Projeto 2).
- Busca híbrida, BM25 e reranking (Projeto 3).
- Extração de tabelas e imagens, e suporte a PDF escaneado (Projeto 4).
- Avaliação automatizada com RAGAS (Projeto 3 em diante).
- Testes automatizados de integração contra a API paga. Ver seção 9.
- Módulo compartilhado entre os scripts (ADR-003).
- Qualquer interface de rede própria.

---

### 4. Fluxos detalhados e diagramas

**Fluxo principal**

Estágio de ingestão, executado uma vez por configuração de corpus:

1. Carregar `.env` e validar `OPENAI_API_KEY`. Ausente, encerrar com código 1.
2. Verificar o serviço Chroma por `GET /api/v2/heartbeat`. Sem resposta, encerrar com
   código 1 e instrução de subir o container.
3. Listar `pdfs/*.pdf` com glob não recursivo. Lista vazia, encerrar com código 1.
4. Para cada PDF, extrair uma `Document` por página, preservando `source` e `page`.
5. Descartar páginas sem texto útil, avisando quantas foram. Se nenhum PDF produziu
   texto, encerrar com código 1 apontando a hipótese de PDF escaneado.
6. Se a coleção existe, reportar quantos chunks ela tinha e apagá-la antes de prosseguir.
7. Dividir em chunks com `RecursiveCharacterTextSplitter`, herdando os metadados.
8. Enviar em lotes para embedding e gravar na coleção. Este é o único estágio pago.
9. Reportar páginas de entrada, chunks de saída e tempo total.

Estágio de consulta, executado muitas vezes:

1. Carregar `.env` e validar a chave. Verificar o serviço Chroma.
2. Abrir a coleção e reportar a contagem de chunks. Coleção ausente ou vazia, encerrar
   com código 1 orientando a rodar a ingestão.
3. Obter a pergunta, do argumento posicional ou do laço interativo.
4. Gerar o embedding da pergunta e recuperar os `k` chunks mais próximos, com distância.
5. Montar o prompt: instrução de fundamentação, frase de escape, contexto numerado,
   pergunta.
6. Chamar o modelo com temperatura 0.
7. Escrever a resposta em stdout; escrever chunks, distâncias e latências em stderr.
8. No modo REPL, voltar ao passo 3 reaproveitando cliente e coleção já abertos.

**Fluxos alternativos e exceções**
- Pergunta vazia no REPL: reexibir o prompt sem consumir chamada de API.
- `\q`, `sair`, EOF (Ctrl+D) ou Ctrl+C no REPL: encerrar com código 0, sem traceback.
- PDF individual sem texto: avisar, pular o arquivo e continuar com os demais.
- Erro transitório da OpenAI (429 ou 5xx): reter com espera exponencial, até 3
  tentativas. Esgotadas, encerrar com código 1.
- Erro de autenticação (401): encerrar imediatamente, sem retentativa. Retentar não
  conserta chave inválida, apenas atrasa o diagnóstico.

**Diagramas**
- Fluxo de ingestão e fluxo de consulta em `docs/domains/rag/diagrams/mermaid/`.

---

### 5. Contratos públicos

**Contrato 1: `ingest.py`**

- Tipo: interface de linha de comando
- Assinatura: `python ingest.py [--chunk-size N] [--chunk-overlap N]`
- Parâmetros:
  - `--chunk-size` (int, default 1000): caracteres por chunk.
  - `--chunk-overlap` (int, default 150): caracteres repetidos entre chunks vizinhos.
    Precisa ser menor que `--chunk-size`, validado antes de qualquer trabalho.
- Semântica de saída:
  - stdout: relatório de contagens.
  - stderr: avisos e diagnóstico.
  - código 0: indexação concluída.
  - código 1: qualquer pré-condição não atendida ou falha de indexação.

**Exemplo de execução**

```
$ python ingest.py
chroma: ok (http://localhost:8000)
colecao 'livros' ja existe com 617 chunks, recriando do zero
lendo pdfs/j-k-rowling-1-harry-potter-e-a-pedra-filosofal.pdf
274 paginas -> 617 chunks (tamanho 1000, sobreposicao 150)
indexado em 8.2s
```

**Contrato 2: `ask.py`**

- Tipo: interface de linha de comando
- Assinatura: `python ask.py [pergunta] [--k N]`
- Parâmetros:
  - `pergunta` (str, opcional): sem ela, entra em modo REPL.
  - `--k` (int, default 4): quantos chunks recuperar.
- Semântica de saída:
  - stdout: apenas a resposta do modelo, permitindo redirecionamento limpo.
  - stderr: chunks recuperados, distâncias, latências e mensagens de estado.
  - código 0: consulta respondida, ou REPL encerrado pelo usuário.
  - código 1: pré-condição não atendida.

**Exemplo de execução**

```
$ python ask.py "Segundo o sumario, qual e o titulo do Capitulo Seis?"
chroma: ok | colecao 'livros': 617 chunks | k=4
busca 0.31s | geracao 1.12s | 4 chunks

O Embarque na plataforma 9 e ½

  [1] j-k-rowling-1-harry-potter-e-a-pedra-filosofal.pdf p.2  dist 0.875
  [2] j-k-rowling-1-harry-potter-e-a-pedra-filosofal.pdf p.41  dist 0.914
  [3] j-k-rowling-1-harry-potter-e-a-pedra-filosofal.pdf p.3  dist 0.930
  [4] j-k-rowling-1-harry-potter-e-a-pedra-filosofal.pdf p.1  dist 0.944
```

A métrica exibida é **distância**, não similaridade: menor significa mais próximo. O
Chroma devolve distância, e chamar isso de score inverteria a leitura. A saída imprime a
legenda para não deixar dúvida.

As páginas são exibidas a partir de 1. O `PyPDFLoader` numera a partir de zero, e a
conversão acontece só na exibição.

**Frase de escape (contrato literal)**

O prompt instrui o modelo a responder exatamente:

```
Não encontrei essa informação nos documentos.
```

A literalidade é contratual: os critérios de aceite 3 e 4 verificam a recusa por
comparação de string, não por interpretação.

**Detalhe de implementação que a validação obrigou a registrar:** a frase aparece no
template do prompt **sem aspas**. Na primeira versão ela estava entre aspas, e o modelo
copiou as aspas para a resposta, quebrando a comparação literal. Envolver a frase em
qualquer delimitador reintroduz o defeito.

---

### 6. Erros, exceções e fallback

**Matriz de erros**

| Condição | Tratamento | Observações |
| --- | --- | --- |
| `OPENAI_API_KEY` ausente ou vazia | Encerrar com código 1 antes de qualquer chamada, citando `.env.example` | Verificado na primeira linha útil |
| Serviço Chroma inacessível | Encerrar com código 1, instruindo `docker compose up -d chroma` | Verificado por heartbeat, não por exceção de biblioteca |
| `pdfs/` sem nenhum `.pdf` | Encerrar com código 1 | Só na ingestão |
| PDF individual sem texto extraível | Avisar em stderr, pular o arquivo, continuar | Hipótese provável: PDF escaneado, tema do Projeto 4 |
| Nenhum PDF produziu texto | Encerrar com código 1 apontando a hipótese de PDF escaneado | Evita coleção vazia silenciosa |
| `--chunk-overlap` maior ou igual a `--chunk-size` | Encerrar com código 1 antes de ler qualquer PDF | Combinação gera divisão infinita |
| Coleção ausente ou vazia na consulta | Encerrar com código 1, orientando rodar `ingest.py` | Evita busca contra o vazio |
| OpenAI 429 ou 5xx | Até 3 tentativas com espera exponencial. Esgotadas, código 1 | Erro transitório |
| OpenAI 401 | Encerrar imediatamente, sem retentativa | Retentar não conserta chave inválida |
| Ctrl+C ou EOF no REPL | Encerrar com código 0, sem traceback | Encerramento é uso normal, não falha |
| Pergunta vazia no REPL | Reexibir o prompt | Não consome chamada de API |

**Estratégias de resiliência**
- Retentativa com espera exponencial apenas para erro transitório de API.
- Verificação de pré-condição antes de qualquer operação paga.
- Nenhum timeout customizado nas chamadas à OpenAI nesta entrega: o default do cliente
  oficial é suficiente para um único usuário.

**Política de fallback**
- Não existe fallback de fonte. Se a recuperação não traz material suficiente, o
  comportamento correto é a frase de escape, não uma busca alternativa. Fallback para web
  é o Projeto 5.

**Invariantes**
- `pdfs/fora-do-corpus/` nunca é lido pela ingestão. O glob é `pdfs/*.pdf`.
- A coleção contém exclusivamente vetores de 1536 dimensões.
- Duas ingestões consecutivas com os mesmos parâmetros produzem a mesma contagem de
  chunks.
- stdout carrega apenas o resultado; todo diagnóstico vai para stderr.
- Todo chunk carrega `source` e `page` nos metadados.

---

### 7. Observabilidade

**Métricas**
- Ingestão: páginas lidas, páginas descartadas por ausência de texto, chunks gerados,
  chunks descartados da coleção anterior, tempo total.
- Consulta: latência de busca, latência de geração, `k` efetivo, distância de cada chunk.

**Logs**
- Texto legível em stderr, não JSON. A cardinalidade de um usuário único não justifica
  estrutura, e o destino é o terminal.
- Campos essenciais por consulta: origem, página e distância de cada chunk recuperado.
- A chave da API nunca aparece em log, nem parcialmente.

**Tracing**
- Não se aplica. Não há sistema distribuído. LangSmith permanece disponível por variáveis
  de ambiente, sem alteração de código, e passa a valer a pena no Projeto 5.

**Dashboards e alertas**
- Nenhum. O painel de uso da OpenAI e um limite de gasto mensal na conta cobrem a única
  métrica que exige acompanhamento.

---

### 8. Dependências e compatibilidade

| Componente | Versão mínima | Observações |
| --- | --- | --- |
| Python | 3.12.3 | Instalado. `pip` só existe dentro do venv |
| langchain | 1.3.14 | Estilo v1, LCEL. Chains legadas foram para `langchain-classic` |
| langchain-openai | 1.4.1 | `OpenAIEmbeddings` e `ChatOpenAI` |
| langchain-text-splitters | 1.1.2 | `RecursiveCharacterTextSplitter` |
| langchain-chroma | 1.1.0 | Exige `chromadb` completo (`>=1.3.5,<2.0.0`) |
| langchain-community | 0.4.2 | `PyPDFLoader`. Em sunset, emite `DeprecationWarning` esperado |
| pypdf | 6.14.2 | Backend do `PyPDFLoader` |
| python-dotenv | 1.2.2 | Carga do `.env` |
| chromadb/chroma (imagem) | 1.5.9 | API v2. A v1 responde `410 Gone` |
| Docker Compose | v2.40.3 | Verificado no ambiente |

**Garantias de compatibilidade**
- Cliente e servidor Chroma devem permanecer na mesma linha de versão (1.5.x). O
  `chromadb` do PyPI está em 1.5.9, coincidindo com a tag da imagem.
- Mudança do modelo de embedding invalida a coleção inteira e exige reindexação. Não
  existe migração entre espaços vetoriais.
- Os `DeprecationWarning` de `langchain-community` são esperados e não indicam erro.

---

### 9. Critérios de aceite técnicos

1. `python ingest.py` conclui com código 0 e reporta páginas de entrada e chunks de
   saída, com o número de chunks maior que o de páginas.
2. `python ingest.py` executado duas vezes seguidas com os mesmos parâmetros reporta a
   mesma contagem de chunks na segunda execução, provando que recriou em vez de duplicar.
3. `python ask.py "<pergunta sobre a edicao>"` responde corretamente e exibe 4 chunks com
   origem, página e distância. A pergunta deve ser sobre a edição em PDF (página, sumário,
   grafia da tradução), nunca sobre o enredo, porque o modelo conhece o enredo do treino.
4. **Teste negativo de grounding.** `python ask.py "<pergunta sobre 1 Corintios>"` retorna
   a frase de escape literal. O corpus de controle está fora do índice por construção
   (ADR-004), portanto o modelo tem incentivo máximo para alucinar e precisa se recusar.
   Este é o critério mais importante da feature.
5. `python ingest.py --chunk-size 200` e `--chunk-size 4000` produzem contagens de chunks
   claramente diferentes, e a mesma pergunta nas três configurações produz contextos
   visivelmente distintos. O entregável é a observação anotada, não apenas a execução.
6. Com o serviço Chroma parado, ambos os scripts encerram com código 1 e mensagem que
   nomeia o comando de correção, sem traceback de biblioteca.
7. Sem `OPENAI_API_KEY`, ambos os scripts encerram com código 1 antes de qualquer chamada
   de rede.
8. `python ask.py "pergunta" > /tmp/saida.txt` grava apenas a resposta no arquivo, com o
   diagnóstico permanecendo no terminal.

Testes automatizados contra a API paga estão fora de escopo (seção 3). A validação destes
critérios é por execução manual com evidência registrada.

---

### 10. Riscos e mitigação

### Ingestão duplicada por reexecução

- **Probabilidade:** alta se o comportamento fosse acrescentar
- **Impacto:** alto e silencioso. Chunks duplicados fazem `k=4` retornar quatro cópias do
  mesmo trecho, reduzindo o contexto efetivo a um único chunk sem nenhum aviso.
- **Mitigação:**
  - Recriar a coleção a cada ingestão, por decisão de desenho.
  - Reportar quantos chunks foram descartados, tornando a recriação visível.
  - Critério de aceite 2 verifica a invariante explicitamente.
- **Plano de contingência:** apagar a coleção e reindexar.

### Corpus de controle indexado por engano

- **Probabilidade:** média
- **Impacto:** crítico. Destrói o teste negativo de grounding em silêncio, sem erro nem
  aviso, e o projeto perde sua principal garantia de correção.
- **Mitigação:**
  - Glob `pdfs/*.pdf` não recursivo, com comentário no cabeçalho do arquivo explicando o
    porquê.
  - ADR-004 e nota no `CLAUDE.md`.
  - `ingest.py` lista os arquivos que vai indexar antes de começar, permitindo notar a
    presença indevida.
- **Plano de contingência:** reindexar após corrigir o glob.

### Falha de infraestrutura confundida com falha do pipeline

- **Probabilidade:** média
- **Impacto:** médio. Serviço parado produz erro de conexão que, para quem aprende RAG, é
  indistinguível de erro de código. Risco herdado do ADR-001 e aceito conscientemente.
- **Mitigação:**
  - Heartbeat explícito no pré-voo, antes de qualquer outra coisa.
  - Mensagem que nomeia o comando de correção, em vez de propagar exceção da biblioteca.
  - Critério de aceite 6 verifica esse comportamento.
- **Plano de contingência:** `docker compose up -d chroma` e conferir `docker compose logs`.

### Consumo de crédito por reindexação repetida

- **Probabilidade:** média
- **Impacto:** baixo. Recriar sempre significa que toda execução de `ingest.py` custa
  chamadas de embedding, e o experimento do critério 5 exige várias.
- **Mitigação:**
  - Reportar o tempo e a contagem, tornando o custo perceptível.
  - Limite de gasto mensal configurado na conta.
- **Plano de contingência:** experimentar sobre um subconjunto do corpus.

---

### 11. Sequenciamento de implementação (Build Order)

| Ordem | Etapa | Depende de | Componentes/arquivos | Critérios que fecha |
| --- | --- | --- | --- | --- |
| 1 | Base: exceções, propriedades e objetos de valor | - | `rag/exceptions.py`, `rag/config.py`, `rag/domain/models.py` | 7 |
| 2 | Repositórios: leitura de arquivos e de vetores | 1 | `rag/repository/` | 1, 2 |
| 3 | Serviços: saúde, divisão, recuperação, prompt, geração | 1, 2 | `rag/service/` | 1, 3, 4, 6 |
| 4 | Facades: os dois casos de uso, sem terminal | 2, 3 | `rag/facade/` | 1, 2, 3, 4 |
| 5 | Apresentação: stdout x stderr e procedência | 1 | `rag/presenter/console_reporter.py` | 3, 8 |
| 6 | Composition roots: argparse e montagem do grafo | 4, 5 | `ingest.py`, `ask.py` | 6, 7 |
| 7 | Validação de grounding e experimento de chunking | 6 | execução manual, seção 12 | 4, 5 |

Esta seção foi reescrita três vezes: pelo ADR-005, que superou o ADR-003 e segregou o
pipeline; pelo ADR-006, que nomeou as camadas; e pelo ADR-007, que extraiu o caso de uso
dos entrypoints. A primeira versão tinha 8 etapas sobre
dois scripts autocontidos e registrava 47 linhas de duplicação como consequência aceita.
Essa duplicação deixou de existir.

O grafo de dependências entre os módulos está em
`docs/domains/rag/diagrams/mermaid/componentes.mmd`, extraído do código por AST, e o C4
nível 3 em `docs/domains/rag/diagrams/c4/componente.puml`.

---

### 12. Registro de validação

Executado em 25/07/2026, contra o corpus real, com o serviço Chroma no ar. Os critérios 3
e 5 exigem observação anotada, não apenas execução; é o que esta seção entrega.

**Situação dos critérios**

| # | Critério | Situação | Evidência |
| --- | --- | --- | --- |
| 1 | Ingestão conclui e reporta contagens | atendido | `274 páginas -> 617 chunks`, código 0, em 8.2s |
| 2 | Reingestão não duplica | atendido | Segunda execução: `coleção 'livros' tinha 617 chunks, recriada do zero`. Contagem conferida direto no Chroma: 617, não 1234. Texto atualizado pelo ADR-007 |
| 3 | Pergunta sobre a edição respondida com procedência | atendido com ressalva | Ver "Limite descoberto" abaixo |
| 4 | Teste negativo de grounding | atendido | Resposta byte a byte idêntica à frase de escape, em duas perguntas sobre 1 Coríntios |
| 5 | Experimento de chunking | atendido | Tabela abaixo |
| 6 | Serviço parado produz mensagem acionável | atendido | Código 1, texto nomeando `docker compose up -d chroma`, sem traceback |
| 7 | Chave ausente encerra antes da rede | atendido | Código 1 nos dois scripts, antes de qualquer chamada |
| 8 | Redirecionamento de stdout leva só a resposta | atendido | Arquivo com 1 linha, zero ocorrências de diagnóstico; stderr com 6 |

**Experimento de chunking (critério 5)**

Mesma pergunta ("Segundo o sumário, qual é o título do Capítulo Seis?") nas três
configurações:

| chunk_size | overlap | chunks | Melhor distância | Página recuperada | Resposta |
| --- | --- | --- | --- | --- | --- |
| 200 | 30 | 2950 | **0.784** | p.1 | correta |
| 1000 | 150 | 617 | 0.875 | p.2 | correta |
| 4000 | 600 | 274 | 0.880 | p.2 | correta |

Duas observações que o experimento produziu:

1. **Com 4000 saíram exatamente 274 chunks para 274 páginas.** Nenhuma página deste PDF
   chega a 4000 caracteres, então o divisor não dividiu nada: o chunk virou a página.
   Aumentar o parâmetro além do tamanho da página não tem efeito algum.
2. **O chunk de 200 recuperou o sumário melhor que os maiores** (0.784 contra 0.875).
   Uma linha de sumário é uma unidade curta e autocontida de significado; diluí-la em 1000
   caracteres de texto vizinho piora o embedding dela. Chunk pequeno favorece consulta
   pontual e prejudica pergunta que exige contexto ao redor. Este é o trade-off central
   do parâmetro, e ele depende da pergunta, não apenas do documento.

**Limite descoberto (critério 3)**

A pergunta "Como está grafado o nome da autora no sumário deste documento?" **falhou**, e
a falha é da recuperação, não da geração. O gabarito existe: esta edição grafa "Joanne K.
Rowlling", com dois L, e o modelo jamais produziria isso de memória. Mas a busca trouxe as
páginas 174 e 38, nunca a página 1.

Causa: é uma **meta-pergunta**, sobre o documento e não sobre o conteúdo dele. O embedding
de "como está grafado o nome da autora" não se aproxima do embedding de uma página que é
uma lista de títulos de capítulo. Busca densa compara significado, e a página do sumário
não significa "nome da autora".

O comportamento observado é o correto: o sistema recusou em vez de responder "J.K.
Rowling" por conhecimento próprio. Um RAG que errasse aqui teria falhado de forma pior.

Registrado como limitação conhecida, não como defeito. As técnicas que a endereçam são
reescrita de consulta (Projeto 2), busca híbrida por palavra-chave (Projeto 3) e indexação
de perguntas hipotéticas em vez do texto bruto (Projeto 4).

**Contraste de distâncias**

O dado mais informativo da bateria, porque torna visível o que o guia chama de erro nº 3
(similaridade alta não é relevância):

| Tipo de pergunta | Melhor distância | Comportamento |
| --- | --- | --- |
| Coberta pelo índice | 0.875 | respondeu, corretamente |
| Meta-pergunta sobre o documento | 1.238 | recusou |
| Fora do índice (corpus de controle) | 1.424 a 1.511 | recusou |

Note que o sistema **sempre** recebeu 4 chunks, inclusive nos dois últimos casos. O Chroma
devolve os k mais próximos independentemente de serem bons. A recusa veio do prompt, não
da busca. É exatamente esse buraco que o grading do Projeto 5 preenche, e é por isso que o
limiar de similaridade foi deliberadamente adiado.
