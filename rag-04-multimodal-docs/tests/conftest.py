"""Raiz da suíte.

Os testes rodam a partir da raiz do projeto, então `rag` e `composition` são
importáveis sem instalação. Este arquivo existe para fixar isso e para
concentrar o caminho do corpus, usado pelo smoke test de partição.
"""

from pathlib import Path

import pytest

import rag.config

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(autouse=True)
def sem_dotenv(monkeypatch: pytest.MonkeyPatch) -> None:
    """Nenhum teste lê o `.env` do autor. Autouse, e isto NÃO é excesso de zelo.

    Foi um incidente real, encontrado na task_04. `config.load()` chama
    `load_dotenv(ROOT/'.env')`, e `load_dotenv` PREENCHE a variável que não
    existe no ambiente. O teste que apagava `OPENAI_API_KEY` para provar que
    configuração ausente vira 500 passou a receber a chave de volta do arquivo:
    a rota seguiu adiante, o corpus real foi particionado com `hi_res` e a
    ingestão gastou uma chamada de resumo por tabela e uma de visão por figura —
    dinheiro do autor, num `pytest` sem argumento.

    O escopo de teste fixado em `docs/guidelines/README.md` diz que a suíte não
    toca API paga. Esta fixture é o que torna isso verdadeiro por construção, em
    vez de depender de a máquina não ter um `.env`.
    """
    monkeypatch.setattr(rag.config, "load_dotenv", lambda *a, **kw: False)

#: Corpus do projeto. É o mesmo PDF do critério de sucesso do guia ("qual foi a
#: receita no 3T24?"), e não um fixture sintético: o que o smoke test precisa
#: provar é que o setup nativo particiona ESTE arquivo.
CORPUS_PDF = ROOT / "pdfs" / "petrobras-desempenho-3t24.pdf"


@pytest.fixture(scope="session")
def corpus_pdf() -> Path:
    """O PDF do corpus, ou skip se ele não estiver na máquina.

    `pdfs/` fica fora do git (o `.gitignore` da raiz do workspace versiona só a
    estrutura), então um clone novo não tem o arquivo. Skip explícito é melhor
    que falha vermelha por um motivo que não é defeito de código.
    """
    if not CORPUS_PDF.exists():
        pytest.skip(f"corpus ausente: {CORPUS_PDF}")
    return CORPUS_PDF
