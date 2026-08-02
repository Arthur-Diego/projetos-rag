#!/usr/bin/env python3
"""Produz a tabela de medição do rag-04: acerto e recusa POR CLASSE DE ALVO.

**GASTA CHAMADAS PAGAS.** Uma embedagem por pergunta (14) e, sem
`--sem-geracao`, mais uma geração por pergunta (14). Com `text-embedding-3-small`
e `gpt-4o-mini` isso custa centavos — mas custa, e a tabela de uma tabela grande
entra no prompt em HTML íntegro, então `--k` alto custa mais do que parece.

Exige o Chroma no ar e os DOIS armazéns populados:

    docker compose up -d chroma
    .venv/bin/python ingest.py
    .venv/bin/python docs/operations/tabela-medicao.py --sem-geracao
    .venv/bin/python docs/operations/tabela-medicao.py --k 8

**Este é o entregável do projeto, não o script.** O que importa é a tabela que
ele imprime, registrada com data em `README.md`.

## O que este script mede, e por que separado por classe

O rag-04 tem três alvos com promessas DIFERENTES (adr-003 da sessão), e uma nota
única os mistura até virar ruído:

- `tabela`: valor exato de célula. É a promessa central e o critério do guia.
- `texto`: linha de base — é o que os projetos 1 a 3 já faziam.
- `imagem`: evidência QUALITATIVA. Nunca valor exato; o julgamento é humano, e o
  script imprime a resposta inteira para que ele seja possível.
- `negativo`: a resposta só existe no PDF do BCB, nunca indexado. Acerto é a
  RECUSA, e por isso esta classe some com `--sem-geracao`.

## Como o acerto é medido

Cada pergunta factual tem, anotada à mão em `perguntas.json`, uma **âncora
textual** que precisa aparecer literalmente em algum hit recuperado — no
`excerpt` ou, para tabela, no `content_html`. Âncora é TRECHO, nunca página: a
correção de 28/07 do rag-03 mostrou que acerto por página conta como sucesso um
trecho vizinho que não responde nada.

As âncoras foram extraídas do PDF com `pypdf`, **nunca pelo `unstructured` do
próprio sistema medido** — senão a medição seria circular e o sistema acertaria
por definição.

## A coluna que só existe neste projeto: HTML no hit

Para as perguntas de tabela o script reporta também se a âncora foi encontrada
dentro do `content_html`, e não apenas no resumo. **É a evidência do critério do
guia**: prova que o que chegou ao LLM foi a tabela íntegra vinda do docstore, e
não o resumo que estava no índice. Um acerto que só aparece no `excerpt` é um
acerto do resumo, e vale menos.

A taxa de recusa é registrada ao lado do acerto, como nos projetos 2 e 3. Ela não
define acerto (uma resposta errada, confiante e com citação contaria como
sucesso, e esse é o modo de falha mais perigoso de um RAG), mas as duas métricas
se checam: acerto subindo com recusa subindo denuncia medição otimista.
"""

import argparse
import json
import re
import sys
import time
import unicodedata
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from composition import build_chroma_client, build_query_facade  # noqa: E402
from rag import config  # noqa: E402
from rag.domain.models import SearchHit  # noqa: E402
from rag.exceptions import RagException  # noqa: E402
from rag.facade.query_facade import QueryFacade  # noqa: E402
from rag.presenter.console_reporter import ConsoleReporter  # noqa: E402

#: As quatro classes de alvo, na ordem em que saem na tabela. `negativo` é a
#: única cujo acerto NÃO é recuperação: é recusa.
CLASSES = ("tabela", "texto", "imagem", "negativo")

#: Classes cujo acerto é "a âncora literal apareceu em algum hit".
CLASSES_COM_ANCORA = ("tabela", "texto")

#: Sigla de uma letra por classe, para o ranking caber numa linha. `texto` e
#: `tabela` começam com a mesma letra, então a distinção é a CAIXA — e ela
#: precisa ser explícita, porque `kind[0]` colapsaria as duas em `t` e o
#: diagnóstico inteiro (veio tabela ou não?) se perderia.
SIGLA = {"texto": "t", "tabela": "T", "imagem": "i"}

TAG_PATTERN = re.compile(r"<[^>]+>")


def normaliza(texto: str) -> str:
    """Achata marcação, espaços, caixa e acentos para a comparação sobreviver.

    Quatro achatamentos, e cada um responde a uma deformação real do corpus:

    - **Tags viram espaço.** O original de uma tabela é HTML, e a âncora
      `Receita de vendas` vive partida em `<td>Receita de vendas</td>`. Sem
      trocar a tag por espaço, células vizinhas colariam (`vendas129.582`) e
      inventariam falso negativo — e, pior, falso positivo em outra combinação.
    - **Espaços colapsam.** A extração de PDF quebra linha no meio de frase e
      duplica espaço.
    - **Caixa some.** Título de coluna vem em maiúscula, o texto corrido não.
    - **Acentos somem.** O OCR do `hi_res` come acento com frequência
      (`execucao`, `6leo`), e uma medição que reprovasse por causa de um til
      estaria medindo tipografia, não recuperação.
    """
    sem_tags = TAG_PATTERN.sub(" ", texto)
    sem_acentos = "".join(
        caractere
        for caractere in unicodedata.normalize("NFD", sem_tags)
        if not unicodedata.combining(caractere)
    )
    return re.sub(r"\s+", " ", sem_acentos).strip().lower()


def ancora_no_hit(ancora: str, hit: SearchHit) -> bool:
    """A âncora aparece na representação ou no original desse hit?

    Os dois campos, e não só um: `excerpt` carrega a representação (o resumo,
    para tabela) e `content_html` o original íntegro. Procurar só no `excerpt`
    reprovaria o pipeline justamente onde ele funciona — o número da célula vive
    no HTML, e é ele que chega ao LLM.
    """
    alvo = normaliza(ancora)
    return alvo in normaliza(hit.excerpt) or (
        hit.content_html is not None and alvo in normaliza(hit.content_html)
    )


def ancora_no_html(ancora: str, hits: tuple[SearchHit, ...]) -> bool:
    """A âncora está no HTML ORIGINAL de alguma tabela recuperada?

    Esta é a evidência do critério do guia, e ela é mais forte que `acertou`: diz
    que a resposta veio da tabela íntegra resolvida no docstore, e não do resumo
    que estava indexado.
    """
    alvo = normaliza(ancora)
    return any(
        hit.kind == "tabela"
        and hit.content_html is not None
        and alvo in normaliza(hit.content_html)
        for hit in hits
    )


def avalia(item: dict[str, Any], hits: tuple[SearchHit, ...], recusou: bool | None) -> bool | None:
    """Aplica o critério de acerto da CLASSE da pergunta.

    Devolve `None` quando a classe não é mensurável na execução corrente — hoje
    isso acontece só com `negativo` sob `--sem-geracao`, cujo acerto é a recusa e
    portanto exige geração. `None` sai da tabela como `n/a`, e não como zero:
    reportar "0 acertos" para o que não foi medido seria mentira barata.
    """
    classe = item["classe"]
    if classe in CLASSES_COM_ANCORA:
        return any(ancora_no_hit(item["ancora"], hit) for hit in hits)
    if classe == "imagem":
        # Recuperação, e só ela: "a descrição da imagem chegou ao contexto?".
        # Se a RESPOSTA reflete o gráfico é julgamento humano (adr-003), feito
        # sobre o texto que o detalhe imprime.
        return any(hit.kind == "imagem" for hit in hits)
    if classe == "negativo":
        return recusou
    raise ValueError(f"classe desconhecida em perguntas.json: {classe!r}")


def mede(
    facade: QueryFacade, perguntas: list[dict[str, Any]], sem_geracao: bool
) -> dict[str, dict[str, Any]]:
    """Roda o golden set e devolve o resultado cru, por id de pergunta.

    Recebe a facade PRONTA em vez de construí-la: é o que torna esta função
    testável sem Chroma, sem OpenAI e sem custo (T6.3). O `--sem-geracao` é
    honrado aqui dentro, chamando a recuperação em vez do `ask` — não adianta
    gerar e descartar.
    """
    resultados: dict[str, dict[str, Any]] = {}
    for item in perguntas:
        inicio = time.perf_counter()

        if sem_geracao:
            hits = facade.retrieve(item["pergunta"]).hits
            recusou: bool | None = None
            resposta = ""
        else:
            answer = facade.ask(item["pergunta"])
            hits, recusou, resposta = answer.hits, answer.refused, answer.text

        resultados[item["id"]] = {
            "acertou": avalia(item, hits, recusou),
            "recusou": recusou,
            "html_no_hit": (
                ancora_no_html(item["ancora"], hits)
                if item["classe"] == "tabela"
                else None
            ),
            "kinds": [hit.kind for hit in hits],
            "paginas": [hit.page for hit in hits],
            "resposta": resposta,
            "segundos": time.perf_counter() - inicio,
        }
        print(".", end="", flush=True)
    print("\n")
    return resultados


def _fracao(ids: list[str], resultados: dict[str, dict[str, Any]], campo: str) -> str:
    """`n/N` contando só o que foi medido; `n/a` quando nada foi."""
    medidos = [i for i in ids if resultados[i][campo] is not None]
    if not medidos:
        return "n/a"
    return f"{sum(1 for i in medidos if resultados[i][campo])}/{len(medidos)}"


def imprime(
    perguntas: list[dict[str, Any]],
    resultados: dict[str, dict[str, Any]],
    sem_geracao: bool,
) -> None:
    """A tabela. É o entregável; tudo acima existe para produzi-la."""
    por_classe = {
        classe: [p["id"] for p in perguntas if p["classe"] == classe]
        for classe in CLASSES
    }

    print("ACERTO POR CLASSE DE ALVO")
    print("  tabela/texto = âncora literal em algum hit recuperado")
    print("  imagem       = algum hit com kind=imagem (o resto é julgamento humano)")
    print("  negativo     = recusou, que é o acerto desta classe")
    print()
    for classe in CLASSES:
        ids = por_classe[classe]
        if not ids:
            continue
        print(f"  {classe:<10} ({len(ids)})  {_fracao(ids, resultados, 'acertou'):>5}")

    if not sem_geracao:
        print("\nTAXA DE RECUSA POR CLASSE (comparável com os projetos 2 e 3)")
        print("  Alta em `negativo` é ACERTO; alta nas demais é sintoma.")
        print()
        for classe in CLASSES:
            ids = por_classe[classe]
            if not ids:
                continue
            print(
                f"  {classe:<10} ({len(ids)})  {_fracao(ids, resultados, 'recusou'):>5}"
            )

    tabelas = por_classe["tabela"]
    if tabelas:
        print("\nEVIDÊNCIA DO CRITÉRIO DO GUIA: a âncora veio do HTML ORIGINAL?")
        print("  Acerto que só aparece no resumo é acerto do RESUMO, e vale menos.")
        print()
        print(f"  âncora no content_html   {_fracao(tabelas, resultados, 'html_no_hit')}")

    print("\nDETALHE POR PERGUNTA")
    for item in perguntas:
        r = resultados[item["id"]]
        marca = {True: "OK", False: "--", None: "n/a"}[r["acertou"]]
        html = {True: " [html]", False: "", None: ""}[r["html_no_hit"]]
        guia = "  <- critério do guia" if item.get("criterio_do_guia") else ""
        # `kinds` e `paginas` saem lado a lado, na ORDEM do ranking: é o que
        # permite ver, quando o acerto falha, se a tabela certa nem apareceu ou
        # se apareceu a tabela errada. Os dois diagnósticos pedem correções
        # opostas (recuperação × representação), e sem as páginas eles são
        # indistinguíveis.
        ranking = " ".join(
            f"{SIGLA[kind]}{pagina}" for kind, pagina in zip(r["kinds"], r["paginas"])
        )
        print(
            f"  {item['id']:<3} [{item['classe']:<8}] {marca:<3}{html}"
            f"  {r['segundos']:.2f}s{guia}"
        )
        print(f"      {item['pergunta']}")
        print(f"      ranking: {ranking or '-'}")

    # O modo de falha mais perigoso de um RAG não é a recusa: é a resposta
    # confiante sem evidência. Ele mora exatamente na diferença entre as duas
    # métricas — não recusou, mas a âncora não estava em hit nenhum — e some
    # numa tabela de frações. Cada uma destas linhas pede conferência humana.
    suspeitas = [
        item
        for item in perguntas
        if item["classe"] in CLASSES_COM_ANCORA
        and resultados[item["id"]]["acertou"] is False
        and resultados[item["id"]]["recusou"] is False
    ]
    if suspeitas:
        print("\nRESPOSTA SEM ÂNCORA (respondeu sem que a evidência fosse recuperada)")
        print("  Confira à mão: é o modo de falha que a taxa de recusa NÃO pega.")
        for item in suspeitas:
            print(f"\n  {item['id']}: {item['pergunta']}")
            print(f"    âncora esperada : {item['ancora']}")
            print(f"    resposta        : {resultados[item['id']]['resposta'].strip()}")

    qualitativas = [p for p in perguntas if p["classe"] == "imagem"]
    if qualitativas and not sem_geracao:
        print("\nJULGAMENTO QUALITATIVO (adr-003: imagem não promete valor exato)")
        print("  Leia e decida: a resposta reflete o que o gráfico mostra?")
        for item in qualitativas:
            print(f"\n  {item['id']}: {item['pergunta']}")
            print(f"    esperado : {item['esperado_qualitativo']}")
            print(f"    resposta : {resultados[item['id']]['resposta'].strip()}")

    media = sum(r["segundos"] for r in resultados.values()) / len(resultados)
    print(f"\nLATÊNCIA MÉDIA POR PERGUNTA: {media:.2f}s")


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Mede acerto de recuperação e taxa de recusa por classe de alvo. "
            "GASTA CHAMADAS PAGAS."
        )
    )
    parser.add_argument(
        "--sem-geracao",
        action="store_true",
        help=(
            "mede só o acerto de recuperação; não gasta chamada de geração. A "
            "classe `negativo` sai como n/a: o acerto dela é a recusa."
        ),
    )
    parser.add_argument(
        "--k",
        type=int,
        default=8,
        help=(
            "quantos trechos recuperar, de 1 a 20 (padrão: 8, e não o 4 do "
            "contrato: a tabela certa deste corpus costuma ficar em 3º ou 7º)"
        ),
    )
    args = parser.parse_args()

    dados = json.loads((Path(__file__).parent / "perguntas.json").read_text())
    perguntas = dados["perguntas"]
    if not perguntas:
        print("arquivo de perguntas vazio: não há o que medir.", file=sys.stderr)
        return 1

    reporter = ConsoleReporter()
    try:
        properties = config.load()
        facade = build_query_facade(
            properties, build_chroma_client(properties), reporter, k=args.k
        )
        # Índice vazio para aqui, antes de qualquer embedagem paga.
        total = facade.open_index(properties.collection)
    except RagException as e:
        reporter.failure(str(e))
        return 1

    print(f"corpus indexado : {dados['corpus']} ({total} representações)")
    print(f"fora do corpus  : {dados['fora_do_corpus']} (controle negativo)")
    print(f"parâmetros      : k={args.k}")
    print(f"geração         : {'DESLIGADA' if args.sem_geracao else 'ligada (GASTA API)'}")
    print()

    try:
        resultados = mede(facade, perguntas, args.sem_geracao)
    except RagException as e:
        reporter.failure(str(e))
        return 1

    imprime(perguntas, resultados, args.sem_geracao)
    return 0


if __name__ == "__main__":
    sys.exit(main())
