"""Testes da fusão RRF.

Nenhum dublê de infraestrutura aqui, e é esse o ponto: a fusão é função pura,
recebe listas e devolve lista. Foi para ficar assim que ela virou componente
próprio em vez de morar dentro do RetrievalService (ADR-003).

Cobre os critérios de aceite 1, 2 e 3 da seção 9 do FDD.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rag.domain.models import PATH_DENSE, PATH_KEYWORD, SearchHit  # noqa: E402
from rag.service.fusion_service import FusionService  # noqa: E402

RRF_K = 60


def hit(doc_id: str, *, distance: float | None = None, text: str = "") -> SearchHit:
    return SearchHit(
        text=text or f"texto de {doc_id}",
        source="harry-potter.pdf",
        page=1,
        doc_id=doc_id,
        distance=distance,
    )


def ids(hits: list[SearchHit]) -> list[str | None]:
    return [h.doc_id for h in hits]


# ---------------------------------------------------------------------------
# Critério 1: a fusão promove o consenso
# ---------------------------------------------------------------------------


def test_trecho_presente_nos_dois_rankings_fica_acima():
    """O trecho que os dois caminhos acharam vence o que só um achou.

    É a razão de existir da busca híbrida. Se este teste falhar, a fusão está
    somando errado ou deduplicando errado, e o projeto inteiro perde o sentido.

    Montagem: `consenso` está em 2º no denso e em 2º no BM25. `so_denso` está em
    1º no denso, e `so_bm25` em 1º no BM25. Cada um dos solitários tem UMA
    contribuição maior, mas o consenso tem DUAS.
    """
    fusion = FusionService()

    resultado = fusion.fuse(
        [
            (PATH_DENSE, [hit("so_denso"), hit("consenso")]),
            (PATH_KEYWORD, [hit("so_bm25"), hit("consenso")]),
        ],
        rrf_k=RRF_K,
    )

    assert ids(resultado)[0] == "consenso"
    # 2 × 1/(60+2) = 0.032258... contra 1/(60+1) = 0.016393...
    assert resultado[0].score > resultado[1].score


def test_provenance_distingue_os_dois_caminhos_de_um_so():
    """Sem isto a tabela de medição não tem como ser preenchida (ADR-003)."""
    fusion = FusionService()

    resultado = fusion.fuse(
        [
            (PATH_DENSE, [hit("consenso"), hit("so_denso")]),
            (PATH_KEYWORD, [hit("consenso")]),
        ],
        rrf_k=RRF_K,
    )

    por_id = {h.doc_id: h for h in resultado}

    consenso = por_id["consenso"].provenance
    assert consenso is not None
    assert set(consenso.paths) == {PATH_DENSE, PATH_KEYWORD}
    assert consenso.dense_rank == 1
    assert consenso.keyword_rank == 1

    solitario = por_id["so_denso"].provenance
    assert solitario is not None
    assert set(solitario.paths) == {PATH_DENSE}
    assert solitario.dense_rank == 2
    assert solitario.keyword_rank is None


def test_ranks_sao_1_based():
    """Ranks são para humanos lerem, como as páginas do PDF."""
    fusion = FusionService()

    resultado = fusion.fuse([(PATH_DENSE, [hit("primeiro")])], rrf_k=RRF_K)

    provenance = resultado[0].provenance
    assert provenance is not None
    assert provenance.dense_rank == 1


# ---------------------------------------------------------------------------
# Critério 2: a fusão depende de POSIÇÃO, nunca de valor
# ---------------------------------------------------------------------------


def test_multiplicar_os_scores_de_um_ranking_nao_muda_a_fusao():
    """Prova que é RRF, e não soma de valores disfarçada.

    Este é o teste que distingue a implementação correta da tentação óbvia. Se
    alguém trocar a fusão por "normaliza e soma", este teste quebra: as duas
    montagens abaixo têm as MESMAS posições e valores de distância
    absurdamente diferentes.
    """
    fusion = FusionService()

    modesto = [
        (PATH_DENSE, [hit("a", distance=0.1), hit("b", distance=0.2)]),
        (PATH_KEYWORD, [hit("b"), hit("c")]),
    ]
    absurdo = [
        (PATH_DENSE, [hit("a", distance=100.0), hit("b", distance=200.0)]),
        (PATH_KEYWORD, [hit("b"), hit("c")]),
    ]

    assert ids(fusion.fuse(modesto, RRF_K)) == ids(fusion.fuse(absurdo, RRF_K))


def test_rrf_k_alto_achata_as_diferencas():
    """Documenta o efeito do parâmetro que o exercício 1 do guia manda variar.

    Com k baixo, a diferença entre 1º e 2º é grande. Com k alto, as duas
    contribuições convergem. A ordem não muda; o que muda é a margem.
    """
    fusion = FusionService()
    ranking = [(PATH_DENSE, [hit("primeiro"), hit("segundo")])]

    baixo = fusion.fuse(ranking, rrf_k=1)
    alto = fusion.fuse(ranking, rrf_k=1000)

    margem_baixa = baixo[0].score - baixo[1].score
    margem_alta = alto[0].score - alto[1].score

    assert margem_baixa > margem_alta
    assert ids(baixo) == ids(alto) == ["primeiro", "segundo"]


# ---------------------------------------------------------------------------
# Critério 3: deduplicação por identidade do documento
# ---------------------------------------------------------------------------


def test_trechos_distintos_com_o_mesmo_prefixo_contam_como_dois():
    """A armadilha do guia da trilha, fixada em teste.

    O guia usa `page_content[:200]` como chave de deduplicação. Num corpus com
    cabeçalho repetido por página, dois trechos diferentes começam igual e
    seriam FUNDIDOS em silêncio, sumindo um deles do resultado sem erro nenhum.
    """
    prefixo = "Capítulo Um: O menino que sobreviveu. " * 10
    assert len(prefixo) > 200

    fusion = FusionService()
    resultado = fusion.fuse(
        [
            (
                PATH_DENSE,
                [
                    hit("chunk-1", text=prefixo + "primeiro final"),
                    hit("chunk-2", text=prefixo + "segundo final"),
                ],
            )
        ],
        rrf_k=RRF_K,
    )

    assert len(resultado) == 2
    assert set(ids(resultado)) == {"chunk-1", "chunk-2"}


def test_sem_doc_id_a_identidade_usa_o_texto_inteiro_nao_um_prefixo():
    """Dublês e adaptadores que não preencham doc_id continuam corretos."""
    prefixo = "x" * 500
    fusion = FusionService()

    a = SearchHit(text=prefixo + "A", source="f.pdf", page=1)
    b = SearchHit(text=prefixo + "B", source="f.pdf", page=1)

    resultado = fusion.fuse([(PATH_DENSE, [a, b])], rrf_k=RRF_K)

    assert len(resultado) == 2


def test_mesmo_trecho_repetido_dentro_de_um_ranking_conta_uma_vez():
    """Defeito do armazém não pode ser premiado como se fosse consenso."""
    fusion = FusionService()

    resultado = fusion.fuse(
        [(PATH_DENSE, [hit("repetido"), hit("repetido"), hit("outro")])],
        rrf_k=RRF_K,
    )

    assert ids(resultado).count("repetido") == 1
    # Vale a MELHOR posição: 1/(60+1), e não a segunda aparição.
    assert resultado[0].doc_id == "repetido"
    assert resultado[0].score == 1.0 / (RRF_K + 1)


def test_distancia_do_caminho_denso_sobrevive_a_fusao():
    """O hit guardado pode ter vindo do BM25, que não tem distância nenhuma."""
    fusion = FusionService()

    resultado = fusion.fuse(
        [
            (PATH_KEYWORD, [hit("comum")]),  # sem distância, e vem primeiro
            (PATH_DENSE, [hit("comum", distance=0.42)]),
        ],
        rrf_k=RRF_K,
    )

    assert resultado[0].distance == 0.42


# ---------------------------------------------------------------------------
# Determinismo e casos degenerados
# ---------------------------------------------------------------------------


def test_empate_e_desempatado_pela_ordem_de_aparicao():
    """Sem desempate estável, duas execuções idênticas dariam ordens diferentes
    e a tabela de medição não repetiria."""
    fusion = FusionService()
    entrada = [(PATH_DENSE, [hit("a")]), (PATH_KEYWORD, [hit("b")])]

    primeira = ids(fusion.fuse(entrada, RRF_K))
    segunda = ids(fusion.fuse(entrada, RRF_K))

    assert primeira == segunda == ["a", "b"]


def test_um_ranking_vazio_nao_impede_o_outro():
    """Um caminho que não achou nada não pode derrubar o que achou."""
    fusion = FusionService()

    resultado = fusion.fuse(
        [(PATH_DENSE, [hit("achou")]), (PATH_KEYWORD, [])],
        rrf_k=RRF_K,
    )

    assert ids(resultado) == ["achou"]


def test_todos_os_rankings_vazios_devolve_lista_vazia_sem_erro():
    fusion = FusionService()

    assert fusion.fuse([(PATH_DENSE, []), (PATH_KEYWORD, [])], RRF_K) == []
    assert fusion.fuse([], RRF_K) == []


def test_ranking_unico_preserva_a_ordem_de_entrada():
    """É o caminho de `hibrida=False`: a fusão sobre uma lista só não reordena."""
    fusion = FusionService()

    resultado = fusion.fuse(
        [(PATH_DENSE, [hit("primeiro"), hit("segundo"), hit("terceiro")])],
        rrf_k=RRF_K,
    )

    assert ids(resultado) == ["primeiro", "segundo", "terceiro"]
