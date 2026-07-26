# ADR-001: Chroma como serviço em container, não embarcado

- **Status:** aceito
- **Data:** 2026-07-25
- **Domínio:** RAG
- **Decisores:** arthu

## Contexto

O Projeto 1 da trilha precisa de um armazém vetorial para persistir os embeddings do
corpus. O `README.md` da trilha especifica Chroma embarcado, com a justificativa explícita
de permitir começar sem resolver Docker, que na época em que o guia foi escrito não
respondia neste ambiente WSL.

Essa premissa não vale mais. Verificação em 25/07/2026: Docker client 28.5.2, Docker
Desktop 4.51.0, Compose v2.40.3, com `docker run hello-world` executando normalmente.

Chroma oferece dois modos de execução do mesmo mecanismo:

- **Embarcado** (`PersistentClient`): roda dentro do interpretador Python, persistindo em
  um diretório local.
- **Servidor**: processo separado, exposto por HTTP, acessado por `chromadb.HttpClient`.

Um dado apurado durante a decisão eliminou um argumento que parecia relevante:
`langchain-chroma` 1.1.0 declara `chromadb<2.0.0,>=1.3.5` como dependência obrigatória.
O pacote completo é instalado no ambiente virtual **nos dois modos**. O servidor,
portanto, não reduz o peso do ambiente Python; ele apenas acrescenta um serviço.

## Decisão

Usar Chroma **em container**, imagem `chromadb/chroma:1.5.9`, declarada em
`docker-compose.yml`, com persistência em volume nomeado `chroma_data` e acesso por
`chromadb.HttpClient` na porta 8000.

Valores verificados contra a imagem, não presumidos de documentação:

| Item | Valor | Como foi obtido |
|---|---|---|
| Caminho de persistência | `/data` | `persist_path` lido do `/config.yaml` interno |
| Porta | 8000 | `ExposedPorts` do manifesto |
| Endpoint de saúde | `GET /api/v2/heartbeat` | resposta 200 |
| API v1 | removida, responde `410 Gone` | resposta 410 |
| Binários disponíveis | `bash` sim; `curl`, `wget`, `python`, `nc` não | `docker exec` |

A última linha tem consequência prática: o healthcheck do compose usa
`bash -c "exec 3<>/dev/tcp/localhost/8000"`, porque nenhuma ferramenta HTTP existe dentro
da imagem. Isso verifica que a porta aceita conexão, não que a API responde, e a limitação
está anotada no próprio `docker-compose.yml`.

Cliente e servidor devem permanecer na mesma linha de versão (`chromadb` 1.5.x nos dois
lados). O `chromadb` do PyPI está em 1.5.9, coincidindo com a tag da imagem.

## Alternativas consideradas

### Chroma embarcado (`PersistentClient`)

Rejeitada. Era a recomendação técnica registrada durante a decisão, por três motivos:
nenhuma peça de infraestrutura pode falhar; apagar e reconstruir o índice é `rm -rf` de um
diretório, operação frequente durante o experimento de chunking; e no Projeto 1, cuja
finalidade é tornar o pipeline visível, qualquer erro que não seja do próprio pipeline é
ruído.

O autor optou pelo container por preferir trabalhar com o modelo cliente/servidor desde o
primeiro projeto, que é como um armazém vetorial existe em produção. O trade-off foi
apresentado e aceito de forma explícita.

### FAISS

Rejeitada. Também roda em processo e sem Docker, e é mais rápida, mas armazena apenas os
vetores: texto e metadados ficam em um arquivo pickle paralelo, e `pickle.load` executa
código arbitrário na desserialização. O guia da trilha introduz FAISS no Projeto 5, então
o contato com a tecnologia acontece de qualquer forma.

### Qdrant

Rejeitada para este projeto. É o armazém do Projeto 2, e antecipá-lo aqui eliminaria o
contraste pedagógico entre os dois projetos, além de contrariar o guia sem ganho.

## Consequências

**Positivas**
- Modelo cliente/servidor desde o primeiro projeto, igual ao de produção.
- O índice sobrevive à remoção do ambiente virtual e do repositório, por viver em volume.
- A API fica inspecionável por HTTP: `curl localhost:8000/api/v2/heartbeat` e Swagger em
  `/docs`.
- O caminho de Docker fica exercitado antes do Projeto 2, onde é obrigatório.

**Negativas**
- Um serviço precisa estar no ar antes de cada sessão. `docker compose up -d chroma` passa
  a ser pré-requisito de `ingest.py` e de `ask.py`.
- Surge uma classe de falhas sem relação com RAG: daemon parado, porta 8000 ocupada,
  volume sem permissão, incompatibilidade entre versões de cliente e servidor. Para quem
  está aprendendo, esses erros são difíceis de distinguir de erro de código. Registrado
  como risco no HLD, com mitigação.
- Cada busca paga uma ida e volta HTTP local. Irrelevante em termos absolutos (1 a 5 ms
  contra cerca de 2 s de geração), mas é custo que o modo embarcado não tem.
- O `README.md` da trilha, na seção do Projeto 1, deixa de corresponder ao que este
  repositório faz. A divergência é deliberada e está registrada aqui.

## Referências

- `docs/domains/rag/hld.md`, seção Arquitetura geral
- `docker-compose.yml` deste repositório
- [[ADR-002-openai-como-provedor-de-modelos]]
