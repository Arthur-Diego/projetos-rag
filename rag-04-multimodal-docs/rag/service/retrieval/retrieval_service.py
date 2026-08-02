"""Política de recuperação: buscar representações, devolver ORIGINAIS.

Separado dos repositórios de propósito: eles sabem guardar e consultar, este
serviço sabe QUANTO trazer e o que fazer com o que voltou.

**É aqui que o padrão multi-vector se fecha.** O Chroma devolve `doc_id`s das
representações que casaram com a pergunta (o resumo da tabela, a descrição da
imagem); o docstore devolve os originais íntegros. O que sobe deste serviço já é
`SearchHit` com o original resolvido — nenhuma camada acima tem como, por
descuido, mandar o resumo ao LLM, porque o resumo não chega até lá.

**Devolve `RetrievalResult` e não `list[SearchHit]`** (precedente do ADR-007 do
rag-03): com dois estágios por dentro, cronometrar de fora produz um agregado
que não responde onde o tempo foi. E a métrica sai pelo RETORNO, nunca por
atributo do serviço, que seria estado mutável compartilhado entre requisições.

Não há limiar de distância, por herança dos projetos 2 e 3: o armazém devolve os
mais próximos SEMPRE, mesmo quando todos são ruins. Quem recusa é o prompt, e só
depois da geração.
"""

from time import perf_counter

from ...config import DEFAULT_K, MAX_K, MIN_K
from ...domain.models import DocumentUnit, IndexMatch, RetrievalResult, SearchHit
from ...exceptions import EmptyIndexException, InvalidParameterException
from ...repository.docstore_repository import DocstoreRepository
from ...repository.vector_repository import VectorRepository
from ..ingestion_log import IngestionLog, NullIngestionLog


class RetrievalService:
    """Busca densa nas representações e resolução dos originais por `doc_id`."""

    def __init__(
        self,
        vectors: VectorRepository,
        docstore: DocstoreRepository,
        k: int = DEFAULT_K,
        log: IngestionLog | None = None,
    ) -> None:
        """Valida a faixa de `k` na CONSTRUÇÃO, não no uso.

        Um serviço que existe é válido (molde do rag-03). Declarar o limite
        1 a 20 em `/capabilities` e não impô-lo transformaria o descritor em
        sugestão, e o contrato diz que ele descreve o backend, não uma intenção.

        Raises:
            InvalidParameterException: `k` fora de 1 a 20. Vira 422 na borda.
        """
        if k < MIN_K:
            raise InvalidParameterException(
                f"k deve ser >= {MIN_K} (recebido: {k})."
            )
        if k > MAX_K:
            raise InvalidParameterException(
                f"k deve ser <= {MAX_K} (recebido: {k}). "
                "Com kind=tabela o que entra no prompt é o HTML ÍNTEGRO, não o "
                "resumo: k alto estoura contexto e custo."
            )
        self._vectors = vectors
        self._docstore = docstore
        self._log = log or NullIngestionLog()
        self.k = k

    def indexed_count(self) -> int:
        return self._vectors.count()

    def require_index(self, collection: str) -> int:
        """Falha cedo se não há o que buscar.

        Chamado ANTES de qualquer chamada paga — antes até da embedagem da
        pergunta, que já custa. Índice vazio é 409, não uma resposta vazia que
        custou duas chamadas de API (precedente do rag-03).

        Raises:
            EmptyIndexException: se a coleção não existe ou está sem
                representações.
        """
        total = self.indexed_count()
        if not total:
            raise EmptyIndexException(
                f"a coleção '{collection}' está vazia ou não existe.\n"
                "       rode primeiro: .venv/bin/python ingest.py"
            )
        return total

    def retrieve(self, question: str) -> RetrievalResult:
        """Busca as representações e devolve os hits já com os originais."""
        marker = perf_counter()
        matches = self._vectors.search(question, k=self.k)
        dense_s = perf_counter() - marker

        marker = perf_counter()
        originals = self._docstore.get([match.doc_id for match in matches])
        docstore_s = perf_counter() - marker

        hits: list[SearchHit] = []
        orphans: list[str] = []
        for match in matches:
            unit = originals.get(match.doc_id)
            if unit is None:
                orphans.append(match.doc_id)
                continue
            hits.append(self._to_hit(match, unit))

        if orphans:
            # Warning e não exceção: um único original perdido não pode derrubar
            # a consulta inteira (hipótese confirmada na entrevista, seção 4 do
            # FDD). Quem denuncia a dessincronia como estado é o `GET /health`;
            # o papel desta linha é impedir que ela passe despercebida na
            # consulta em que apareceu.
            self._log.stage(
                f"[recuperação] ATENÇÃO: {len(orphans)} hit(s) órfão(s) "
                "descartado(s) — doc_id no índice sem original no docstore: "
                + ", ".join(orphans[:5])
                + (" e outros" if len(orphans) > 5 else "")
                + ". Os dois armazéns estão dessincronizados; confira GET /health."
            )

        self._log.stage(
            f"[recuperação] {len(hits)} trecho(s) de {len(matches)} match(es) "
            f"— busca {dense_s:.2f}s, docstore {docstore_s:.2f}s"
        )
        return RetrievalResult(
            hits=tuple(hits),
            dense_s=dense_s,
            docstore_s=docstore_s,
            discarded=len(orphans),
        )

    @staticmethod
    def _to_hit(match: IndexMatch, unit: DocumentUnit) -> SearchHit:
        """Junta as duas metades num hit do contrato 1.3.0.

        **`content_html` só existe com `kind=tabela`** (invariante da seção 6 do
        FDD), e `excerpt` carrega SEMPRE a representação — o trecho, o resumo ou
        a descrição, conforme o tipo. Para texto e imagem, original e
        representação são o mesmo conteúdo (o multi-vector é seletivo, ADR-002),
        e é por isso que só a tabela tem um segundo campo.

        `score` e não `distance`: o contrato declara os dois com sentidos
        OPOSTOS (menor é melhor na distância, maior é melhor na pontuação), e a
        conversão acontece AQUI, uma vez só. Com embeddings unitários da OpenAI,
        `1 - distância do cosseno` é a similaridade, que é o que "maior é
        melhor" significa.
        """
        return SearchHit(
            source=unit.source,
            page=unit.page,
            kind=unit.kind,
            excerpt=unit.representation,
            score=1.0 - match.distance,
            # Também exige `content_is_html`: tabela detectada sem estrutura
            # tem texto plano no `content`, e o contrato define `content_html`
            # como o HTML original — sem ele, o hit degrada para `excerpt`.
            content_html=(
                unit.content
                if unit.kind == "tabela" and unit.content_is_html
                else None
            ),
        )
