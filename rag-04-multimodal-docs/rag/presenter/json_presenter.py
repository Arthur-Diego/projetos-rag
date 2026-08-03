"""Apresentação em JSON, conforme `../docs/contracts/rag-api.yaml` 1.3.0.

Irmão do `ConsoleReporter`: mesma camada, mesmo papel, saída diferente. A
existência dos dois é a prova de que a facade valeu.

Regra da camada: **nada aqui decide o que fazer, só como mostrar.**

Regra dura herdada do rag-03: **campo opcional ausente é OMITIDO, nunca
emitido como `null`.** Um cliente do contrato 1.2.0 não pode receber uma chave
que ele não conhece com valor nulo e ter que distinguir "ausente" de "vazio".

Neste projeto a regra ganhou um caso com significado próprio: `content_html`
presente equivale a "este hit é uma tabela e o original está aqui". Emiti-lo
como `null` em hits de texto faria todo cliente ter que testar o valor além da
presença, e um cliente 1.2.0 receberia uma chave desconhecida com valor nulo.
"""

from ..domain.models import Answer, ElementCounts, IngestionReport, SearchHit

EXCERPT_CHARS = 280
"""Teto do trecho exibível, o mesmo do rag-03.

`excerpt` é para EXIBIÇÃO, não é o que vai ao modelo — o que vai ao modelo é o
original íntegro, montado pelo `PromptBuilder`. Cortar aqui não perde
informação nenhuma da resposta; deixar de cortar encheria a lista de fontes do
frontend com uma unidade de texto inteira.
"""


class JsonPresenter:
    """Converte objetos de domínio no formato do contrato compartilhado."""

    def hit(self, hit: SearchHit) -> dict:
        """Serializa um trecho recuperado, no `SearchHit` da 1.3.0.

        **`content_html` sai APENAS com `kind=tabela`**, e é invariante da seção
        6 do FDD, não detalhe de serialização: o campo carrega HTML de documento
        de origem externa, e o cliente sanitiza antes de pôr no DOM. Emiti-lo em
        hit de texto ensinaria o frontend a esperá-lo em qualquer lugar.

        **HTML nunca entra em `excerpt`.** Aqui isso é consequência de onde o
        dado vem: `excerpt` é a REPRESENTAÇÃO (o trecho, o resumo da tabela, a
        descrição da imagem), e a marcação mora só no `content`.

        `provenance` não é emitido em projeto nenhum aqui: só existe caminho
        denso, e um objeto de procedência com um caminho só seria ruído que o
        frontend exibiria como se houvesse escolha.
        """
        body: dict = {
            "source": hit.source,
            "page": hit.page,
            "kind": hit.kind,
            "excerpt": " ".join(hit.excerpt.split())[:EXCERPT_CHARS],
        }
        if hit.score is not None:
            body["score"] = round(hit.score, 6)
        if hit.kind == "tabela" and hit.content_html:
            body["content_html"] = hit.content_html
        return body

    def answer(self, answer: Answer) -> dict:
        """Serializa a resposta no `Answer` do contrato.

        `citations` e `rewritten_question` são OMITIDOS, não vazios: este
        projeto não resolve citação por afirmação nem reescreve pergunta
        (adr-002 da sessão), e `citations: []` diria "procurei e não achei", que
        é afirmação diferente de "este backend não faz isso".

        Os tempos saem arredondados em milissegundos: precisão maior seria ruído
        numa medida dominada por chamada de rede.
        """
        return {
            "text": answer.text,
            "refused": answer.refused,
            "hits": [self.hit(h) for h in answer.hits],
            "timings": {
                name: round(value, 3) for name, value in answer.timings.items()
            },
        }

    def elements(self, counts: ElementCounts) -> dict:
        """As três contagens, SEMPRE presentes quando o objeto está presente.

        A regra da omissão de opcionais para no nível do objeto `elements`: ele
        é opcional, mas o contrato declara `required: [textos, tabelas, imagens]`
        DENTRO dele. Omitir `tabelas` por ser zero seria dizer "não sei", e "não
        sei" e "procurei e não achei" são afirmações diferentes — a segunda é o
        sinal do risco 1.
        """
        return {
            "textos": counts.textos,
            "tabelas": counts.tabelas,
            "imagens": counts.imagens,
        }

    def ingestion(self, report: IngestionReport) -> dict:
        """O `IngestionReport` do contrato.

        Os campos do rag-03 que não existem aqui (`discarded_pages`,
        `previous_chunks`, `chunk_size`, `chunk_overlap`) são omitidos, não
        zerados: são opcionais no contrato e nenhum deles tem significado numa
        ingestão que reconcilia em vez de recriar. `previous_chunks: 0` seria
        especialmente enganoso — diria "não havia nada antes" quando o correto é
        "nada foi descartado, por desenho".
        """
        return {
            "pages": report.pages,
            "chunks": report.chunks,
            "seconds": round(report.seconds, 2),
            "elements": self.elements(report.elements),
        }

    def problem(self, title: str, detail: str, code: str) -> dict:
        # A mensagem das exceções já é multilinha e acionável; aqui ela vira uma
        # linha só, porque o destino é uma caixa de erro, não um terminal.
        return {
            "title": title,
            "detail": " ".join(detail.split()),
            "code": code,
        }
