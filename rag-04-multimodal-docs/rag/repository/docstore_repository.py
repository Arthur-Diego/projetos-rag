"""Armazém dos ORIGINAIS: a fonte de verdade do projeto (ADR-001).

Camada de repositório. O mundo externo aqui é o `BaseStore` do LangChain, hoje
um `LocalFileStore` em `data/docstore/`.

**Regra dura, no molde do `vector_repository.py` do rag-03: nada do vocabulário
do armazém atravessa este arquivo.** `mget`, `mset`, `bytes`, o formato JSON de
serialização e o nome do arquivo em disco ficam aqui dentro. O que sobe é
`DocumentUnit`, domínio puro.

Por que este é o armazém que importa: perder o Chroma custa minutos de
re-embedding sobre dados que continuam existindo; perder isto custa a ingestão
inteira, incluindo os minutos de `hi_res` e todas as chamadas pagas. É a razão
de o ADR-001 declarar o docstore como fonte de verdade e não como cache.
"""

import json
from typing import Any, Protocol

from langchain_core.stores import BaseStore

from ..domain.models import DocumentUnit, Kind


class DocstoreRepository(Protocol):
    """Contrato do armazém dos originais."""

    def known(self, doc_ids: list[str]) -> set[str]:
        """Quais destes ids JÁ existem.

        Em lote, e não um `contains` por unidade, porque é esta chamada que
        decide quem chega a pagar (ADR-003): perguntar item a item por um corpus
        de centenas de unidades transformaria a verificação de idempotência num
        gargalo de I/O maior que a economia que ela produz.
        """
        ...

    def put(self, units: list[DocumentUnit]) -> None:
        """Grava os originais. Mesma chave sobrescreve com o mesmo conteúdo."""
        ...

    def get(self, doc_ids: list[str]) -> dict[str, DocumentUnit]:
        """Resolve ids em originais. Id sem original simplesmente não aparece.

        A ausência não é erro aqui: quem decide o que fazer com um `doc_id`
        órfão é a consulta (descarta o hit com warning) e o `/health` (denuncia
        a dessincronia). Levantar neste nível faria um único original perdido
        derrubar a consulta inteira.
        """
        ...

    def count(self) -> int:
        """Quantos originais existem. Alimenta a sincronia do `/health`."""
        ...

    def reset(self) -> int:
        """Apaga todos os originais e devolve quantos havia.

        Só o script de reset chama. A ingestão nunca apaga: ela reconcilia
        (ADR-003). Idempotente — armazém já vazio devolve zero, não erro.
        """
        ...


def _encode(unit: DocumentUnit) -> bytes:
    """Serializa a unidade para o armazém.

    JSON e não `pickle`: o docstore é a fonte de verdade e vai sobreviver a
    versões deste código. `pickle` amarraria a leitura à definição exata da
    classe no momento da gravação, e um `NamedTuple` com campo novo tornaria
    ilegível uma ingestão que custou horas.
    """
    return json.dumps(unit._asdict(), ensure_ascii=False).encode("utf-8")


def _decode(raw: bytes) -> DocumentUnit | None:
    """Reconstrói a unidade, ou None se o registro não presta.

    Registro ilegível é tratado como ausente, pelo mesmo motivo do cache de
    partição: o consumidor já sabe lidar com ausência (descarta o hit, denuncia
    no `/health`), e um `JSONDecodeError` subindo daqui derrubaria a consulta
    inteira por causa de um arquivo.
    """
    try:
        body: dict[str, Any] = json.loads(raw.decode("utf-8"))
        kind: Kind = body["kind"]
        return DocumentUnit(
            doc_id=body["doc_id"],
            kind=kind,
            content=body["content"],
            representation=body["representation"],
            source=body["source"],
            page=int(body["page"]),
            figure_path=body.get("figure_path"),
            # `True` para registros gravados antes do campo existir: o
            # comportamento deles era publicar `content_html`, e a releitura
            # não pode mudar o que uma ingestão já paga produziu.
            content_is_html=bool(body.get("content_is_html", True)),
        )
    except Exception:
        return None


class FileDocstoreRepository:
    """Adaptador sobre um `BaseStore` de bytes (hoje `LocalFileStore`).

    Depende de `BaseStore`, e não de `LocalFileStore`, porque é essa a troca que
    o ADR-001 protege: object storage em produção é uma linha no
    `composition.py` e nada aqui muda.

    A chave é o `doc_id`, que é hexadecimal por construção (ADR-003). É o que
    torna o nome do arquivo em disco seguro sem sanitização nenhuma: nenhum
    trecho de PDF vira caminho.
    """

    def __init__(self, store: BaseStore[str, bytes]) -> None:
        self._store = store

    def known(self, doc_ids: list[str]) -> set[str]:
        if not doc_ids:
            return set()
        # Uma ida ao armazém para o lote inteiro. Ver o Protocol.
        found = self._store.mget(doc_ids)
        return {
            doc_id
            for doc_id, raw in zip(doc_ids, found, strict=True)
            if raw is not None
        }

    def put(self, units: list[DocumentUnit]) -> None:
        if not units:
            return
        self._store.mset([(unit.doc_id, _encode(unit)) for unit in units])

    def get(self, doc_ids: list[str]) -> dict[str, DocumentUnit]:
        if not doc_ids:
            return {}
        resolved: dict[str, DocumentUnit] = {}
        for doc_id, raw in zip(doc_ids, self._store.mget(doc_ids), strict=True):
            if raw is None:
                continue
            unit = _decode(raw)
            if unit is not None:
                resolved[doc_id] = unit
        return resolved

    def count(self) -> int:
        return sum(1 for _ in self._store.yield_keys())

    def reset(self) -> int:
        """Apaga tudo pelo `mdelete` do próprio armazém.

        Pelo `BaseStore`, e não apagando o diretório em disco: o tipo concreto é
        uma escolha do `composition.py` (ADR-001), e um `rmtree` aqui dentro
        amarraria o reset ao `LocalFileStore` — trocar por object storage
        deixaria de zerar coisa nenhuma, em silêncio.
        """
        keys = list(self._store.yield_keys())
        if keys:
            self._store.mdelete(keys)
        return len(keys)
