"""DTOs de entrada da camada HTTP.

Só a borda. Nada aqui decide comportamento: o papel é aceitar o corpo da
requisição no formato do contrato e recusar o que não for corpo válido.

A validação de DOMÍNIO (k fora da faixa, turno malformado) não está nos
modelos: ela vive nas camadas que sabem o que os valores significam, e chega ao
cliente como `Problem`, não como o erro de validação do framework. Um 422 do
Pydantic tem formato próprio e quebraria o contrato compartilhado.
"""

from pydantic import BaseModel, Field


class AskRequest(BaseModel):
    # SEM `min_length=1`, e a ausência é a decisão.
    #
    # Com a restrição no modelo, o Pydantic responde ANTES do error handler e o
    # corpo sai no formato dele (`{"detail": [{"type": "string_too_short", ...}]}`),
    # não no `Problem` que o contrato declara para o 422 de /ask. O frontend cai
    # no ramo degradado e mostra "HTTP 422" sem explicação.
    #
    # A validação de pergunta vazia vive na rota, levantando
    # InvalidParameterException, que o error handler traduz para `Problem`.
    question: str
    options: dict = Field(default_factory=dict)


class IngestRequest(BaseModel):
    options: dict = Field(default_factory=dict)
