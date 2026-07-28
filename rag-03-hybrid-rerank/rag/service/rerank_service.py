"""Reordenação dos candidatos por cross-encoder.

O último estágio do funil, e o que mais melhora a precisão.

**A distinção que justifica o estágio:**

- **Bi-encoder** (a busca densa): embeda pergunta e documento SEPARADAMENTE e
  compara os dois vetores. Rápido, escala para milhões, menos preciso.
- **Cross-encoder** (este): processa pergunta e documento JUNTOS, numa passada
  pela rede. Lento, não escala, muito mais preciso.

Daí o formato de funil: o bi-encoder escolhe algumas dezenas entre milhares, e o
cross-encoder escolhe poucos entre essas dezenas. Rodá-lo sobre o corpus inteiro
seria inviável; sobre 20 candidatos é barato.

**Duas ressalvas honestas, das duas que a pesquisa de contexto trouxe.**

A primeira é custo. O BEIR (Thakur et al., 2021, Tabela 3) mede 6,1 segundos
para rerankear top-100 em CPU, contra 450 ms em GPU. Extrapolando para 20 a 50
candidatos, algo entre 1,2 e 3,0 segundos por turno. Esta máquina não tem GPU. O
estágio fica ligado por padrão mesmo assim (ADR-001 da feature): o que se usa
precisa ser o que se mede, e `rerank_s` torna o custo visível em vez de sentido.

A segunda é que **reordenar nem sempre melhora**. Ainda no BEIR, o ganho médio
do rerank é de cerca de +11% em nDCG@10, mas a variância por conjunto de dados
vai de −26% (Touché-2020) a +47% (FiQA). Existe corpus em que o cross-encoder
degrada o resultado do BM25. É por isso que o estágio é desligável por
parâmetro e comparável na tabela, e não uma verdade assumida.

`Protocol` com uma implementação (ADR-004), diferente do `FusionService` que é
classe concreta. A indireção se paga aqui porque a segunda implementação já tem
nome e prazo: a API de rerank hospedada, que é o exercício 2 do guia. Com o
`Protocol`, ela entra como arquivo novo e uma linha no composition root.
"""

from typing import Protocol

from ..domain.models import Provenance, SearchHit
from ..exceptions import ServiceUnavailableException

#: Modelos carregados, por nome. **Cache de PROCESSO, e ele não é opcional.**
#:
#: O `provide_repository` do Projeto 2 é reconstruído a cada requisição HTTP.
#: Um provedor ingênuo deste serviço carregaria meio gigabyte de modelo por
#: `/ask`. É a mesma classe de defeito que o cache do vector store já corrigiu
#: uma vez lá, onde o comentário no código diz "isto não é micro-otimização; é
#: dinheiro". Aqui não é dinheiro, é o turno inteiro travando.
_LOADED: dict[str, object] = {}


class RerankService(Protocol):
    """Contrato do reordenador."""

    def rerank(
        self, question: str, hits: list[SearchHit], top_n: int
    ) -> list[SearchHit]:
        """Reordena por relevância e devolve os `top_n` melhores."""
        ...


class CrossEncoderRerankService:
    """Reordenação com cross-encoder local, em CPU (ADR-004).

    Não gasta API, e nenhum trecho do corpus sai da máquina neste estágio. É
    consequência colateral da escolha, e vale registrar porque vira argumento
    real caso o corpus um dia seja sensível.
    """

    def __init__(self, model_name: str) -> None:
        self._model_name = model_name

    def _model(self):
        """Carrega o modelo uma vez por processo e reaproveita.

        O import do `sentence_transformers` é local de propósito: ele arrasta o
        `torch`, que é a maior dependência da trilha, e custa segundos só para
        importar. Deixá-lo no topo do módulo faria QUALQUER entrypoint pagar
        esse custo, inclusive o `ingest.py`, que nunca reordena nada.

        Falha ao carregar vira indisponibilidade de serviço, **nunca** um
        silencioso "segue sem rerank". A matriz de erros do FDD é explícita: um
        fallback silencioso aqui produziria uma tabela de medição errada, que é
        precisamente o dano que este projeto existe para evitar.
        """
        if self._model_name not in _LOADED:
            try:
                from sentence_transformers import CrossEncoder

                _LOADED[self._model_name] = CrossEncoder(self._model_name)
            except Exception as e:
                raise ServiceUnavailableException(
                    f"não foi possível carregar o reordenador "
                    f"'{self._model_name}' ({type(e).__name__}).\n"
                    "       a primeira execução baixa cerca de 500 MB e precisa de rede;\n"
                    "       para rodar sem este estágio use --sem-rerank"
                ) from e
        return _LOADED[self._model_name]

    def rerank(
        self, question: str, hits: list[SearchHit], top_n: int
    ) -> list[SearchHit]:
        """Pontua cada par (pergunta, trecho) e devolve os melhores.

        A ordem de saída vem da pontuação do modelo, **não** da ordem de
        entrada. É o que o critério de aceite 4 verifica, com um dublê que
        inverte.

        O que é preservado do que já existia no hit, e por quê:

        - `distance`, quando o trecho passou pelo caminho denso. Decidido com o
          autor: o campo é emitido sempre que teve valor, em qualquer
          configuração, e só fica ausente no trecho que veio exclusivamente do
          BM25, onde ele nunca existiu.
        - `provenance`, acrescida de `rerank_score`. Jogar fora as posições que
          a fusão registrou apagaria o dado que responde "por que este trecho
          subiu", que é a pergunta do projeto inteiro.

        `score` passa a carregar a pontuação do reordenador, substituindo a da
        fusão. As duas concordam no sentido: MAIOR é melhor. A da fusão continua
        acessível em `provenance.rrf_score`, então nada se perde: dá para ver um
        trecho que a fusão pôs em quinto e o reordenador trouxe para primeiro,
        que é exatamente o caso que justifica o estágio.
        """
        if not hits:
            return []

        model = self._model()
        try:
            scores = model.predict([(question, hit.text) for hit in hits])
        except Exception as e:
            raise ServiceUnavailableException(
                f"o reordenador falhou ({type(e).__name__})."
            ) from e

        # `enumerate` no desempate mantém a ordem da fusão entre pontuações
        # iguais, o que torna a saída determinística. Sem isso, duas execuções
        # idênticas poderiam produzir ordens diferentes e a tabela não repetiria.
        ranked = sorted(
            enumerate(zip(hits, scores, strict=True)),
            key=lambda pair: (-float(pair[1][1]), pair[0]),
        )

        result: list[SearchHit] = []
        for _, (hit, score) in ranked[:top_n]:
            previous = hit.provenance or Provenance(paths=())
            result.append(
                hit._replace(
                    score=float(score),
                    provenance=previous._replace(rerank_score=float(score)),
                )
            )
        return result
