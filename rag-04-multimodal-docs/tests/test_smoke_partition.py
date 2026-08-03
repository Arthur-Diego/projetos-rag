"""T1.1 — smoke test do setup: o `unstructured` particiona o corpus.

Isto é o teste do RISCO 2 do FDD ("o setup nativo quebra no WSL2"): ele existe
para transformar uma quebra de ambiente em falha vermelha explícita, num
segundo, em vez de num traceback no meio de uma ingestão de minutos.

**Roda com `strategy="fast"`, não `hi_res`, e a escolha é deliberada.** `fast` lê
apenas a camada de texto do PDF: sobe em segundos, não depende de poppler nem de
tesseract e não baixa modelo de layout. O que ele prova é a metade do setup que
é pré-requisito de tudo — que a biblioteca importa, que o PDF é legível e que
sai elemento do outro lado. `hi_res` de verdade (com `infer_table_structure` e
extração de imagens) é caro demais para uma suíte, e é exercitado na task_03,
onde o cache de partição (ADR-005) paga o custo uma vez só.

Consequência honesta: este teste passando NÃO prova que o `hi_res` funciona, e
portanto não prova que as tabelas serão detectadas (risco 1). A verificação
nativa completa está registrada no README de setup.
"""

from pathlib import Path

import pytest


@pytest.mark.smoke
def test_particiona_o_corpus_sem_erro(corpus_pdf: Path) -> None:
    """Particionar o PDF do corpus termina sem exceção e devolve elementos."""
    from unstructured.partition.pdf import partition_pdf

    elements = partition_pdf(filename=str(corpus_pdf), strategy="fast")

    assert len(elements) > 0, (
        "a partição não devolveu elemento nenhum. Com strategy='fast' isso "
        "significa PDF sem camada de texto (escaneado) ou arquivo corrompido."
    )
