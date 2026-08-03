"""As propriedades se validam na construção, não no uso.

O que se cobra aqui é a promessa do módulo: um `RagProperties` que existe é
válido. Nada nestes testes toca disco, rede ou API paga.
"""

import pytest

from rag.config import DEFAULT_PARTITION_STRATEGY, RagProperties
from rag.exceptions import InvalidConfigurationException


def test_estrategia_de_particao_invalida_e_recusada_na_construcao() -> None:
    """`PARTITION_STRATEGY` fora do conjunto aceito não vira objeto válido.

    Sem isto, um typo no `.env` (`hires`) cairia silenciosamente no caminho de
    contingência, e a ingestão inteira rodaria sem detectar tabela nenhuma —
    exatamente a falha silenciosa que o risco 1 do FDD descreve.
    """
    with pytest.raises(InvalidConfigurationException):
        RagProperties(openai_api_key="sk-teste", partition_strategy="hires")  # type: ignore[arg-type]


def test_porta_do_chroma_fora_da_faixa_e_recusada() -> None:
    with pytest.raises(InvalidConfigurationException):
        RagProperties(openai_api_key="sk-teste", chroma_port=0)


def test_defaults_apontam_para_o_container_deste_projeto() -> None:
    """8002 é a porta do rag-04; 8000 e 8001 são dos projetos 1 e 2 (ADR-001).

    O endpoint de saúde é `/api/v2/heartbeat`: na imagem 1.5.9 a v1 responde
    410 Gone, e apontar para lá reportaria o container saudável como morto.
    """
    properties = RagProperties(openai_api_key="sk-teste")

    assert properties.chroma_port == 8002
    assert properties.chroma_url == "http://localhost:8002"
    assert properties.health_url == "http://localhost:8002/api/v2/heartbeat"
    assert properties.partition_strategy == DEFAULT_PARTITION_STRATEGY == "hi_res"


def test_os_tres_diretorios_de_dados_sao_distintos() -> None:
    """Cache de partição, docstore e figuras têm ciclos de vida diferentes.

    O reset (task_04) zera os armazéns e PRESERVA o cache de partição; apontar
    dois deles para o mesmo lugar apagaria os minutos de `hi_res` junto.
    """
    properties = RagProperties(openai_api_key="sk-teste")

    diretorios = {
        properties.partition_cache_dir,
        properties.docstore_dir,
        properties.figures_dir,
    }
    assert len(diretorios) == 3
