"""Roteamento por categoria: elementos brutos viram unidades indexáveis.

**É o coração do padrão multi-vector, e a única tradução de `Element` do
`unstructured` para `DocumentUnit` do domínio.** Daqui para cima nada mais
conhece a biblioteca de partição.

Uma responsabilidade só, separada do `PartitionService` de propósito: a
partição responde "o que tem no PDF?" e custa minutos; o roteamento responde
"o que disso vira unidade, e de que tipo?" e custa microssegundos. Juntá-las
faria o teste do roteamento (T3.1, escopo fixado nas guidelines) depender de
particionar um PDF de verdade.

A regra que o desenho protege: **tabela e imagem NUNCA entram no agrupamento.**
Agrupar uma tabela com o parágrafo vizinho desfaria, numa linha, a separação que
o `hi_res` levou minutos para produzir — e o resultado seria o `PyPDFLoader` dos
projetos 1 a 3 com um custo muito maior.
"""

import shutil
from collections.abc import Sequence
from pathlib import Path

from unstructured.chunking.title import chunk_by_title
from unstructured.documents.elements import Element, Image, Table

from ..config import DEFAULT_MAX_CHARACTERS
from ..domain.identity import compute_doc_id
from ..domain.models import DocumentUnit, ElementCounts
from ..repository.pdf_partitioner import content_hash
from .ingestion_log import IngestionLog, NullIngestionLog


def count_elements(units: Sequence[DocumentUnit]) -> ElementCounts:
    """Contagem por categoria, com ZERO EXPLÍCITO no que não ocorreu.

    `ElementCounts` já nasce zerado, então uma categoria ausente sai como 0 e
    não como campo omitido. A distinção é toda a informação do relatório de uma
    extração multimodal: ausente significaria "não sei", e `tabelas: 0` num
    relatório financeiro significa "procurei e não achei" — o sinal do risco 1
    do FDD (T3.8, EC-3 da US-001).
    """
    return ElementCounts(
        textos=sum(1 for unit in units if unit.kind == "texto"),
        tabelas=sum(1 for unit in units if unit.kind == "tabela"),
        imagens=sum(1 for unit in units if unit.kind == "imagem"),
    )


def page_of(element: Element) -> int:
    """Página 1-based do elemento, ou 0 quando a biblioteca não soube dizer.

    0 é honesto e não é 1: reportar "página 1" para um elemento sem página
    conhecida faria a citação apontar para um lugar errado do PDF, que é pior
    que apontar para lugar nenhum.
    """
    page = getattr(element.metadata, "page_number", None)
    return int(page) if page else 0


class ElementRoutingService:
    """Transforma elementos brutos em unidades, uma decisão por categoria."""

    def __init__(
        self,
        figures_dir: Path,
        max_characters: int = DEFAULT_MAX_CHARACTERS,
        log: IngestionLog | None = None,
    ) -> None:
        self._figures_dir = figures_dir
        self._max_characters = max_characters
        self._log = log or NullIngestionLog()

    def route(
        self, elements: Sequence[Element], source: str
    ) -> list[DocumentUnit]:
        """Roteia os elementos de UM documento.

        A ordem da saída é: textos agrupados, depois tabelas, depois imagens. A
        ordem não tem significado para a busca (o índice é vetorial), e agrupar
        por categoria torna o log por estágio legível.

        `representation` sai VAZIA para tabela e imagem: preenchê-la é trabalho
        do estágio pago (ADR-002), e ele só roda para as unidades novas. Texto
        já sai completo, porque texto narrativo embeda bem e resumi-lo seria
        pagar por uma perda de informação.
        """
        tables = [e for e in elements if isinstance(e, Table)]
        images = [e for e in elements if isinstance(e, Image)]
        narrative = [
            e for e in elements if not isinstance(e, (Table, Image))
        ]

        units: list[DocumentUnit] = []
        units.extend(self._text_units(narrative, source))
        units.extend(self._table_units(tables, source))
        units.extend(self._image_units(images, source))

        deduplicated = self._deduplicate(units)
        self._report(deduplicated, source)
        return deduplicated

    # -- texto --------------------------------------------------------------

    def _text_units(
        self, narrative: Sequence[Element], source: str
    ) -> list[DocumentUnit]:
        """Agrupa o texto narrativo com `chunk_by_title`.

        `chunk_by_title` e não divisão por caracteres: ele quebra nos títulos,
        que é onde o documento já declarou que um assunto termina. Num relatório
        trimestral isso mantém "Desempenho financeiro" inteiro em vez de cortá-lo
        no caractere 1000 e produzir dois pedaços que, isolados, dizem menos que
        a soma deles.

        `max_characters` é TETO, não alvo: seções curtas viram unidades curtas.
        """
        if not narrative:
            return []

        chunks = chunk_by_title(
            list(narrative), max_characters=self._max_characters
        )
        units = []
        for chunk in chunks:
            text = (chunk.text or "").strip()
            if not text:
                continue
            units.append(
                DocumentUnit(
                    doc_id=compute_doc_id("texto", source, text),
                    kind="texto",
                    content=text,
                    # Multi-vector SELETIVO (ADR-002): a representação do texto
                    # é o próprio texto. Não há chamada paga neste ramo.
                    representation=text,
                    source=source,
                    page=page_of(chunk),
                )
            )
        return units

    # -- tabela -------------------------------------------------------------

    def _table_units(
        self, tables: Sequence[Element], source: str
    ) -> list[DocumentUnit]:
        """Uma unidade por tabela, carregando o HTML estruturado.

        `text_as_html` é o que o `infer_table_structure` produziu, e é o que
        precisa chegar ao LLM na consulta: linhas e colunas com a relação entre
        elas preservada. `element.text` da mesma tabela é a sopa de números que
        os projetos anteriores indexavam — usado aqui só como fallback, quando o
        Table Transformer não devolveu HTML (tabela detectada mas não
        estruturada), porque perder a tabela inteira seria pior.
        """
        units = []
        for table in tables:
            html = getattr(table.metadata, "text_as_html", None)
            content = (html or table.text or "").strip()
            if not content:
                continue
            units.append(
                DocumentUnit(
                    doc_id=compute_doc_id("tabela", source, content),
                    kind="tabela",
                    content=content,
                    # Vazia de propósito: o resumo é o estágio pago.
                    representation="",
                    source=source,
                    page=page_of(table),
                )
            )
        return units

    # -- imagem -------------------------------------------------------------

    def _image_units(
        self, images: Sequence[Element], source: str
    ) -> list[DocumentUnit]:
        """Uma unidade por imagem, apontando para o arquivo extraído.

        **O `doc_id` da imagem sai do hash dos BYTES do arquivo, não do texto do
        elemento.** O texto de um `Image` é o OCR do que estiver dentro dela,
        frequentemente vazio num gráfico: hashear isso faria todas as figuras sem
        texto colapsarem num único `doc_id` e o índice perderia todas menos uma.
        O byte da figura é o conteúdo real dela.

        O arquivo é copiado para um nome derivado do `doc_id` (ADR-003). O
        `unstructured` nomeia as figuras por página e posição, e esses nomes
        mudam quando o modelo de layout muda; o nome canônico não muda enquanto
        a imagem for a mesma. A cópia é idempotente: destino existente não é
        reescrito.
        """
        units = []
        for image in images:
            raw = getattr(image.metadata, "image_path", None)
            if not raw:
                # Imagem detectada mas não extraída para arquivo. Sem arquivo não
                # há o que descrever, e uma unidade sem conteúdo poluiria o índice.
                self._log.stage(
                    f"[roteamento] imagem na página {page_of(image)} de {source} "
                    "sem arquivo extraído; ignorada"
                )
                continue

            origin = Path(raw)
            if not origin.exists():
                self._log.stage(
                    f"[roteamento] figura ausente em disco ({origin}); ignorada"
                )
                continue

            doc_id = compute_doc_id("imagem", source, content_hash(origin))
            figure = self._canonical_figure(origin, doc_id)
            units.append(
                DocumentUnit(
                    doc_id=doc_id,
                    kind="imagem",
                    # Vazios de propósito: os DOIS são a descrição, e a descrição
                    # é o estágio pago (ADR-002 e ADR-006).
                    content="",
                    representation="",
                    source=source,
                    page=page_of(image),
                    figure_path=str(figure),
                )
            )
        return units

    def _canonical_figure(self, origin: Path, doc_id: str) -> Path:
        """Copia a figura para `<doc_id><extensão>`, se ainda não estiver lá."""
        self._figures_dir.mkdir(parents=True, exist_ok=True)
        target = self._figures_dir / f"{doc_id}{origin.suffix or '.jpg'}"
        if not target.exists():
            shutil.copyfile(origin, target)
        return target

    # -- fechamento ---------------------------------------------------------

    @staticmethod
    def _deduplicate(units: Sequence[DocumentUnit]) -> list[DocumentUnit]:
        """Colapsa unidades de conteúdo idêntico no mesmo `doc_id`.

        Rodapé repetido em vinte páginas produz vinte elementos e um único
        `doc_id`. **Não é erro** (EC-2 da US-003): é deduplicação de graça, e o
        índice fica melhor sem as dezenove cópias. Mantém a primeira ocorrência,
        que é a de menor página.
        """
        seen: set[str] = set()
        unique = []
        for unit in units:
            if unit.doc_id in seen:
                continue
            seen.add(unit.doc_id)
            unique.append(unit)
        return unique

    def _report(self, units: Sequence[DocumentUnit], source: str) -> None:
        """Contagem por categoria e por página, exigida pela AC-4 da US-001."""
        counts = count_elements(units)
        self._log.stage(
            f"[roteamento] {source}: {counts.textos} texto(s), "
            f"{counts.tabelas} tabela(s), {counts.imagens} imagem(ns)"
        )
        if counts.tabelas == 0:
            # Denúncia explícita do risco 1. Sem esta linha, "nenhuma tabela
            # detectada" é indistinguível de "o PDF não tem tabela".
            self._log.stage(
                "[roteamento] ATENÇÃO: nenhuma tabela detectada. Com "
                "strategy=fast isso é esperado; com hi_res é o risco 1 do FDD. "
                "Rode docs/operations/inspeciona-tabelas.py antes de gastar API."
            )
        by_page: dict[int, int] = {}
        for unit in units:
            by_page[unit.page] = by_page.get(unit.page, 0) + 1
        paginas = ", ".join(f"p.{p}: {n}" for p, n in sorted(by_page.items()))
        self._log.stage(f"[roteamento] unidades por página — {paginas}")
