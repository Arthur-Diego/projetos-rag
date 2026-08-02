"""Conteúdo de `GET /capabilities`.

**O ponto central do contrato compartilhado.** É este descritor que permite ao
frontend genérico ser genérico: ele monta os controles a partir daqui e não
precisa saber o que cada campo significa.

Duas ausências são decisões, não esquecimento:

- **`history` fora de `features`** (adr-002 da sessão). É ele que faz o frontend
  guardar a transcrição e mostrar a aba de conversa; sem ele, o mesmo frontend
  mostra a tela de pergunta única. O rag-04 é pergunta única.
- **`stream` fora de `features`** (seção 3 do FDD). Não há resposta em fluxo.

`sources` está presente: a lista de fontes com selo de `kind` e a tabela
renderizada é metade do que este projeto entrega na interface.

Os defaults vêm de `config.py` e não são reescritos aqui. Um descritor que
prometesse um default e a CLI usasse outro faria a resposta mudar dependendo de
onde se pergunta.
"""

from ..config import DEFAULT_DESCREVER_IMAGENS, DEFAULT_K, MAX_K, MIN_K

PROJECT = "rag-04-multimodal-docs"

CAPABILITIES = {
    "project": PROJECT,
    "description": (
        "RAG multimodal sobre PDF complexo: indexa o resumo da tabela e a "
        "descrição da imagem, e entrega ao modelo o original íntegro"
    ),
    "features": ["ask", "ingest", "sources"],
    "parameters": {
        "k": {
            "type": "integer",
            "label": "Trechos recuperados",
            "help": (
                "Quantos trechos enviar ao modelo. Neste projeto uma tabela "
                "entra no prompt em HTML ÍNTEGRO, não como resumo: valor alto "
                "estoura o contexto e o custo mais rápido que nos anteriores."
            ),
            "default": DEFAULT_K,
            "minimum": MIN_K,
            "maximum": MAX_K,
            "applies_to": ["ask"],
        },
        "descrever_imagens": {
            "type": "boolean",
            "label": "Descrever imagens",
            "help": (
                "Chama o modelo de visão uma vez por figura extraída. "
                "Desligado, as imagens continuam sendo extraídas e contadas, "
                "mas não são descritas nem indexadas nesta execução."
            ),
            "default": DEFAULT_DESCREVER_IMAGENS,
            "applies_to": ["ingest"],
        },
    },
}
