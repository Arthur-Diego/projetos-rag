"""AC-1/EC-2 da US-005 — o script de inspeção, contra um cache sintético.

Critério da seção 9 do FDD que estava sem teste (rodada de revisão 001). O
script é ferramenta de operação com nome hifenizado, então a importação é por
caminho; o cache é pré-populado para que NADA seja particionado — o teste prova
a listagem, a marcação de suspeita e o custo zero, não o `hi_res`.
"""

import importlib.util
import sys
from pathlib import Path

import pytest
from unstructured.documents.elements import ElementMetadata, Table

from rag import config
from rag.config import RagProperties
from rag.repository.pdf_partitioner import FilePartitionCache, content_hash

SCRIPT = (
    Path(__file__).resolve().parent.parent
    / "docs"
    / "operations"
    / "inspeciona-tabelas.py"
)


def _load_script():  # type: ignore[no-untyped-def]
    spec = importlib.util.spec_from_file_location("inspeciona_tabelas", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _table(page: int, html: str | None, text: str) -> Table:
    meta = ElementMetadata(page_number=page, text_as_html=html)
    return Table(text, metadata=meta)


def test_lista_tabelas_do_cache_com_marcacao_de_suspeita(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    pdf_dir = tmp_path / "pdfs"
    pdf_dir.mkdir()
    pdf = pdf_dir / "relatorio.pdf"
    pdf.write_bytes(b"%PDF-fake")

    properties = RagProperties(
        openai_api_key="sk-teste",
        pdf_dir=pdf_dir,
        docstore_dir=tmp_path / "docstore",
        partition_cache_dir=tmp_path / "particao",
        figures_dir=tmp_path / "figuras",
        partition_strategy="hi_res",
    )
    # Cache pré-populado sob a MESMA chave que o serviço calcula: o script tem
    # que listar sem particionar nada (é o "sem custo" do AC-1).
    cache = FilePartitionCache(properties.partition_cache_dir, "hi_res")
    cache.save(
        content_hash(pdf),
        [
            _table(3, "<table><tr><td>129,6</td></tr></table>", "129,6"),
            _table(7, None, "sopa de números sem estrutura"),
        ],
    )

    modulo = _load_script()
    monkeypatch.setattr(config, "load", lambda **kw: properties)
    monkeypatch.setattr(modulo, "config", config)
    monkeypatch.setattr(sys, "argv", ["inspeciona-tabelas.py"])

    assert modulo.main() == 0

    saida = capsys.readouterr()
    assert "2 tabela(s) detectada(s)" in saida.out
    assert "página 3" in saida.out
    assert "página 7" in saida.out
    assert "SUSPEITA" in saida.out, "tabela sem HTML tem que sair marcada, não sumir"
    assert "total: 2 tabela(s), 1 suspeita(s)" in saida.out
