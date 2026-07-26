"""Formato das requisições, conforme `docs/contracts/rag-api.yaml`.

Equivalem aos DTOs de entrada do Spring. Só descrevem forma: nenhuma regra de
negócio mora aqui.
"""

from pydantic import BaseModel, Field


class AskRequest(BaseModel):
    question: str = Field(min_length=1, description="Pergunta em linguagem natural")
    options: dict = Field(
        default_factory=dict,
        description=(
            "Parâmetros específicos do projeto, conforme /capabilities. "
            "Chaves desconhecidas são ignoradas, por contrato: é o que permite ao "
            "mesmo frontend falar com projetos de gerações diferentes."
        ),
    )


class IngestRequest(BaseModel):
    options: dict = Field(default_factory=dict)
