"""Descritor deste backend, devolvido por GET /capabilities.

**É o mecanismo que torna o frontend genérico.** Ele desenha os controles a
partir daqui e nunca conhece parâmetro de projeto nenhum. Um projeto novo
acrescenta uma entrada em `parameters` e o controle aparece sozinho na
interface, sem alteração no cliente.

`applies_to` diz em que operação o parâmetro vale; ausente significa todas.
"""

PROJECT = "rag-01-fundamentos-pdf"

CAPABILITIES = {
    "project": PROJECT,
    "description": "RAG ingênuo sobre PDF, com procedência e recusa verificável",
    "features": ["ask", "ingest"],
    "parameters": {
        "k": {
            "type": "integer",
            "label": "Chunks recuperados",
            "help": "Quantos trechos enviar ao modelo. Baixo demais falta contexto; "
                    "alto demais dilui o sinal.",
            "default": 4,
            "minimum": 1,
            "maximum": 20,
            "applies_to": ["ask"],
        },
        "chunk_size": {
            "type": "integer",
            "label": "Tamanho do chunk",
            "help": "Caracteres por pedaço. Pergunta de síntese pede chunk grande; "
                    "pergunta de localização, pequeno.",
            "default": 1000,
            "minimum": 100,
            "maximum": 8000,
            "applies_to": ["ingest"],
        },
        "chunk_overlap": {
            "type": "integer",
            "label": "Sobreposição",
            "help": "Caracteres repetidos entre chunks vizinhos. Precisa ser menor "
                    "que o tamanho. Zera na virada de página, por desenho do loader.",
            "default": 150,
            "minimum": 0,
            "maximum": 2000,
            "applies_to": ["ingest"],
        },
    },
}
