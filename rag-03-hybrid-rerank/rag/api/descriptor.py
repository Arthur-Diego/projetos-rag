"""Conteúdo de GET /capabilities.

**O ponto central do contrato compartilhado.** É este descritor que permite ao
frontend ser genérico: ele monta os controles a partir daqui e não precisa
saber o que cada campo significa.

`history` em `features` é o gatilho da interface de conversa. Declará-lo é o
que faz o frontend guardar a transcrição e devolvê-la em `options.history`; sem
ele, o mesmo frontend mostra a tela de pergunta única que o `rag-01` usa.

Os defaults vêm de `config.py`, não são reescritos aqui. Se o descritor
prometesse um default e a CLI usasse outro, o frontend e o terminal
divergiriam, e a diferença apareceria como "a resposta muda dependendo de onde
eu pergunto".
"""

from ..config import (
    DEFAULT_CANDIDATES,
    DEFAULT_CHUNK_OVERLAP,
    DEFAULT_CHUNK_SIZE,
    DEFAULT_CONDITIONAL_REWRITE,
    DEFAULT_HISTORY_WINDOW,
    DEFAULT_HYBRID,
    DEFAULT_K,
    DEFAULT_RERANK,
    DEFAULT_RRF_K,
    MAX_CANDIDATES,
    MAX_CHUNK_OVERLAP,
    MAX_CHUNK_SIZE,
    MAX_HISTORY_WINDOW,
    MAX_K,
    MAX_RRF_K,
    MIN_CHUNK_SIZE,
)

PROJECT = "rag-03-hybrid-rerank"

CAPABILITIES = {
    "project": PROJECT,
    "description": (
        "RAG com busca híbrida: recupera por significado e por palavra exata, "
        "funde os dois rankings por posição e reordena com cross-encoder"
    ),
    "features": ["ask", "ingest", "history"],
    "parameters": {
        "k": {
            "type": "integer",
            "label": "Chunks recuperados",
            "help": (
                "Quantos trechos enviar ao modelo. Baixo demais falta contexto; "
                "alto demais dilui e aumenta a chance de citação confusa."
            ),
            "default": DEFAULT_K,
            "minimum": 1,
            "maximum": MAX_K,
            "applies_to": ["ask"],
        },
        "hibrida": {
            "type": "boolean",
            "label": "Busca híbrida",
            "help": (
                "Acrescenta a busca por palavra exata (BM25) ao lado da busca "
                "por significado. É o que faz código, sigla e nome próprio raro "
                "pararem de sumir: um termo literal não tem significado para "
                "embedar."
            ),
            "default": DEFAULT_HYBRID,
            "applies_to": ["ask"],
        },
        "rerank": {
            "type": "boolean",
            "label": "Reordenar candidatos",
            "help": (
                "Relê a pergunta junto de cada candidato e reordena. Melhora "
                "bastante a precisão e custa segundos por turno, porque roda "
                "local na CPU."
            ),
            "default": DEFAULT_RERANK,
            "applies_to": ["ask"],
        },
        "candidates": {
            "type": "integer",
            "label": "Candidatos por caminho",
            "help": (
                "Quantos trechos cada busca traz antes da fusão. Mais candidatos "
                "dão mais material para reordenar, e o custo do reordenador "
                "cresce junto."
            ),
            "default": DEFAULT_CANDIDATES,
            "minimum": 1,
            "maximum": MAX_CANDIDATES,
            "applies_to": ["ask"],
        },
        "rrf_k": {
            "type": "integer",
            "label": "Amortecimento da fusão",
            "help": (
                "Valor baixo dá muito peso a quem ficou em primeiro; alto achata "
                "as diferenças entre posições. 60 é o padrão da literatura."
            ),
            "default": DEFAULT_RRF_K,
            "minimum": 1,
            "maximum": MAX_RRF_K,
            "applies_to": ["ask"],
        },
        "history_window": {
            "type": "integer",
            "label": "Janela de histórico",
            "help": (
                "Quantos turnos anteriores considerar. Conversa longa estoura o "
                "contexto e piora a reescrita. Zero desliga o histórico."
            ),
            "default": DEFAULT_HISTORY_WINDOW,
            "minimum": 0,
            "maximum": MAX_HISTORY_WINDOW,
            "applies_to": ["ask"],
        },
        "conditional_rewrite": {
            "type": "boolean",
            "label": "Reescrita condicional",
            "help": (
                "Pula a reescrita quando a pergunta já parece autossuficiente. "
                "Economiza uma chamada de LLM por turno, ao risco de não "
                "reescrever algo que precisava."
            ),
            "default": DEFAULT_CONDITIONAL_REWRITE,
            "applies_to": ["ask"],
        },
        "chunk_size": {
            "type": "integer",
            "label": "Tamanho do chunk",
            "help": "Caracteres por pedaço. Afeta a indexação, exige reindexar.",
            "default": DEFAULT_CHUNK_SIZE,
            "minimum": MIN_CHUNK_SIZE,
            "maximum": MAX_CHUNK_SIZE,
            "applies_to": ["ingest"],
        },
        "chunk_overlap": {
            "type": "integer",
            "label": "Sobreposição",
            "help": (
                "Caracteres repetidos entre pedaços vizinhos. Evita cortar uma "
                "frase no meio."
            ),
            "default": DEFAULT_CHUNK_OVERLAP,
            "minimum": 0,
            "maximum": MAX_CHUNK_OVERLAP,
            "applies_to": ["ingest"],
        },
    },
}
