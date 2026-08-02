"""Montagem do prompt de resposta.

É aqui que se compra o grounding, e é aqui que o projeto 4 se prova. As
instruções de fundamentação e de escape são herança dos projetos 1 a 3; o que
muda é o `format_context`.

**O critério de sucesso do guia é uma linha deste arquivo:** para um hit
`kind=tabela`, o que entra no contexto é o `content_html` — a tabela ORIGINAL,
vinda do docstore —, nunca o `excerpt`, que carrega o resumo que serviu para
buscar. Indexa-se o que embeda bem, entrega-se o que responde bem (ADR-002).
Trocar `hit.content_html` por `hit.excerpt` abaixo não produziria erro nenhum:
produziria respostas erradas com aparência normal, que é o modo de falha que
este projeto existe para expor.
"""

from ..domain.models import SearchHit
from .ingestion_log import IngestionLog, NullIngestionLog

ESCAPE_PHRASE = "Não encontrei essa informação nos documentos."
"""Contrato literal.

Os critérios de aceite comparam string, não interpretam. Mudar esta constante
quebra a validação do projeto.

É a MESMA string dos projetos 1 a 3, de propósito: a taxa de recusa só é
comparável entre eles se a frase for idêntica.
"""

MAX_TABLE_CHARS = 12_000
"""Teto de caracteres de UMA tabela dentro do contexto.

Contingência do risco 5 do FDD (tabela grande estoura contexto e custo). Alto de
propósito: o corte é a última linha de defesa, não a política — com `k=4` e o
default de contexto do `gpt-4o-mini`, uma tabela do corpus cabe inteira, e
truncar por hábito destruiria justamente a integridade que o projeto promete.

Quando o corte acontece, ele é REGISTRADO em log. Truncamento silencioso faria
uma resposta errada por falta da última linha da tabela parecer alucinação do
modelo.
"""

_TRUNCATION_MARK = (
    "\n<!-- TABELA TRUNCADA: as linhas seguintes foram cortadas por limite de "
    "contexto. Não afirme totais nem completude a partir desta tabela. -->"
)

# A frase de escape aparece no template SEM aspas nem delimitador. Com aspas, o
# modelo as copia para a resposta e quebra a comparação literal — defeito
# encontrado na validação do Projeto 1, não previsto.
_ANSWER_TEMPLATE = """Responda a pergunta usando SOMENTE o contexto abaixo.

O contexto traz trechos de um relatório, numerados. Alguns são texto, outros são
TABELAS EM HTML e outros são DESCRIÇÕES DE IMAGENS, e cada trecho vem marcado
com o seu tipo.

Cite as fontes no formato [n], usando o número que aparece antes de cada trecho,
ao final de cada afirmação que você fizer. Cite apenas números que existem no
contexto. Nunca invente um número.

Ao ler uma tabela em HTML, respeite a estrutura: o valor de uma célula pertence
ao cruzamento do seu cabeçalho de coluna com o da sua linha. Não some, não
calcule e não consolide nada que a tabela não traga pronto.

Ao usar uma descrição de imagem (gráfico), trate-a como evidência QUALITATIVA:
tendência, comparação e ordem de grandeza. Se a pergunta pedir um valor exato
que só existe num gráfico, ou marque a aproximação de forma explícita ("cerca
de", "aproximadamente"), ou recuse. Nunca apresente número preciso lido de
gráfico como se fosse exato.

Se o contexto não contiver a resposta, responda com esta frase exata, sem aspas,
sem markdown, sem citação e sem acrescentar nada antes ou depois:
{escape}

Nunca use conhecimento próprio. Nunca complete lacunas do contexto.

Contexto:
{context}

Pergunta: {question}"""

#: Rótulo de tipo que precede cada trecho. Explícito porque o modelo precisa
#: saber que está lendo marcação de tabela para respeitar linha e coluna, e
#: porque a instrução sobre gráfico só se aplica ao trecho certo.
_KIND_LABEL = {
    "texto": "texto",
    "tabela": "tabela em HTML, original íntegro",
    "imagem": "descrição de imagem gerada por modelo de visão",
}


class PromptBuilder:
    """Monta o prompt final a partir da pergunta e dos trechos recuperados."""

    def __init__(self, log: IngestionLog | None = None) -> None:
        """O log é opcional, como em todo consumidor da porta.

        Diagnóstico não é comportamento: um `PromptBuilder` que exigisse log
        para funcionar seria intestável sem dublê. Mas o tamanho do contexto e o
        truncamento SÃO observabilidade obrigatória (seção 7 do FDD), então
        quem monta o grafo de verdade sempre passa um.
        """
        self._log = log or NullIngestionLog()

    def format_context(self, hits: tuple[SearchHit, ...]) -> str:
        """Numera os trechos e entrega o ORIGINAL de cada um.

        A numeração é 1-based e é o que o modelo cita em `[n]`.

        **O que entra por tipo:** texto cru para `kind=texto`, HTML COMPLETO
        para `kind=tabela`, descrição para `kind=imagem`. Para texto e imagem,
        original e representação coincidem (multi-vector seletivo, ADR-002) e
        `excerpt` já é o original; para tabela eles divergem, e é o
        `content_html` que vale. Um hit `kind=tabela` sem `content_html` é
        inconsistência do emissor: aqui degrada para o resumo em vez de sumir
        com a fonte, e o log denuncia.

        O tamanho do contexto é logado em toda consulta: é a métrica do risco 5
        do FDD e o que permite atribuir custo ao estágio certo.
        """
        blocks = [
            f"[{position}] (fonte: {hit.source}, página {hit.page}, "
            f"tipo: {_KIND_LABEL.get(hit.kind, hit.kind)})\n"
            f"{self._original(position, hit)}"
            for position, hit in enumerate(hits, 1)
        ]
        context = "\n\n".join(blocks)
        tables = sum(1 for hit in hits if hit.kind == "tabela")
        self._log.stage(
            f"[contexto] {len(hits)} trecho(s), {tables} tabela(s) em HTML, "
            f"{len(context)} caractere(s) enviados ao modelo"
        )
        return context

    def build(self, question: str, hits: tuple[SearchHit, ...]) -> str:
        return _ANSWER_TEMPLATE.format(
            escape=ESCAPE_PHRASE,
            context=self.format_context(hits),
            question=question,
        )

    def _original(self, position: int, hit: SearchHit) -> str:
        """O conteúdo íntegro deste hit, truncado só se for grande demais."""
        if hit.kind == "tabela":
            if not hit.content_html:
                self._log.stage(
                    f"[contexto] ATENÇÃO: trecho [{position}] tem kind=tabela e "
                    "nenhum content_html; usando o resumo. O original não foi "
                    "resolvido no docstore — confira GET /health."
                )
                return hit.excerpt
            return self._truncated(position, hit.content_html)
        return hit.excerpt

    def _truncated(self, position: int, html: str) -> str:
        """Corta a tabela no teto e REGISTRA o corte. Nunca silencioso."""
        if len(html) <= MAX_TABLE_CHARS:
            return html
        self._log.stage(
            f"[contexto] ATENÇÃO: tabela do trecho [{position}] truncada de "
            f"{len(html)} para {MAX_TABLE_CHARS} caractere(s) (risco 5 do FDD). "
            "A resposta pode não refletir as linhas cortadas."
        )
        return html[:MAX_TABLE_CHARS] + _TRUNCATION_MARK
