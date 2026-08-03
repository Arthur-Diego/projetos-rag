"""T2.1/T2.2 — regressão do contrato compartilhado 1.3.0.

A rodada de revisão 001 apontou que a aditividade só estava conferida por
inspeção. Este teste crava o que a 1.3.0 promete: uma versão futura que mexer
num `required` ou tirar um campo novo quebra AQUI, não no primeiro consumidor.
"""

from pathlib import Path

import yaml

CONTRACT = (
    Path(__file__).resolve().parent.parent.parent / "docs" / "contracts" / "rag-api.yaml"
)


def _spec() -> dict:
    spec = yaml.safe_load(CONTRACT.read_text(encoding="utf-8"))
    assert isinstance(spec, dict)
    return spec


def test_versao_e_required_intactos() -> None:
    """T2.1 — o yaml parseia e a aditividade estrutural se mantém."""
    spec = _spec()
    assert spec["info"]["version"] == "1.3.0"

    schemas = spec["components"]["schemas"]
    assert schemas["SearchHit"]["required"] == ["source"]
    assert schemas["IngestionReport"]["required"] == ["pages", "chunks", "seconds"]
    assert schemas["Answer"]["required"] == ["text", "hits", "refused", "timings"]


def test_campos_novos_da_1_3_0() -> None:
    """T2.2 — os campos do ADR-004 existem, opcionais e com os tipos fixados."""
    spec = _spec()
    schemas = spec["components"]["schemas"]

    hit = schemas["SearchHit"]["properties"]
    assert hit["kind"]["enum"] == ["texto", "tabela", "imagem"]
    assert hit["content_html"]["type"] == "string"

    elements = schemas["IngestionReport"]["properties"]["elements"]
    assert sorted(elements["required"]) == ["imagens", "tabelas", "textos"]
    for campo in ("textos", "tabelas", "imagens"):
        assert elements["properties"][campo]["type"] == "integer"

    health = spec["paths"]["/health"]["get"]["responses"]["200"]
    docstore = health["content"]["application/json"]["schema"]["properties"][
        "docstore_originals"
    ]
    assert docstore["type"] == "integer"
