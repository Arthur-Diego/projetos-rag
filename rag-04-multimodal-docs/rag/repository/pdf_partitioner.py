"""Partição bruta do PDF e o cache dela (ADR-005).

Camada de repositório: aqui moram as DUAS fronteiras externas do estágio local
— a biblioteca `unstructured` (que por sua vez chama poppler, tesseract e os
modelos de layout) e o sistema de arquivos que guarda o cache.

**O que atravessa esta fronteira é `Element` do `unstructured`, e isso é
deliberado.** O cache precisa persistir e restaurar exatamente o que o `hi_res`
produziu, com `text_as_html` e `image_path` intactos: converter para tipo de
domínio antes de cachear jogaria fora justamente a informação que a partição
custou minutos para obter, e o roteamento por categoria (que é quem traduz para
`DocumentUnit`) precisa da categoria original do elemento. A tradução acontece
uma vez, no `ElementRoutingService`; daí para cima é domínio puro.

Os dois `Protocol` daqui existem para o teste T3.5: provar que um cache válido
NÃO invoca o particionador exige poder contar as invocações, e contar exige
poder substituir.
"""

import hashlib
from pathlib import Path
from typing import Protocol

from unstructured.documents.elements import Element
from unstructured.partition.pdf import partition_pdf
from unstructured.staging.base import elements_from_json, elements_to_json

from ..config import PartitionStrategy
from ..exceptions import PartitionFailedException


def content_hash(path: Path) -> str:
    """Hash do CONTEÚDO do arquivo, não do nome.

    A chave do cache é o conteúdo porque um PDF trocado no lugar, com o mesmo
    nome, serviria elementos velhos para sempre — a consequência negativa que o
    ADR-005 registra e mitiga exatamente assim. O efeito colateral é bem-vindo:
    o mesmo PDF renomeado acerta o cache (EC-3 da US-002).

    Lê em blocos porque um relatório com figuras passa de 10 MB e não há motivo
    para carregar o arquivo inteiro na memória só para hashear.
    """
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


class Partitioner(Protocol):
    """Contrato do estágio caro: PDF em disco vira lista de elementos."""

    def partition(self, path: Path) -> list[Element]:
        ...


class PartitionCache(Protocol):
    """Contrato do cache da partição bruta.

    `load` devolve `None` para ausência E para cache ilegível. As duas coisas
    levam ao mesmo lugar — refazer a partição — e distingui-las no tipo de
    retorno obrigaria todo chamador a tratar um caso que ele resolve igual. O
    que NÃO se perde é o aviso: o descarte é anunciado por `last_discard`, e o
    serviço o repassa ao log (EC-1 da US-002).
    """

    def load(self, key: str) -> list[Element] | None:
        ...

    def save(self, key: str, elements: list[Element]) -> None:
        ...

    @property
    def last_discard(self) -> str | None:
        """Motivo do último descarte de cache corrompido, ou None."""
        ...


class UnstructuredPartitioner:
    """Adaptador do `unstructured` sobre um PDF.

    `hi_res` é o objeto de estudo do projeto: modelo de layout, Table
    Transformer e OCR, minutos de CPU por PDF, e o único caminho que produz
    tabela em HTML. `fast` é a contingência declarada do risco 2 do FDD — lê só
    a camada de texto, sobe em segundos e NÃO DETECTA TABELA NENHUMA.
    """

    def __init__(
        self,
        strategy: PartitionStrategy,
        figures_dir: Path,
    ) -> None:
        self._strategy = strategy
        self._figures_dir = figures_dir

    def partition(self, path: Path) -> list[Element]:
        """Roda a partição e devolve os elementos brutos.

        `infer_table_structure=True` é o que liga o Table Transformer e
        preenche `metadata.text_as_html`. Sem ele a tabela desce como texto
        corrido e o projeto inteiro perde o objeto — seria o `PyPDFLoader` dos
        projetos 1 a 3 com outro nome.

        A extração de imagens sai para `data/figures/` em ARQUIVO, e não em
        base64 dentro do elemento (`extract_image_block_to_payload=False`):
        o cache da partição é JSON e serializar megabytes de base64 dentro dele
        tornaria caro justamente o estágio que existe para ser barato.

        Raises:
            PartitionFailedException: se a biblioteca falhar (quase sempre
                dependência nativa ausente — poppler ou tesseract) ou se a
                partição não devolver elemento nenhum.
        """
        self._figures_dir.mkdir(parents=True, exist_ok=True)
        try:
            elements = partition_pdf(
                filename=str(path),
                strategy=self._strategy,
                infer_table_structure=True,
                extract_image_block_types=["Image"],
                extract_image_block_to_payload=False,
                extract_image_block_output_dir=str(self._figures_dir),
            )
        except Exception as e:
            raise PartitionFailedException(
                f"a partição de {path.name} falhou ({type(e).__name__}: {e}).\n"
                "       com strategy=hi_res isto quase sempre é dependência nativa "
                "ausente:\n"
                "       sudo apt install -y poppler-utils tesseract-ocr "
                "tesseract-ocr-por\n"
                "       contingência: PARTITION_STRATEGY=fast no .env (sem tabelas)."
            ) from e

        if not elements:
            raise PartitionFailedException(
                f"{path.name} não produziu elemento nenhum.\n"
                "       PDF sem camada de texto e sem OCR disponível, ou arquivo "
                "corrompido."
            )
        return list(elements)


class FilePartitionCache:
    """Cache em `data/partition/`, um JSON por (conteúdo do PDF, estratégia).

    A estratégia entra na chave porque `fast` e `hi_res` produzem partições
    DIFERENTES do mesmo arquivo. Sem ela, destravar o pipeline com `fast` durante
    o setup gravaria um cache sem tabela nenhuma que seria servido depois, com o
    `hi_res` já funcionando, e o sintoma seria `tabelas: 0` sem causa aparente —
    o risco 1 disfarçado de risco 2.
    """

    def __init__(self, directory: Path, strategy: PartitionStrategy) -> None:
        self._directory = directory
        self._strategy = strategy
        self._last_discard: str | None = None

    @property
    def last_discard(self) -> str | None:
        return self._last_discard

    def _path(self, key: str) -> Path:
        # O nome deriva do hash: hexadecimal, sem separador de caminho possível.
        return self._directory / f"{key}-{self._strategy}.json"

    def load(self, key: str) -> list[Element] | None:
        """Lê o cache, ou devolve None se ele não existe ou não presta.

        **Cache corrompido é descartado, nunca propagado.** Um JSON truncado por
        interrupção no meio da gravação levantaria no meio da ingestão, minutos
        depois, com mensagem da biblioteca. Aqui ele vira uma repartição e uma
        linha de log — o custo é o do `hi_res`, que é exatamente o que se paga
        quando não há cache. É a EC-1 da US-002.
        """
        self._last_discard = None
        path = self._path(key)
        if not path.exists():
            return None
        try:
            elements = elements_from_json(filename=str(path))
        except Exception as e:
            self._last_discard = f"{path.name} ilegível ({type(e).__name__})"
            return None
        if not elements:
            self._last_discard = f"{path.name} vazio"
            return None
        return list(elements)

    def save(self, key: str, elements: list[Element]) -> None:
        """Grava o cache de forma atômica.

        Escrita em arquivo temporário e `replace` no final: `replace` é atômico
        no mesmo sistema de arquivos, então uma interrupção deixa o cache
        ANTIGO (ou nenhum), nunca um arquivo meio escrito. Cache corrompido já é
        tratado na leitura, mas não produzi-lo é melhor que sobreviver a ele.
        """
        self._directory.mkdir(parents=True, exist_ok=True)
        path = self._path(key)
        temporary = path.with_suffix(".json.tmp")
        temporary.write_text(elements_to_json(elements, indent=0), encoding="utf-8")
        temporary.replace(path)
