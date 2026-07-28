"""Fusão de rankings por Reciprocal Rank Fusion.

**Este é o componente mais importante do projeto e o mais barato de testar.**
Ele não tem dependência nenhuma: recebe listas, devolve lista. É por isso que
mora aqui e não dentro do RetrievalService (ADR-003) — lá, testá-lo exigiria
dublar dois repositórios e um serviço de rerank para exercitar uma função que
não depende de nenhum deles.

O problema que o RRF resolve: os dois caminhos devolvem valores incomparáveis.
BM25 devolve algo como 14.7, numa escala sem teto que depende da frequência dos
termos no corpus; a busca densa devolve algo como 0.83, limitada e medindo
ângulo. Não existe normalização honesta entre as duas, porque não medem a mesma
grandeza. Qualquer tentativa de normalizar por mínimo e máximo dos candidatos
torna a pontuação de um trecho dependente de quem mais foi recuperado junto com
ele, o que é instável entre execuções e mata a reprodutibilidade que a medição
exige.

O RRF resolve ignorando o valor e usando só a POSIÇÃO:

    score(d) = Σ  1 / (rrf_k + posição(d, r) + 1)
               r

para cada ranking `r` em que `d` aparece. Um trecho presente nos dois rankings
soma as duas contribuições, e é por isso que a fusão o promove.

Implementado em Python e não delegado ao retriever nativo do motor (ADR-002):
fundir à mão é o entendimento que o projeto existe para produzir, e mantém a
estratégia de fusão independente de onde os dados estão guardados.
"""

from ..domain.models import PATH_DENSE, PATH_KEYWORD, Provenance, SearchHit

#: Chave de identidade de um trecho, para deduplicação.
_Identity = tuple[str, int, str] | str


def _identity(hit: SearchHit) -> _Identity:
    """Identidade do trecho, para a fusão saber que dois hits são o mesmo.

    Prefere o identificador do armazém, que é exato. Sem ele (dublês de teste,
    ou adaptador que não o preencha), cai para a tripla completa fonte, página e
    texto INTEIRO.

    O que NUNCA é usado é um prefixo do texto. O guia da trilha usa
    `page_content[:200]`, e isso funde silenciosamente dois trechos distintos
    que compartilhem o começo, o que num corpus com cabeçalho repetido por
    página é o caso comum e não a exceção.
    """
    if hit.doc_id is not None:
        return hit.doc_id
    return (hit.source, hit.page, hit.text)


class FusionService:
    """Funde rankings por Reciprocal Rank Fusion.

    Classe concreta e não `Protocol`: existe uma implementação, e a guideline do
    workspace é explícita sobre não criar indireção para um implementador só. Se
    um projeto futuro fundir por outro critério que não posição, aí sim vira
    `Protocol`.
    """

    def fuse(
        self,
        rankings: list[tuple[str, list[SearchHit]]],
        rrf_k: int,
    ) -> list[SearchHit]:
        """Funde rankings rotulados e devolve a lista ordenada e deduplicada.

        Args:
            rankings: pares (nome do caminho, ranking). O nome viaja junto
                porque a `Provenance` precisa dizer DE QUAL caminho o trecho
                veio e em que posição ficou em cada um; uma lista de listas
                anônimas obrigaria o chamador a reconstruir isso por índice, e
                índice posicional é exatamente o tipo de acoplamento que produz
                erro silencioso quando alguém insere um caminho no meio.
            rrf_k: amortecimento. Baixo dá muito peso a quem ficou em primeiro;
                alto achata as diferenças até a fusão virar quase união simples.

        Returns:
            Trechos ordenados por pontuação decrescente, cada um com `score`
            preenchido (MAIOR é melhor) e `provenance` descrevendo o caminho
            percorrido. `distance` é preservada quando o trecho veio do caminho
            denso, e continua significando o que sempre significou.

        Empates são desempatados pela ordem de primeira aparição, o que torna a
        saída determinística. Sem isso, duas execuções idênticas poderiam
        produzir ordens diferentes e a tabela de medição não repetiria.
        """
        scores: dict[_Identity, float] = {}
        best: dict[_Identity, SearchHit] = {}
        ranks: dict[_Identity, dict[str, int]] = {}
        # Ordem de primeira aparição, para desempate determinístico. Guardada
        # como dict de posição, e não consultada com list.index() dentro do
        # sorted, que seria quadrático.
        first_seen: dict[_Identity, int] = {}

        for path, ranking in rankings:
            for position, hit in enumerate(ranking):
                key = _identity(hit)
                contribution = 1.0 / (rrf_k + position + 1)

                if key not in scores:
                    scores[key] = 0.0
                    best[key] = hit
                    ranks[key] = {}
                    first_seen[key] = len(first_seen)

                # Repetição do mesmo trecho DENTRO do mesmo ranking conta uma
                # vez, pela melhor posição. Somar de novo premiaria um defeito
                # do armazém como se fosse consenso entre caminhos.
                if path in ranks[key]:
                    continue

                scores[key] += contribution
                ranks[key][path] = position + 1  # 1-based, para humanos

                # Preserva a distância quando ela existe: o hit guardado pode ter
                # vindo do caminho léxico, que não tem distância nenhuma.
                if best[key].distance is None and hit.distance is not None:
                    best[key] = best[key]._replace(distance=hit.distance)

        fused = sorted(
            first_seen,
            key=lambda key: (-scores[key], first_seen[key]),
        )

        result: list[SearchHit] = []
        for key in fused:
            hit = best[key]
            per_path = ranks[key]
            result.append(
                hit._replace(
                    score=scores[key],
                    provenance=Provenance(
                        paths=tuple(per_path),
                        dense_rank=per_path.get(PATH_DENSE),
                        keyword_rank=per_path.get(PATH_KEYWORD),
                        rrf_score=scores[key],
                    ),
                )
            )
        return result
