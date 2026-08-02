"""T3.6 — a seleção de arquivos não desce em subdiretórios.

Teste pequeno para uma falha que não tem sintoma: `pdfs/fora-do-corpus/` é o
controle negativo da recusa (US-008). Se ele vazar para o índice, a recusa
simplesmente para de acontecer e a leitura vira "o grounding piorou".

É verificável por grep justamente porque é silencioso — e por isso vale um teste
que quebra vermelho no dia em que alguém trocar `*.pdf` por `**/*.pdf`.
"""

from pathlib import Path

import pytest

from rag.exceptions import EmptyCorpusException
from rag.repository.corpus_reader import PdfCorpusReader


@pytest.fixture
def corpus(tmp_path: Path) -> Path:
    (tmp_path / "petrobras.pdf").write_bytes(b"%PDF")
    (tmp_path / "balanco.pdf").write_bytes(b"%PDF")
    (tmp_path / "notas.txt").write_text("não é PDF", encoding="utf-8")

    fora = tmp_path / "fora-do-corpus"
    fora.mkdir()
    (fora / "bcb.pdf").write_bytes(b"%PDF")
    return tmp_path


def test_arquivos_fora_do_corpus_nunca_entram_na_selecao(corpus: Path) -> None:
    nomes = [path.name for path in PdfCorpusReader(corpus).files()]

    assert nomes == ["balanco.pdf", "petrobras.pdf"]
    assert "bcb.pdf" not in nomes


def test_diretorio_sem_pdf_falha_antes_de_qualquer_custo(tmp_path: Path) -> None:
    """EC-1 da US-001: erro claro ANTES dos minutos de CPU e do dinheiro."""
    with pytest.raises(EmptyCorpusException):
        PdfCorpusReader(tmp_path).require_files()
