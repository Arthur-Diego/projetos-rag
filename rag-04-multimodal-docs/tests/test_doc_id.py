"""T3.2 — o `doc_id` determinístico (ADR-003).

O que se cobra aqui é a promessa da qual dependem a idempotência inteira e a
segurança dos nomes de arquivo. Nada toca disco, rede ou API.
"""

from rag.domain.identity import compute_doc_id


def test_o_mesmo_conteudo_produz_o_mesmo_id_em_chamadas_diferentes() -> None:
    """A propriedade que economiza dinheiro.

    Se isto falhar, cada reingestão vira um índice duplicado e uma fatura nova —
    é exatamente o comportamento do `uuid.uuid4()` do guia, que o ADR-003
    rejeitou.
    """
    primeiro = compute_doc_id("tabela", "relatorio.pdf", "<table><td>129,6</td></table>")
    segundo = compute_doc_id("tabela", "relatorio.pdf", "<table><td>129,6</td></table>")

    assert primeiro == segundo


def test_conteudos_diferentes_produzem_ids_diferentes() -> None:
    base = compute_doc_id("texto", "relatorio.pdf", "a receita cresceu")

    assert base != compute_doc_id("texto", "relatorio.pdf", "a receita caiu")
    # Origem e tipo também desambiguam: o mesmo texto vindo de outro PDF é
    # outra unidade, com outra procedência.
    assert base != compute_doc_id("texto", "outro.pdf", "a receita cresceu")
    assert base != compute_doc_id("tabela", "relatorio.pdf", "a receita cresceu")


def test_a_serializacao_e_estavel_contra_ambiguidade_de_separador() -> None:
    """Duas unidades diferentes não podem colidir por causa do separador.

    Concatenar os três campos com um separador exigiria um caractere que nunca
    ocorre no conteúdo — e "nunca ocorre" é falso em corpus real. A serialização
    por JSON escapa por construção.
    """
    a = compute_doc_id("texto", "a.pdf", 'b.pdf","x')
    b = compute_doc_id("texto", 'a.pdf","x', "b.pdf")

    assert a != b


def test_o_id_e_seguro_como_nome_de_arquivo() -> None:
    """Path traversal neutralizado por CONSTRUÇÃO, não por sanitização.

    Os nomes dos arquivos do docstore e das figuras derivam deste valor. Um id
    que carregasse `/` ou `..` transformaria conteúdo de PDF em caminho de
    escrita — e o corpus vem de fora.
    """
    hostil = compute_doc_id("texto", "../../etc/passwd", "../../../etc/shadow\x00/")

    assert len(hostil) == 64
    assert all(caractere in "0123456789abcdef" for caractere in hostil)
