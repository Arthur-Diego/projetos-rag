"""Produz a tabela de medição: 10 perguntas x 3 configurações.

**GASTA CHAMADAS PAGAS.** Uma de embedding por pergunta e por configuração (30),
mais uma de geração por pergunta e por configuração se a taxa de recusa for
pedida (mais 30). Com `gpt-4o-mini` e `text-embedding-3-small` isso custa
centavos, mas custa.

Exige o Elasticsearch no ar e o índice populado:

    docker compose up -d elasticsearch
    python ingest.py
    python docs/operations/tabela-medicao.py

**Este é o entregável do projeto, não o script.** O que importa é a tabela que
ele imprime.

Como o acerto é medido (ADR-002 da feature): cada pergunta tem, anotado à mão em
`perguntas.json`, o conjunto de páginas que sustentam a resposta. Uma
configuração acerta quando um dos trechos finais entregues ao modelo vem de uma
dessas páginas. As anotações foram ancoradas por busca literal no PDF, nunca
pelo sistema medido, senão a medição seria circular.

A taxa de recusa é registrada ao lado. Ela não define acerto (uma resposta
errada, confiante e com citação contaria como sucesso, e esse é o modo de falha
mais perigoso de um RAG), mas é a métrica que o Projeto 2 mediu, e mantê-la é o
que torna os dois projetos comparáveis.
"""

import argparse
import json
import sys
import time
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from elasticsearch import Elasticsearch  # noqa: E402

from rag import config  # noqa: E402
from rag.domain.models import Conversation  # noqa: E402
from rag.repository.keyword_repository import ElasticKeywordRepository  # noqa: E402
from rag.repository.vector_repository import ElasticVectorRepository  # noqa: E402
from rag.service.citation_resolver import CitationResolver  # noqa: E402
from rag.service.retrieval.dense_search_service import DenseSearchService  # noqa: E402
from rag.service.retrieval.fusion_service import FusionService  # noqa: E402
from rag.service.retrieval.keyword_search_service import (  # noqa: E402
    KeywordSearchService,
)
from rag.service.generation_service import (  # noqa: E402
    OpenAiGenerationService,
    create_embeddings,
)
from rag.service.prompt_builder import PromptBuilder  # noqa: E402
from rag.service.query_rewrite_service import QueryRewriteService  # noqa: E402
from rag.service.retrieval.rerank_service import CrossEncoderRerankService  # noqa: E402
from rag.service.retrieval.retrieval_service import RetrievalService  # noqa: E402
from rag.facade.query_facade import QueryFacade  # noqa: E402

#: As três colunas da tabela. São combinações dos MESMOS estágios: o caminho
#: denso sempre executa, e o que varia é acrescentar o léxico e a reordenação.
CONFIGURACOES = [
    ("só densa", {"hybrid": False, "rerank": False}),
    ("híbrida", {"hybrid": True, "rerank": False}),
    ("híbrida+rerank", {"hybrid": True, "rerank": True}),
]


def build(properties, client, generation, **funil) -> QueryFacade:
    return QueryFacade(
        rewrite=QueryRewriteService(generation),
        retrieval=RetrievalService(
            DenseSearchService(
                ElasticVectorRepository(
                    client=client,
                    index=properties.collection,
                    embeddings=create_embeddings(
                        properties.embedding_model,
                        properties.max_retries,
                        properties.request_timeout_s,
                    ),
                )
            ),
            keywords=KeywordSearchService(
                ElasticKeywordRepository(client, properties.collection)
            ),
            fusion=FusionService(),
            reranker=CrossEncoderRerankService(properties.reranker_model),
            **funil,
        ),
        prompts=PromptBuilder(),
        generation=generation,
        citations=CitationResolver(),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--sem-geracao",
        action="store_true",
        help="mede só o acerto de recuperação; nao gasta chamadas de geração",
    )
    parser.add_argument("--k", type=int, default=4)
    parser.add_argument("--candidates", type=int, default=20)
    parser.add_argument("--rrf-k", type=int, default=60)
    parser.add_argument(
        "--reranker",
        default=None,
        help=(
            "sobrescreve o modelo de reordenacao. Serve para isolar o efeito da "
            "LINGUA do modelo: o padrao e treinado em ingles e o corpus e em "
            "portugues. Ex.: cross-encoder/mmarco-mMiniLMv2-L12-H384-v1"
        ),
    )
    args = parser.parse_args()

    dados = json.loads((Path(__file__).parent / "perguntas.json").read_text())
    perguntas = dados["perguntas"]
    if not perguntas:
        print("arquivo de perguntas vazio: nao ha o que medir.", file=sys.stderr)
        return 1

    properties = config.load()
    if args.reranker:
        properties = replace(properties, reranker_model=args.reranker)
    client = Elasticsearch(properties.elastic_url)
    generation = OpenAiGenerationService(
        properties.chat_model,
        properties.temperature,
        properties.max_retries,
        properties.request_timeout_s,
    )

    print(f"corpus indexado : {dados['corpus']}")
    print(f"parametros      : k={args.k} candidates={args.candidates} rrf_k={args.rrf_k}")
    print(f"reranker        : {properties.reranker_model}")
    print(f"geracao         : {'DESLIGADA' if args.sem_geracao else 'ligada (gasta API)'}")
    print()

    resultados: dict[str, dict[str, dict]] = {}
    for nome, funil in CONFIGURACOES:
        facade = build(
            properties,
            client,
            generation,
            k=args.k,
            candidates=args.candidates,
            rrf_k=args.rrf_k,
            **funil,
        )
        resultados[nome] = {}
        for item in perguntas:
            esperadas = set(item["paginas"])
            inicio = time.perf_counter()

            if args.sem_geracao:
                retrieval = facade._retrieval.retrieve(item["pergunta"])
                hits, recusou = retrieval.hits, None
            else:
                answer = facade.ask(item["pergunta"], Conversation())
                hits, recusou = answer.hits, answer.refused

            resultados[nome][item["id"]] = {
                "acertou": any(h.page in esperadas for h in hits),
                "recusou": recusou,
                "paginas": [h.page for h in hits],
                "segundos": time.perf_counter() - inicio,
            }
            print(".", end="", flush=True)
    print("\n")

    # ---- a tabela ----
    largura = max(len(n) for n, _ in CONFIGURACOES) + 2
    categorias = ["conceitual", "identificador"]

    print("ACERTOS (trecho de pagina esperada entre os finais)")
    print(f"{'':22}" + "".join(f"{n:>{largura}}" for n, _ in CONFIGURACOES))
    for categoria in categorias:
        ids = [p["id"] for p in perguntas if p["categoria"] == categoria]
        linha = f"{categoria.capitalize()} ({len(ids)})".ljust(22)
        for nome, _ in CONFIGURACOES:
            certos = sum(1 for i in ids if resultados[nome][i]["acertou"])
            linha += f"{f'{certos}/{len(ids)}':>{largura}}"
        print(linha)
    total = f"TOTAL ({len(perguntas)})".ljust(22)
    for nome, _ in CONFIGURACOES:
        certos = sum(1 for r in resultados[nome].values() if r["acertou"])
        total += f"{f'{certos}/{len(perguntas)}':>{largura}}"
    print(total)

    if not args.sem_geracao:
        print("\nTAXA DE RECUSA (comparavel com o Projeto 2)")
        linha = "".ljust(22)
        for nome, _ in CONFIGURACOES:
            recusas = sum(1 for r in resultados[nome].values() if r["recusou"])
            linha += f"{f'{recusas}/{len(perguntas)}':>{largura}}"
        print("".ljust(22) + "".join(f"{n:>{largura}}" for n, _ in CONFIGURACOES))
        print(linha)

    print("\nLATENCIA MEDIA POR TURNO (s)")
    print("".ljust(22) + "".join(f"{n:>{largura}}" for n, _ in CONFIGURACOES))
    linha = "".ljust(22)
    for nome, _ in CONFIGURACOES:
        media = sum(r["segundos"] for r in resultados[nome].values()) / len(perguntas)
        linha += f"{f'{media:.2f}':>{largura}}"
    print(linha)

    print("\nDETALHE POR PERGUNTA")
    for item in perguntas:
        marcas = " ".join(
            f"{nome}={'OK' if resultados[nome][item['id']]['acertou'] else '--'}"
            for nome, _ in CONFIGURACOES
        )
        print(f"  {item['id']} [{item['categoria'][:5]}] {marcas}   {item['pergunta'][:52]}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
