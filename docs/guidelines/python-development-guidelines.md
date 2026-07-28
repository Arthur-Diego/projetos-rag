# Guideline de Desenvolvimento — Python

Referência rápida para os projetos Python desta trilha de estudo de RAG. Vale para o
Projeto 1 e para os Projetos 2 a 7.

Vive no workspace, não dentro de um projeto, pelo mesmo motivo da
[guideline de arquitetura em camadas](arquitetura-em-camadas.md): cópia diverge na
primeira alteração. Promovida de `rag-01-fundamentos-pdf/docs/guidelines/` em 27/07/2026,
quando o Projeto 2 passou a precisar dela — o texto já se declarava válido para os
Projetos 1 a 7, então a cópia nunca chegou a existir.

**O que é transversal e o que é de cada projeto:** este documento define princípios,
convenções e ferramentas. As versões de biblioteca de cada projeto vivem no
`requirements.txt` dele — a seção "Project Stack" abaixo é o denominador comum, não o
lock de nenhum projeto.

Ambiente-alvo: **Python 3.12.3** (o instalado). A versão estável mais recente da
linguagem é a 3.14.6, de junho/2026; a 3.15 está em beta e sai em outubro/2026. A 3.12
segue recebendo correções de segurança e é totalmente adequada — nada nesta trilha exige
recurso posterior a ela.

## Project Stack

**Bibliotecas especificadas**:

- **Framework**: LangChain (v1.3.14) — composição de pipelines de LLM e RAG — https://docs.langchain.com/oss/python/
- **Testes**: pytest (v9.1.1) — framework de testes com fixtures e parametrização — https://docs.pytest.org
- **Validação**: Pydantic (v2.13.4) — validação e saída estruturada por modelo de dados — https://github.com/pydantic/pydantic
- **Logging**: structlog (v26.1.0) — logs estruturados com contexto encadeado — https://www.structlog.org

**Ferramentas essenciais auto-selecionadas**:

- **Formatação**: Ruff format (v0.16.0) — formatador drop-in do Black, >99,9% idêntico — https://docs.astral.sh/ruff/formatter/
- **Lint**: Ruff (v0.16.0) — substitui flake8, isort e dezenas de plugins — https://docs.astral.sh/ruff
- **Tipos**: mypy (v2.3.0) — verificação estática de tipos — https://www.mypy-lang.org/
- **Build/Deps**: pip (v26.1.2) + venv (stdlib) — https://pip.pypa.io
- **Cobertura**: pytest-cov (v7.1.0) — https://pypi.org/project/pytest-cov/

> Esta seção é referência rápida. **Todos os exemplos de código deste guia usam apenas a
> biblioteca padrão** — os princípios valem independentemente da biblioteca escolhida.

---

## 1. Princípios Fundamentais

### 1.1 Filosofia e estilo

O Zen do Python (PEP 20) não é folclore: é o critério de desempate. Rode `python -c
"import this"` quando estiver em dúvida entre duas formas.

- **Explícito supera implícito.** Um `import *` economiza três segundos hoje e custa uma
  hora de busca amanhã.
- **Simples supera complexo.** Se a solução exige um diagrama para ser explicada, ela
  provavelmente está errada.
- **Formatação é automática.** Ruff format decide, você não discute. Discussão sobre
  vírgula é tempo que não virou código.
- **PEP 8 é o piso**, não o teto. O linter cobre o piso; o resto é julgamento.

### 1.2 Clareza acima de concisão

Nomes comunicam intenção. `chunks` diz mais que `data`; `chunk_overlap` diz mais que
`co`. Em código de RAG isso pesa mais que o normal, porque os conceitos já são abstratos
— não some abstração de nomenclatura à abstração do domínio.

```python
# Ruim: o que é d? o que é k?
def f(d, k=4):
    return s.similarity_search(d, k)

# Bom: a assinatura já é a documentação
def buscar_trechos(pergunta: str, quantidade: int = 4) -> list[Document]:
    return store.similarity_search(pergunta, k=quantidade)
```

Otimização prematura é o erro clássico. Meça antes (seção 15), otimize depois (17).

---

## 2. Inicialização do Projeto

### 2.1 Criando um projeto novo

Não há `pip` no sistema — ele nasce dentro do ambiente virtual:

```bash
mkdir meu-projeto && cd meu-projeto
python3 -m venv .venv
source .venv/bin/activate        # Linux/WSL/macOS
python -m pip install --upgrade pip
```

Confirme que está no ambiente certo antes de instalar qualquer coisa:

```bash
which python                     # deve apontar para .venv/bin/python
python -c "import sys; print(sys.prefix)"
```

### 2.2 Gerenciamento de dependências

```bash
python -m pip install requests             # instalar
python -m pip install "requests==2.32.3"   # instalar versão fixa
python -m pip uninstall requests           # remover
python -m pip list --outdated              # ver o que envelheceu
python -m pip freeze > requirements.txt    # congelar o estado atual
python -m pip install -r requirements.txt  # reconstruir o ambiente
```

`pip freeze` captura **tudo**, inclusive dependências transitivas. Para um projeto de
estudo isso é bom: torna o ambiente reprodutível byte a byte. Para uma biblioteca, prefira
declarar só as diretas em `pyproject.toml`.

---

## 3. Estrutura do Projeto

Layout mínimo, para scripts:

```
projeto/
├── .venv/                 ambiente virtual (gitignored)
├── .env                   segredos (gitignored, NUNCA commitado)
├── .env.example           modelo do .env, esse sim versionado
├── .gitignore
├── requirements.txt       dependências fixadas
├── pyproject.toml         configuração de ruff, mypy, pytest
├── ingest.py              scripts de entrada
├── ask.py
├── tests/
│   └── test_ingest.py
└── data/                  saída gerada, descartável (gitignored)
```

### Layout em camadas (padrão desta trilha)

**A fonte de verdade estrutural é `../../../docs/guidelines/arquitetura-em-camadas.md`,
no nível do workspace.** Ela vale para os 10 projetos, inclusive os três em Java, e não
deve ser copiada para dentro de projeto nenhum: cópia diverge na primeira alteração.

Instanciação em Python:

```
projeto/
├── ingest.py                 entrypoint: argparse + composition root
├── ask.py                    entrypoint: idem
├── rag/
│   ├── exceptions.py         RagException e subclasses
│   ├── config.py             RagProperties (frozen dataclass)
│   ├── domain/models.py      NamedTuple: SearchHit, Answer, IngestionReport
│   ├── facade/               casos de uso, sem terminal
│   ├── service/              Protocol + implementação, uma responsabilidade
│   ├── repository/           Protocol + adaptador de fonte externa
│   └── presenter/            único que escreve
├── docs/
└── pdfs/
```

As cinco regras que dão sentido à estrutura estão na guideline do workspace. As duas que
mais se quebram por descuido:

- **A facade não conhece terminal.** Nada de `print`, `argparse` ou `sys.stderr` em
  `facade/`. É isso que permite ao caso de uso servir CLI, HTTP e MCP sem alteração.
- **As camadas levantam, o entrypoint encerra.** Nenhuma camada chama `sys.exit()`.

Como esta trilha usa `Protocol` em vez de `ABC`, **o mypy deixa de ser opcional**: sem ele
os contratos não são verificados por ninguém, nem em tempo de execução nem antes.

`pyproject.toml` centraliza a configuração de todas as ferramentas:

```toml
[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B", "SIM"]

[tool.mypy]
python_version = "3.12"
warn_return_any = true
warn_unused_ignores = true

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-v --strict-markers"
markers = ["integration: exige serviços externos"]
```

---

## 4. Desenvolvimento em Container (Docker)

### 4.1 Filosofia

Nem todo projeto Python precisa de container. Mas a partir do momento em que entra um
serviço externo — Chroma, Qdrant, Postgres, Neo4j, Redis — o container deixa de ser
preferência e vira a forma sensata de garantir a mesma versão do serviço em qualquer
máquina.

Regra: **containerize as dependências, não necessariamente a aplicação.** Em
desenvolvimento, rodar o Python no host e os serviços em container dá o melhor equilíbrio
entre isolamento e velocidade de iteração.

### 4.2 Arquivos

`Dockerfile` (só se a aplicação também for containerizada), `docker-compose.yml` (os
serviços de que ela depende) e `.dockerignore`.

### 4.3 Dockerfile de desenvolvimento

Imagem oficial, variante slim, versão fixada. Sem multi-stage em desenvolvimento:

```dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["sleep", "infinity"]
```

`sleep infinity` mantém o container de pé para você entrar nele e executar comandos —
em desenvolvimento você quer um ambiente, não um processo.

### 4.4 Docker Compose

```yaml
services:
  qdrant:
    image: qdrant/qdrant:v1.18.3
    ports: ["6333:6333"]
    volumes: ["qdrant_data:/qdrant/storage"]
    healthcheck:
      test: ["CMD-SHELL", "bash -c ':> /dev/tcp/127.0.0.1/6333'"]
      interval: 10s
      timeout: 3s
      retries: 5

volumes:
  qdrant_data:
```

Volumes nomeados preservam o índice entre reinícios. Sem eles, cada `docker compose down`
custa uma reindexação inteira — e reindexar custa chamadas de API pagas.

### 4.5 `.dockerignore`

```
.venv/
__pycache__/
*.pyc
.git/
.env
data/
.pytest_cache/
.ruff_cache/
```

### 4.6 Comandos essenciais

| Ação | Comando |
|---|---|
| Subir um serviço | `docker compose up -d qdrant` |
| Ver logs | `docker compose logs -f qdrant` |
| Estado dos serviços | `docker compose ps` |
| Shell no container | `docker compose exec qdrant sh` |
| Parar tudo | `docker compose down` |
| Parar e apagar os dados | `docker compose down -v` |
| Conferir o daemon | `docker version` |

### 4.7 Boas práticas

- Suba **um serviço por vez** (`up -d <serviço>`). Elasticsearch e Neo4j sozinhos
  consomem gigabytes de RAM.
- Fixe a tag da imagem. `:latest` significa que seu ambiente muda sozinho.
- No WSL 2, o daemon só responde com a integração ativada em Docker Desktop → Settings →
  Resources → WSL Integration. `docker version` tem que mostrar Client **e** Server.
- Healthcheck não é enfeite: sem ele o script conecta antes do serviço aceitar conexão, e
  você depura um erro de rede que é de tempo.

---

## 5. Convenções de Nomenclatura

| Elemento | Convenção | Exemplo |
|---|---|---|
| Módulo / pacote | `snake_case`, curto | `ingest.py`, `retrieval/` |
| Classe | `PascalCase` | `DocumentLoader` |
| Função / método | `snake_case` | `dividir_em_chunks()` |
| Variável | `snake_case` | `chunk_overlap` |
| Constante | `UPPER_SNAKE_CASE` | `CHUNK_SIZE = 1000` |
| Privado (convenção) | prefixo `_` | `_normalizar()` |
| Type alias | `PascalCase` | `Chunks = list[Document]` |

Regras que evitam dor:

- Nunca sombreie um nome da stdlib. Um arquivo `json.py` no diretório quebra o `import
  json` de todo o projeto, e a mensagem de erro não aponta para ele.
- Evite `l`, `O`, `I` como nomes de variável — indistinguíveis de `1` e `0` em várias
  fontes (PEP 8 diz isso explicitamente).
- Booleanos ganham prefixo verbal: `tem_texto`, `is_valido`, `deve_reindexar`.
- Sufixo de unidade quando houver ambiguidade: `timeout_s`, `tamanho_bytes`,
  `chunk_size_chars`. Em RAG isso é crítico — "tamanho 1000" é caractere ou token?

---

## 6. Tipos e Sistema de Tipos

Python tem **tipagem gradual** (PEP 484): as anotações não são verificadas em tempo de
execução, são contrato para leitor e para o mypy. Isso não as torna opcionais — as torna
documentação que o computador confere.

### 6.1 Declaração

```python
from dataclasses import dataclass, field
from typing import Literal, Protocol

Caminho = str                                  # alias simples
Metadados = dict[str, str | int]               # sintaxe nativa 3.9+/3.10+

@dataclass(frozen=True, slots=True)
class Chunk:
    texto: str
    fonte: str
    pagina: int
    metadados: Metadados = field(default_factory=dict)

Estrategia = Literal["densa", "esparsa", "hibrida"]
```

`frozen=True` torna o objeto imutável — chunk indexado não deve mudar depois de criado.
`slots=True` reduz memória, o que importa quando existem dezenas de milhares deles.

### 6.2 Segurança de tipos

```bash
python -m pip install mypy==2.3.0
mypy .                          # verifica o projeto
mypy --strict ingest.py         # o rigor máximo, para arquivo novo
```

Prefira `X | None` a `Optional[X]` (3.10+) e sempre anote o retorno — inclusive `-> None`.
Uma função sem anotação de retorno é invisível para o mypy: ele assume `Any` e para de
verificar tudo que depende dela.

```python
# Ruim: Any se espalha silenciosamente a partir daqui
def carregar(caminho):
    return json.loads(open(caminho).read())

# Bom: o contrato é verificável
def carregar(caminho: str) -> dict[str, object]:
    with open(caminho, encoding="utf-8") as f:
        return json.load(f)
```

### 6.3 Alocação e inicialização

Nunca use mutável como default — o objeto é criado **uma vez**, na definição da função, e
compartilhado entre todas as chamadas:

```python
# Ruim: a lista sobrevive entre chamadas e acumula
def adicionar(item: str, destino: list[str] = []) -> list[str]:
    destino.append(item)
    return destino

# Bom
def adicionar(item: str, destino: list[str] | None = None) -> list[str]:
    destino = [] if destino is None else destino
    destino.append(item)
    return destino
```

---

## 7. Funções e Métodos

### 7.1 Assinaturas

```python
from pathlib import Path

def dividir_em_chunks(
    texto: str,
    *,
    tamanho: int = 1000,
    sobreposicao: int = 150,
) -> list[str]:
    """Divide o texto em pedaços com sobreposição.

    Args:
        texto: conteúdo a dividir.
        tamanho: caracteres por chunk.
        sobreposicao: caracteres repetidos entre chunks vizinhos.

    Returns:
        Lista de chunks na ordem original.

    Raises:
        ValueError: se sobreposicao >= tamanho.
    """
    if sobreposicao >= tamanho:
        raise ValueError(
            f"sobreposicao ({sobreposicao}) deve ser menor que tamanho ({tamanho})"
        )

    passo = tamanho - sobreposicao
    return [texto[i : i + tamanho] for i in range(0, len(texto), passo)]
```

O `*` força os parâmetros seguintes a serem nomeados. `dividir_em_chunks(t, 1000, 150)`
não diz o que é 1000 nem o que é 150; `dividir_em_chunks(t, tamanho=1000,
sobreposicao=150)` diz. Em código com muitos números mágicos, isso vale mais que um
comentário.

### 7.2 Retornos e erros

```python
# Ruim: engole o erro e devolve um valor que mente
def ler_pdf(caminho: str) -> str:
    try:
        return extrair(caminho)
    except Exception:
        return ""          # chamador acha que o PDF estava vazio

# Bom: falha alto, com contexto
def ler_pdf(caminho: Path) -> str:
    if not caminho.exists():
        raise FileNotFoundError(f"PDF não encontrado: {caminho}")

    texto = extrair(caminho)
    if not texto.strip():
        raise ValueError(
            f"{caminho} não produziu texto — provavelmente é PDF escaneado (imagem)"
        )
    return texto
```

O segundo caso não é preciosismo: PDF escaneado devolvendo string vazia é o erro nº 1 de
quem começa em RAG, e a mensagem acima economiza uma tarde inteira de depuração no lugar
errado.

### 7.3 Boas práticas

- Uma responsabilidade por função. Se o nome precisa de "e", são duas.
- Limite de 3–4 parâmetros posicionais; acima disso, agrupe num dataclass.
- Sem efeito colateral escondido: função que se chama `calcular_` não escreve em disco.
- Retorne cedo para reduzir aninhamento (seção 19.1).

---

## 8. Tratamento de Erros

### 8.1 Filosofia

Python usa exceções, e a cultura é **EAFP** — *easier to ask forgiveness than
permission*. Tente e trate a falha, em vez de checar todas as pré-condições antes.

```python
class ErroDeIngestao(Exception):
    """Base das falhas de ingestão deste projeto."""

class PdfSemTexto(ErroDeIngestao):
    """PDF sem camada de texto extraível (provavelmente escaneado)."""

class IndiceVazio(ErroDeIngestao):
    """Busca executada contra um índice sem documentos."""


def indexar(caminho: Path) -> int:
    try:
        texto = extrair(caminho)
    except OSError as e:
        # 'from e' preserva a exceção original no traceback.
        # Sem isso, você perde a causa raiz e depura o sintoma.
        raise ErroDeIngestao(f"falha ao ler {caminho}") from e

    if not texto.strip():
        raise PdfSemTexto(f"{caminho} não tem camada de texto")

    return len(texto)
```

Uma hierarquia própria permite ao chamador escolher a granularidade: capturar
`ErroDeIngestao` para tratar tudo, ou `PdfSemTexto` para tratar aquele caso.

### 8.2 Convenções

```python
# Ruim: captura tudo, inclusive KeyboardInterrupt e bugs seus,
# e o log não diz o que aconteceu
try:
    resultado = processar(doc)
except:
    print("erro")

# Bom: exceção específica, contexto no log, traceback preservado
try:
    resultado = processar(doc)
except PdfSemTexto:
    logger.warning("pulando arquivo sem texto", extra={"arquivo": doc.nome})
    continue
except ErroDeIngestao:
    logger.exception("falha ao processar", extra={"arquivo": doc.nome})
    raise
```

`except:` nu captura `SystemExit` e `KeyboardInterrupt` — seu Ctrl+C deixa de funcionar.
Se precisar de amplitude, use `except Exception:`, que exclui esses dois.

`logger.exception()` só existe dentro de um bloco `except` e inclui o traceback
automaticamente. `logger.error()` no mesmo lugar joga fora a informação mais útil.

### 8.3 Boas práticas

- Nunca silencie sem comentar o porquê. `except X: pass` exige uma linha explicando.
- Contexto no erro: qual arquivo, qual ID, qual valor. "erro ao processar" não ajuda.
- Trate no limite de I/O, não em toda camada. Erro tratado três vezes vira três logs do
  mesmo evento.
- `finally` ou context manager para liberar recurso — `with` é quase sempre a resposta.

---

## 9. Concorrência e Paralelismo

### 9.1 Modelo

Python tem três modelos, e escolher o errado é a diferença entre 10× mais rápido e 10%
mais lento. O critério é onde o tempo está sendo gasto:

| Modelo | Use quando | Não use quando |
|---|---|---|
| `asyncio` | I/O de rede, muitas chamadas HTTP | CPU pesada |
| `threading` | I/O bloqueante de biblioteca síncrona | CPU pesada (o GIL serializa) |
| `multiprocessing` | CPU pesada (parsing, embedding local) | tarefas curtas (o overhead domina) |

O GIL (*Global Interpreter Lock*) permite um bytecode Python por vez. Threads não
aceleram cálculo — aceleram espera. Chamada de API é espera; parsear 300 PDFs é cálculo.

### 9.2 Sincronização

```python
import asyncio

async def buscar(cliente, url: str, sem: asyncio.Semaphore) -> str:
    # O semáforo limita a concorrência. Sem ele, 500 documentos viram
    # 500 conexões simultâneas e a API devolve 429.
    async with sem:
        async with cliente.get(url) as resposta:
            return await resposta.text()

async def buscar_todos(urls: list[str], max_simultaneas: int = 5) -> list[str]:
    sem = asyncio.Semaphore(max_simultaneas)
    async with criar_cliente() as cliente:
        tarefas = [buscar(cliente, u, sem) for u in urls]
        return await asyncio.gather(*tarefas)
```

Para código síncrono, `ThreadPoolExecutor` cobre a maioria dos casos com menos cerimônia:

```python
from concurrent.futures import ThreadPoolExecutor, as_completed

def processar_lote(itens: list[str], trabalhadores: int = 5) -> list[str]:
    resultados = []
    with ThreadPoolExecutor(max_workers=trabalhadores) as pool:
        futuros = {pool.submit(processar, i): i for i in itens}
        for f in as_completed(futuros):
            item = futuros[f]
            try:
                resultados.append(f.result())
            except Exception:
                logger.exception("falhou", extra={"item": item})
    return resultados
```

O `try` dentro do laço é essencial: sem ele, um item que falha aborta o lote inteiro e
você perde o trabalho já feito.

### 9.3 Boas práticas

- Sempre limite a concorrência. "Todos de uma vez" é como se descobre o rate limit da
  API pela via cara.
- Sempre defina timeout. Requisição sem timeout pode pendurar o processo para sempre.
- Use `asyncio.TaskGroup` (3.11+) em vez de `gather` quando quiser que uma falha cancele
  as irmãs.
- Encerramento gracioso: capture `KeyboardInterrupt` e cancele as tarefas pendentes.

### 9.4 Armadilhas comuns

- **Misturar bloqueante com async.** Chamada síncrona dentro de `async def` trava o event
  loop inteiro; isole com `asyncio.to_thread()`.
- **Esquecer o `await`.** A corrotina nunca executa e o retorno é um objeto coroutine — o
  `RuntimeWarning` emitido passa despercebido.
- **Estado compartilhado sem lock.** `contador += 1` não é atômico.

---

## 10. Interfaces e Abstrações

### 10.1 Design

Python favorece *duck typing*, mas `Protocol` (PEP 544) torna o contrato explícito e
verificável pelo mypy — sem exigir herança:

```python
from typing import Protocol, runtime_checkable

@runtime_checkable
class ArmazemVetorial(Protocol):
    """Contrato mínimo de um vector store para esta trilha."""

    def adicionar(self, textos: list[str]) -> list[str]: ...

    def buscar(self, consulta: str, k: int = 4) -> list[str]: ...
```

Qualquer classe com esses dois métodos satisfaz o protocolo. Não é preciso importar nada
nem herdar de nada — o que permite trocar Chroma por Qdrant sem tocar em quem consome.

Interfaces pequenas envelhecem melhor. Um protocolo com 12 métodos obriga toda
implementação a preencher 12 buracos; um com 2 é implementável em cinco minutos.

### 10.2 Implementação

```python
class ArmazemEmMemoria:
    """Implementa ArmazemVetorial sem herdar dele."""

    def __init__(self) -> None:
        self._textos: list[str] = []

    def adicionar(self, textos: list[str]) -> list[str]:
        inicio = len(self._textos)
        self._textos.extend(textos)
        return [str(i) for i in range(inicio, len(self._textos))]

    def buscar(self, consulta: str, k: int = 4) -> list[str]:
        termos = set(consulta.lower().split())
        pontuados = sorted(
            self._textos,
            key=lambda t: len(termos & set(t.lower().split())),
            reverse=True,
        )
        return pontuados[:k]


def indexar_e_buscar(armazem: ArmazemVetorial, textos: list[str]) -> list[str]:
    armazem.adicionar(textos)
    return armazem.buscar("consulta exemplo")
```

Use ABC (`abc.ABC`) em vez de `Protocol` quando quiser **compartilhar implementação**
entre as subclasses, não só o contrato.

### 10.3 Composição

```python
class ComCache:
    """Envolve outro armazém acrescentando cache — sem herança."""

    def __init__(self, interno: ArmazemVetorial) -> None:
        self._interno = interno
        self._cache: dict[str, list[str]] = {}

    def adicionar(self, textos: list[str]) -> list[str]:
        self._cache.clear()
        return self._interno.adicionar(textos)

    def buscar(self, consulta: str, k: int = 4) -> list[str]:
        chave = f"{consulta}:{k}"
        if chave not in self._cache:
            self._cache[chave] = self._interno.buscar(consulta, k)
        return self._cache[chave]
```

`ComCache` também satisfaz `ArmazemVetorial` — pode envolver a si mesmo ou qualquer
implementação futura. Composição sobre herança.

---

## 11. Testes Unitários

### 11.1 Estrutura

Arquivos `test_*.py`, funções `test_*`, e o padrão **AAA**: arranje, aja, afirme.

```python
# tests/test_chunking.py
import pytest

from ingest import dividir_em_chunks


def test_divide_respeitando_a_sobreposicao():
    # Arranje
    texto = "a" * 250

    # Aja
    chunks = dividir_em_chunks(texto, tamanho=100, sobreposicao=20)

    # Afirme
    assert len(chunks) == 4
    assert all(len(c) <= 100 for c in chunks)
    assert chunks[0][-20:] == chunks[1][:20]


def test_rejeita_sobreposicao_maior_que_o_tamanho():
    with pytest.raises(ValueError, match="deve ser menor"):
        dividir_em_chunks("texto", tamanho=100, sobreposicao=100)
```

O nome do teste é a especificação. `test_divide_respeitando_a_sobreposicao` diz o que o
sistema promete; `test_chunking_2` não diz nada e some do radar quando quebra.

### 11.2 Testes parametrizados

```python
@pytest.mark.parametrize(
    ("tamanho", "sobreposicao", "esperado"),
    [
        (100, 0, 3),      # sem sobreposição
        (100, 20, 4),     # com sobreposição, mais chunks
        (300, 0, 1),      # cabe em um só
        (250, 0, 1),      # limite exato
    ],
    ids=["sem-overlap", "com-overlap", "chunk-grande", "limite-exato"],
)
def test_quantidade_de_chunks(tamanho, sobreposicao, esperado):
    assert len(dividir_em_chunks("a" * 250, tamanho=tamanho,
                                 sobreposicao=sobreposicao)) == esperado
```

Os `ids` aparecem na saída de falha. Sem eles, você lê `test_quantidade[100-20-4]` e
precisa contar posições para saber qual caso quebrou.

Fixtures isolam a preparação e o pytest cuida da limpeza:

```python
@pytest.fixture
def pdf_temporario(tmp_path):
    arquivo = tmp_path / "amostra.pdf"
    arquivo.write_bytes(b"%PDF-1.4\n...")
    return arquivo          # tmp_path é apagado automaticamente
```

### 11.3 Asserções

`assert` puro basta — o pytest reescreve a expressão e mostra os dois lados na falha.
Não use `assertEqual`; não há ganho.

```python
assert resultado == esperado
assert "trecho" in resposta
assert pytest.approx(0.83, abs=1e-2) == score      # ponto flutuante
with pytest.raises(ValueError):                     # exceção esperada
    funcao_que_falha()
```

Nunca compare float com `==` direto: `0.1 + 0.2 != 0.3` em qualquer linguagem com IEEE
754.

### 11.4 Comandos

```bash
pytest                                  # tudo
pytest tests/test_chunking.py           # um arquivo
pytest -k "sobreposicao"                # por nome
pytest tests/test_chunking.py::test_divide_respeitando_a_sobreposicao
pytest -v                               # detalhado
pytest -x                               # para na primeira falha
pytest --lf                             # só os que falharam da última vez
pytest --cov=. --cov-report=term-missing   # cobertura, com linhas faltantes
pytest -m "not integration"             # exclui os marcados
```

`--cov-report=term-missing` é o único formato de cobertura que serve para agir: mostra
**quais linhas** não foram exercitadas, em vez de um percentual que não diz o que fazer.

---

## 12. Mocks e Testabilidade

### 12.1 Estratégias

`unittest.mock` é stdlib e cobre tudo. A regra: **mocke o que é lento, caro ou
não-determinístico** — chamada de API paga, relógio, rede, disco. Não mocke a sua própria
lógica, ou o teste passa a verificar o mock.

```python
from unittest.mock import Mock, patch


def test_nao_chama_a_api_quando_o_cache_tem_a_resposta():
    cliente = Mock()
    cliente.embed.return_value = [0.1, 0.2, 0.3]

    servico = Servico(cliente, cache={"oi": [0.1, 0.2, 0.3]})
    servico.embed("oi")

    cliente.embed.assert_not_called()
```

`patch` substitui no **local onde o nome é usado**, não onde foi definido — a fonte de
90% das confusões com mock:

```python
# ingest.py faz: from openai import Client
# Portanto o alvo é "ingest.Client", NÃO "openai.Client"
@patch("ingest.Client")
def test_indexacao(mock_cliente):
    mock_cliente.return_value.embed.return_value = [0.0] * 1536
    assert indexar("amostra.pdf") == 12
```

### 12.2 Injeção de dependência

Não há framework de DI em Python — o construtor basta:

```python
# Ruim: a dependência é criada dentro, impossível de substituir
class Indexador:
    def __init__(self):
        self.cliente = ClienteOpenAI(os.environ["OPENAI_API_KEY"])

# Bom: injetada, com default conveniente para produção
class Indexador:
    def __init__(self, cliente: ClienteEmbedding | None = None):
        self.cliente = cliente or ClienteOpenAI(os.environ["OPENAI_API_KEY"])
```

A segunda versão é testável sem mock nenhum: passe um fake e pronto.

### 12.3 Test doubles

**Stub** devolve valor fixo (não interessa como foi chamado); **mock** registra chamadas
e permite asserção (o *como* importa); **fake** é implementação simplificada que funciona;
**spy** envolve o real e observa.

Um fake de vector store em memória (seção 10.2) costuma valer mais que uma pilha de
mocks: o teste fica legível e exercita o fluxo de verdade.

---

## 13. Testes de Integração

### 13.1 Estrutura

Separe por marcador, declarado no `pyproject.toml`:

```python
@pytest.mark.integration
def test_indexa_e_recupera_de_verdade(tmp_path):
    store = criar_store(persist_directory=str(tmp_path))
    store.adicionar(["o prazo de garantia é de 12 meses"])

    assert "garantia" in store.buscar("qual o prazo?")[0]
```

### 13.2 Execução seletiva

```bash
pytest -m "not integration"        # rápido, roda a cada salvamento
pytest -m integration              # lento, roda antes do commit
pytest --strict-markers            # falha se o marcador não foi declarado
```

`--strict-markers` evita o erro silencioso de digitar `@pytest.mark.integrationn` — sem
ele o marcador desconhecido é ignorado e o teste roda quando não devia.

### 13.3 Dependências reais

Para serviços em container, `testcontainers` (v4.15.0) sobe e derruba o serviço dentro do
teste. Vale a partir do momento em que há Qdrant ou Postgres envolvido.

Um princípio que economiza dinheiro nesta trilha: **API paga não entra em teste
automatizado.** Use um fake determinístico de embedding (por exemplo, hash do texto
normalizado em um vetor) e reserve as chamadas reais para a execução manual.

---

## 14. Testes de Carga

### 14.1 Ferramentas

Locust (v2.46.2) para carga sobre HTTP; `pytest-benchmark` para função isolada. Em
pipeline de LLM o gargalo raramente é o seu código — é a API e o rate limit.

### 14.2 O que medir

Não requisições por segundo, mas **latência por estágio** e **custo por consulta**:

```python
import time

def medir(pergunta: str) -> dict[str, float]:
    t0 = time.perf_counter()
    docs = retriever.buscar(pergunta)
    t1 = time.perf_counter()
    llm.responder(pergunta, docs)
    return {"busca_s": t1 - t0, "geracao_s": time.perf_counter() - t1}
```

`time.perf_counter()`, nunca `time.time()` — o segundo anda para trás quando o relógio do
sistema é ajustado.

### 14.3 Concorrência

Suba a concorrência aos poucos (2, 5, 10) e observe o primeiro `429`. Esse é o seu teto
real, e ele é por conta, não por biblioteca.

---

## 15. Profiling e Diagnóstico

### 15.1 CPU e memória

```bash
python -m cProfile -s cumtime ingest.py | head -30     # stdlib, zero setup
py-spy top -- python ingest.py                          # amostragem, processo vivo
py-spy record -o perfil.svg -- python ingest.py         # flamegraph
memray run ingest.py && memray flamegraph memray-*.bin  # memória
```

`py-spy` (v0.4.2) tem uma vantagem decisiva: anexa a um processo **já em execução**, sem
reiniciar nem instrumentar. Quando o script está travado há dez minutos e você não sabe
onde, `py-spy dump --pid <pid>` responde na hora.

### 15.2 Medição pontual

```python
import cProfile, pstats

with cProfile.Profile() as perfil:
    indexar("documento.pdf")

pstats.Stats(perfil).sort_stats("cumtime").print_stats(15)
```

Ordene por `cumtime` (acumulado, inclui aninhadas) para achar o caminho caro; por
`tottime` (próprio) para achar a função cara.

### 15.3 Análise

Meça antes de otimizar. A intuição sobre o que é lento em Python erra na maioria das
vezes — e em pipeline de LLM a resposta é quase sempre "a chamada de rede", não o laço.

---

## 16. Benchmarks

### 16.1 Escrevendo

Para trechos pequenos, `timeit` (stdlib) já isola o ruído:

```python
import timeit

setup = "from ingest import dividir_em_chunks; texto = 'a' * 100_000"
tempo = timeit.timeit("dividir_em_chunks(texto)", setup=setup, number=100)
print(f"{tempo / 100 * 1000:.2f} ms por execução")
```

```bash
python -m timeit -s "texto = 'a' * 100_000" "texto.split()"
```

### 16.2 Parametrizados

```python
for tamanho in (500, 1000, 2000, 4000):
    t = timeit.timeit(f"dividir_em_chunks(texto, tamanho={tamanho})",
                      setup=setup, number=50)
    print(f"tamanho={tamanho:5} → {t / 50 * 1000:6.2f} ms")
```

### 16.3 Execução e análise

Regras para o número não mentir:

- Rode ao menos 5 vezes e use a **mediana** — um pico de GC distorce a média.
- Sem outros programas pesados na máquina.
- Mude **um** parâmetro por vez; alterar corpus e chunk size juntos não mede nada.
- Anote a variação percentual: o valor absoluto não transfere entre máquinas.

---

## 17. Otimização

### 17.1 Princípios

1. **Meça primeiro** (seção 15). Otimizar por palpite muda código sem mudar tempo.
2. **Ataque o dominante.** Acelerar em 90% algo que ocupa 2% do tempo rende 1,8%.
3. **Documente o trade-off.** Toda otimização compra velocidade com legibilidade; deixe o
   preço escrito no comentário.

### 17.2 Otimizações comuns

```python
# Ruim: O(n) por consulta
if item in lista_grande: ...

# Bom: O(1), se a ordem não importa
if item in conjunto_grande: ...
```

```python
# Ruim: cria uma string nova a cada volta — O(n²)
saida = ""
for chunk in chunks:
    saida += chunk + "\n"

# Bom: uma alocação
saida = "\n".join(chunks)
```

```python
from functools import lru_cache

# Memoização para função pura e cara. Só para argumentos hasheáveis
# e resultado determinístico — cache de função com efeito colateral
# é bug com aparência de otimização.
@lru_cache(maxsize=1024)
def normalizar(texto: str) -> str:
    return " ".join(texto.lower().split())
```

Em pipelines de RAG, a otimização que mais rende não é de CPU: é **enviar menos chamadas
de API**. Agrupar embeddings em lote transforma 500 requisições em 5.

### 17.3 Memória

Gerador em vez de lista quando o consumo é sequencial e o volume é grande:

```python
# Ruim: 300 páginas inteiras na memória de uma vez
def carregar(caminhos: list[Path]) -> list[str]:
    return [c.read_text(encoding="utf-8") for c in caminhos]

# Bom: uma por vez
def carregar(caminhos: list[Path]) -> Iterator[str]:
    for c in caminhos:
        yield c.read_text(encoding="utf-8")
```

`__slots__` (ou `@dataclass(slots=True)`) corta o `__dict__` de cada instância — relevante
a partir de dezenas de milhares de objetos.

### 17.4 Desempenho básico

- Resolva atributo fora do laço: `metodo = obj.metodo` antes do `for`.
- List comprehension é mais rápida que `for` com `append`, e mais legível.
- Prefira built-ins (`sum`, `sorted`, `any`) — são C, não Python.
- `f"{x}"` supera `"%s" % x` e `.format()` em velocidade e clareza.

---

## 18. Segurança

### 18.1 Práticas essenciais

**Nunca escreva segredo no código.** Em projeto de RAG isso é a falha nº 1, e a mais cara:
uma chave da OpenAI num repositório público é detectada por varredores automáticos e
usada em minutos.

```python
import os

# Ruim
API_KEY = "sk-proj-abc123..."

# Bom: falha alto e cedo se não estiver configurada
API_KEY = os.environ.get("OPENAI_API_KEY")
if not API_KEY:
    raise RuntimeError("OPENAI_API_KEY não definida — copie .env.example para .env")
```

O `.gitignore` com `.env` entra **antes** do primeiro `git add`, não depois. Depois já
é tarde: o segredo fica no histórico mesmo que você apague o arquivo.

Valide toda entrada externa. Em RAG, "entrada externa" inclui o texto dos documentos e a
saída do LLM — nenhum dos dois é confiável:

```python
def caminho_seguro(base: Path, nome: str) -> Path:
    """Impede path traversal: '../../etc/passwd' não escapa da base."""
    destino = (base / nome).resolve()
    if not destino.is_relative_to(base.resolve()):
        raise ValueError(f"caminho fora da base permitida: {nome}")
    return destino
```

Nunca use `eval()`, `exec()` ou `pickle.load()` sobre dado que você não gerou. `pickle`
executa código arbitrário na desserialização — é execução remota disfarçada de
carregamento de arquivo.

### 18.2 Ferramentas

```bash
python -m pip install pip-audit==2.10.1 bandit==1.9.4
pip-audit                          # vulnerabilidades conhecidas nas dependências
bandit -r . -x ./tests,./.venv     # padrões inseguros no seu código
```

### 18.3 Segurança nas fronteiras

Código gerado por LLM que vai ser **executado** — SQL, Cypher, shell — é a superfície mais
perigosa de um sistema de RAG. Instrução em prompt ("nunca use DELETE") é sugestão a um
modelo probabilístico, não controle de segurança.

O controle real é infraestrutura: **usuário somente-leitura no banco**, timeout na
consulta, lista de tabelas permitidas. Trate o prompt como documentação da intenção e a
permissão como o mecanismo.

---

## 19. Padrões de Código

### 19.1 Retorno antecipado

```python
# Ruim: a lógica principal fica soterrada em três níveis
def processar(doc):
    if doc is not None:
        if doc.texto:
            if len(doc.texto) > 10:
                return indexar(doc)
            else:
                return None
        else:
            return None
    else:
        return None

# Bom: as guardas saem na frente, o caminho feliz fica no nível zero
def processar(doc: Documento | None) -> str | None:
    if doc is None:
        return None
    if not doc.texto:
        return None
    if len(doc.texto) <= 10:
        return None
    return indexar(doc)
```

### 19.2 Separação de responsabilidades

Isole a lógica pura do I/O. A parte pura é testável sem mock, sem rede e sem disco:

```python
# I/O na borda
def ler_documentos(pasta: Path) -> list[str]:
    return [p.read_text(encoding="utf-8") for p in pasta.glob("*.txt")]

# lógica pura no meio — esta é a parte que ganha teste unitário
def preparar(textos: list[str], tamanho: int) -> list[str]:
    return [c for t in textos for c in dividir_em_chunks(t, tamanho=tamanho)]

# I/O na outra borda
def gravar(chunks: list[str], store: ArmazemVetorial) -> None:
    store.adicionar(chunks)
```

### 19.3 DRY, com juízo

Extraia duplicação quando o **motivo** da mudança for o mesmo. Dois trechos parecidos que
mudam por razões diferentes devem permanecer separados — unificá-los cria um acoplamento
que só aparece meses depois, quando um dos dois precisa mudar e o outro não.

Regra prática: duplicou duas vezes, observe. Três, extraia.

### 19.4 Escopo de variável

Declare o mais perto possível do uso. Use `with` para qualquer recurso que precise ser
fechado — arquivo, conexão, lock:

```python
# Ruim: se ocorrer exceção antes do close, o arquivo fica aberto
f = open("dados.txt", encoding="utf-8")
conteudo = f.read()
f.close()

# Bom: fecha mesmo com exceção
with open("dados.txt", encoding="utf-8") as f:
    conteudo = f.read()
```

Sempre passe `encoding="utf-8"` explicitamente. O default depende do sistema, e o
resultado é o texto funcionar na sua máquina e quebrar em outra.

---

## 20. Gerenciamento de Dependências

### 20.1 Princípios

- **Biblioteca padrão primeiro.** `pathlib`, `json`, `sqlite3`, `logging`, `dataclasses`
  e `unittest.mock` resolvem mais do que se imagina.
- **Versões explícitas.** Sem pin, seu projeto muda sozinho e você debuga uma mudança de
  API achando que errou o conceito.
- **Minimalismo.** Cada dependência é código de terceiro que você passa a manter.
- **Prefira o pacote dedicado ao guarda-chuva.** No ecossistema LangChain, `langchain-openai`
  em vez de `langchain-community` sempre que existir — os pacotes guarda-chuva estão em
  *sunset* e emitem `DeprecationWarning`.

### 20.2 Comandos

```bash
python -m pip list --outdated            # o que envelheceu
python -m pip install --upgrade <pkg>    # atualizar um
pip-audit                                # vulnerabilidades
python -m pip check                      # conflitos de dependência
python -m pip freeze > requirements.txt  # recongelar após mudança
```

---

## 21. Comentários e Documentação

### 21.1 Comentários

Comente o **porquê**, nunca o **quê**. O que o código faz está no código; por que ele faz
assim, não.

```python
# Ruim: repete o que a linha já diz
i += 1  # incrementa i

# Bom: registra a decisão e a consequência
# 150 de sobreposição (15% do chunk) evita cortar uma frase no meio.
# Abaixo de ~10% o corte volta a aparecer; acima de ~25% o custo de
# embedding sobe sem ganho de recall mensurável.
chunk_overlap = 150
```

Comentário que descreve código desatualizado é pior que nenhum: ele mente com autoridade.

### 21.2 Docstrings

Formato Google (PEP 257 define a forma; o estilo Google é o mais legível):

```python
def buscar(pergunta: str, k: int = 4) -> list[Chunk]:
    """Recupera os k chunks mais similares à pergunta.

    Similaridade alta não é o mesmo que relevância: o armazém sempre
    devolve os k mais próximos, mesmo quando todos são ruins. Filtre por
    limiar quando a ausência de resposta for um resultado aceitável.

    Args:
        pergunta: texto da consulta em linguagem natural.
        k: quantos chunks retornar.

    Returns:
        Chunks ordenados por similaridade decrescente.

    Raises:
        IndiceVazio: se nenhum documento foi indexado ainda.
    """
```

```bash
python -c "import ingest; help(ingest.buscar)"   # lê a docstring
```

### 21.3 Documentação de módulo

Primeira linha do arquivo, antes de qualquer import:

```python
"""Ingestão de PDFs para o índice vetorial.

Executar uma vez por corpus:
    python ingest.py

Lê de pdfs/*.pdf (não recursivo: pdfs/fora-do-corpus/ fica de fora
de propósito) e grava na coleção do serviço Chroma.
"""
```

---

## 22. Banco de Dados

### 22.1 Abordagem

| Abordagem | Vantagem | Custo |
|---|---|---|
| **SQL puro** (`sqlite3`, `psycopg`) | controle total, zero mágica, SQL transferível | mapeamento manual para objeto |
| **Query builder** | composição segura de consultas | uma dependência a mais |
| **ORM** (SQLAlchemy) | produtividade em CRUD, migrações | esconde o SQL gerado, e o SQL gerado importa |

Para estudo e para scripts, SQL puro com a stdlib vence: você vê exatamente o que roda.

### 22.2 Conexão e consulta

`sqlite3` é stdlib — nada a instalar:

```python
import sqlite3
from contextlib import closing
from pathlib import Path


def conectar(caminho: Path) -> sqlite3.Connection:
    conexao = sqlite3.connect(
        caminho,
        timeout=10.0,             # espera por lock em vez de falhar na hora
        isolation_level=None,     # autocommit; transação explícita via BEGIN
    )
    conexao.row_factory = sqlite3.Row       # acesso por nome: linha["titulo"]
    conexao.execute("PRAGMA foreign_keys = ON")   # desligado por padrão no SQLite
    return conexao


def contar_por_status(caminho: Path, status: str) -> int:
    # closing() garante o fechamento mesmo com exceção
    with closing(conectar(caminho)) as conexao:
        cursor = conexao.execute(
            "SELECT COUNT(*) AS total FROM pedidos WHERE status = ?",
            (status,),            # parâmetro ligado, nunca interpolado
        )
        return cursor.fetchone()["total"]
```

Parametrização não é estilo, é a fronteira entre um programa e uma vulnerabilidade:

```python
# Ruim: injeção de SQL. status = "x'; DROP TABLE pedidos; --" apaga a tabela
conexao.execute(f"SELECT * FROM pedidos WHERE status = '{status}'")

# Bom: o driver escapa; o valor nunca vira sintaxe
conexao.execute("SELECT * FROM pedidos WHERE status = ?", (status,))
```

Transação explícita para escrita em lote — uma ordem de grandeza mais rápida que um
commit por linha, e atômica:

```python
def inserir_muitos(conexao: sqlite3.Connection, linhas: list[tuple[str, int]]) -> None:
    try:
        conexao.execute("BEGIN")
        conexao.executemany(
            "INSERT INTO chunks (texto, pagina) VALUES (?, ?)", linhas
        )
        conexao.execute("COMMIT")
    except sqlite3.Error:
        conexao.execute("ROLLBACK")
        raise
```

### 22.3 Migrações

Não há ferramenta de migração na stdlib. Para projetos pequenos, versione o schema na
própria base com `PRAGMA user_version` e aplique os passos pendentes em ordem:

```python
MIGRACOES = [
    "CREATE TABLE IF NOT EXISTS chunks (id INTEGER PRIMARY KEY, texto TEXT, pagina INT)",
    "CREATE INDEX IF NOT EXISTS idx_chunks_pagina ON chunks(pagina)",
]

def migrar(conexao: sqlite3.Connection) -> None:
    versao = conexao.execute("PRAGMA user_version").fetchone()[0]
    for i, ddl in enumerate(MIGRACOES[versao:], start=versao):
        conexao.execute(ddl)
        conexao.execute(f"PRAGMA user_version = {i + 1}")
```

Em projetos maiores, Alembic (com SQLAlchemy) é o padrão do ecossistema.

### 22.4 Boas práticas

- Consulta parametrizada **sempre**. Concatenação de string em SQL não tem caso legítimo.
- Índice nas colunas de filtro frequente — e confira com `EXPLAIN QUERY PLAN`.
- Conexão é recurso: abra tarde, feche cedo, use `with`/`closing`.
- Transação explícita para escrita em lote.
- Timeout e política de retry para erro de lock; sem eles o script trava sem dizer por quê.

---

## 23. Logs e Observabilidade

### 23.1 Níveis

| Nível | Quando | Exemplo nesta trilha |
|---|---|---|
| `DEBUG` | diagnóstico detalhado | os 4 chunks recuperados, com score |
| `INFO` | marco normal | "36 páginas → 412 chunks" |
| `WARNING` | anormal, mas seguiu | "PDF sem texto, pulando" |
| `ERROR` | operação falhou | "falha ao chamar a API de embedding" |
| `CRITICAL` | processo não continua | "OPENAI_API_KEY ausente" |

`print()` serve para a saída que o usuário pediu. Tudo que é diagnóstico vai para log —
a diferença é que log tem nível, destino e carimbo de tempo, e pode ser desligado sem
mexer no código.

### 23.2 Configuração

```python
import logging
import sys

def configurar_logs(nivel: str = "INFO") -> None:
    logging.basicConfig(
        level=getattr(logging, nivel.upper()),
        format="%(asctime)s %(levelname)-8s %(name)s %(message)s",
        datefmt="%H:%M:%S",
        stream=sys.stderr,        # stderr: não polui a saída útil no stdout
    )
    # Bibliotecas HTTP logam cada requisição em DEBUG e afogam o seu log
    logging.getLogger("httpx").setLevel(logging.WARNING)


logger = logging.getLogger(__name__)   # __name__ dá a hierarquia de módulos de graça
```

Mandar log para `stderr` e resultado para `stdout` permite `python ask.py "..." > resposta.txt`
sem levar o log junto.

### 23.3 Log estruturado

```python
import json
import logging


class FormatadorJson(logging.Formatter):
    def format(self, registro: logging.LogRecord) -> str:
        saida = {
            "ts": self.formatTime(registro),
            "nivel": registro.levelname,
            "msg": registro.getMessage(),
        }
        # 'extra' vira campo de primeira classe, não texto interpolado
        for chave, valor in getattr(registro, "contexto", {}).items():
            saida[chave] = valor
        if registro.exc_info:
            saida["traceback"] = self.formatException(registro.exc_info)
        return json.dumps(saida, ensure_ascii=False)


logger.info(
    "indexação concluída",
    extra={"contexto": {"arquivo": "manual.pdf", "paginas": 36, "chunks": 412}},
)
```

Campo estruturado é filtrável: `... | jq 'select(.chunks > 400)'`. Mensagem interpolada
("indexei 412 chunks de manual.pdf") só é grepável, e grep não compara números.

### 23.4 Métricas

Instrumente as fronteiras de I/O — é onde o tempo e o dinheiro moram. Num pipeline de
RAG, o mínimo útil por consulta: latência da busca, latência da geração, número de chunks
recuperados, tokens de entrada e de saída.

```python
import time
from contextlib import contextmanager

@contextmanager
def cronometrar(operacao: str):
    inicio = time.perf_counter()
    try:
        yield
    finally:
        logger.info(
            "operação concluída",
            extra={"contexto": {"op": operacao,
                                "ms": round((time.perf_counter() - inicio) * 1000, 1)}},
        )

with cronometrar("busca"):
    docs = retriever.buscar(pergunta)
```

Mantenha a cardinalidade dos rótulos sob controle: usar a pergunta do usuário como label
de métrica gera uma série temporal nova por consulta e derruba qualquer coletor.

---

## 24. Regras de Ouro

1. **Simplicidade.** A solução óbvia primeiro. Abstração se paga quando o terceiro caso
   aparece, não quando você imagina o segundo.
2. **Erros explícitos.** Nunca silencie. Toda exceção capturada é tratada ou relançada
   com contexto.
3. **Testes.** O que não tem teste não tem contrato — tem hábito.
4. **Documentação.** Docstring no que é público; comentário no que é surpreendente.
5. **Desempenho medido.** Perfile antes, otimize depois, meça de novo.
6. **Segredo fora do código.** `.env` no `.gitignore` antes do primeiro `git add`.

---

## 25. Checklist Pré-Commit

**Código**
- [ ] `ruff format .` aplicado
- [ ] `ruff check .` sem erro
- [ ] `mypy .` sem erro novo
- [ ] O script roda de ponta a ponta

**Testes**
- [ ] `pytest` passa inteiro
- [ ] Cobertura ≥ 70% no código crítico
- [ ] Testes de integração rodados quando houve mudança de I/O

**Qualidade**
- [ ] Exceções tratadas explicitamente, com contexto
- [ ] Recursos fechados com `with`
- [ ] Nenhum segredo no diff — `git diff --staged | grep -iE 'sk-|api[_-]?key|password'`
- [ ] `pip-audit` sem vulnerabilidade nova

**Documentação**
- [ ] Funções públicas com docstring
- [ ] README atualizado se o comando de uso mudou
- [ ] Comentários explicam o porquê

**Docker (quando aplicável)**
- [ ] `docker compose config` válido
- [ ] Serviços sobem e passam no healthcheck

---

## 26. Referências

### Documentação oficial
- [Python 3.12 — documentação](https://docs.python.org/3.12/)
- [Status das versões do Python](https://devguide.python.org/versions/)
- [PEP 8 — Style Guide for Python Code](https://peps.python.org/pep-0008/)
- [PEP 20 — The Zen of Python](https://peps.python.org/pep-0020/)
- [PEP 257 — Docstring Conventions](https://peps.python.org/pep-0257/)
- [PEP 484 — Type Hints](https://peps.python.org/pep-0484/)
- [PEP 544 — Protocols](https://peps.python.org/pep-0544/)
- [Google Python Style Guide](https://google.github.io/styleguide/pyguide.html)

### Ferramentas essenciais
- [Ruff — linter e formatador](https://docs.astral.sh/ruff/)
- [Ruff formatter](https://docs.astral.sh/ruff/formatter/)
- [mypy](https://www.mypy-lang.org/)
- [pip](https://pip.pypa.io/) · [venv](https://docs.python.org/3/library/venv.html)
- [pip-audit](https://pypi.org/project/pip-audit/) · [bandit](https://bandit.readthedocs.io/)

### Testes e desempenho
- [pytest](https://docs.pytest.org/)
- [unittest.mock](https://docs.python.org/3/library/unittest.mock.html)
- [testcontainers-python](https://github.com/testcontainers/testcontainers-python)
- [py-spy](https://github.com/benfred/py-spy) · [memray](https://github.com/bloomberg/memray)
- [locust](https://locust.cloud/)

### Stack da trilha
- [LangChain (Python)](https://docs.langchain.com/oss/python/) · [migração v1](https://docs.langchain.com/oss/python/migrate/langchain-v1)
- [Pydantic](https://docs.pydantic.dev/) · [structlog](https://www.structlog.org/)
- [FastAPI](https://fastapi.tiangolo.com/) · [uvicorn](https://www.uvicorn.org/) — projetos que expõem o contrato HTTP

### Vector stores da trilha
Um por projeto, de propósito. Ao comparar dois, leia os adaptadores em `repository/`,
não o fluxo — o `Protocol VectorRepository` esconde exatamente a diferença que interessa.
- [Chroma](https://docs.trychroma.com/) — Projeto 1
- [Qdrant](https://qdrant.tech/documentation/) · [langchain-qdrant](https://python.langchain.com/docs/integrations/vectorstores/qdrant/) — Projeto 2

### Comunidade
- [Python Discourse](https://discuss.python.org/)
- [Awesome Python](https://github.com/vinta/awesome-python)
