"""Identidade determinística das unidades indexáveis (ADR-003).

Camada folha, como `models.py`: não importa nada do projeto e nada de fora.
Uma função pura, e ela é a peça que torna a ingestão idempotente.

**Por que não `uuid.uuid4()`, que é o que o guia usa.** Aleatório por
definição: cada reingestão geraria ids novos, duplicaria o índice inteiro em
silêncio e repagaria resumo, descrição e embedding de conteúdo que não mudou.
O guia ingere uma vez e joga fora; este projeto declara a iteração sobre a
ingestão como parte do trabalho.

**Por que hash de conteúdo e não posição no documento.** Id sequencial é
estável só enquanto o documento E o particionador não mudam: uma tabela a mais
detectada pelo modelo de layout desloca todos os ids seguintes e desalinha o
índice inteiro sem aviso. O hash só muda onde o conteúdo mudou.
"""

import hashlib
import json

from .models import Kind


def compute_doc_id(kind: Kind, source: str, content: str) -> str:
    """Id determinístico de uma unidade: hash de conteúdo + origem + tipo.

    As três parcelas do ADR-003, e cada uma responde por um caso:

    - `content` é o que muda quando o documento muda. É o eixo da economia:
      conteúdo idêntico não repaga.
    - `source` desambigua o mesmo texto vindo de dois PDFs diferentes. Sem ele,
      um rodapé comum a dois relatórios colapsaria num id só e o segundo
      relatório perderia a procedência.
    - `kind` desambigua o improvável mas possível: um texto cujo conteúdo
      coincide com o HTML de uma tabela indexaria os dois no mesmo lugar.

    **A serialização precisa ser estável, e é por isso que passa por JSON.**
    Concatenar com separador exigiria escolher um caractere que nunca ocorre nos
    campos, e "nunca ocorre" é falso em corpus real: um separador que aparece no
    conteúdo faz duas unidades diferentes produzirem a mesma cadeia. O
    `json.dumps` com chaves ordenadas e separadores fixos escapa por construção
    e não depende da ordem de inserção do dicionário.

    A saída é hexadecimal (64 caracteres de `[0-9a-f]`), e isso não é detalhe
    estético: os nomes de arquivo do docstore e das figuras DERIVAM deste valor.
    Um id que carregasse `/` ou `..` viraria path traversal com conteúdo de PDF
    como vetor. Hexadecimal neutraliza a classe inteira por construção — é a
    consequência de segurança registrada no ADR-003.
    """
    payload = json.dumps(
        {"kind": kind, "source": source, "content": content},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
