"""DTOs de entrada da camada HTTP.

Só a borda. Nada aqui decide comportamento: o papel é aceitar o corpo da
requisição no formato do contrato e recusar o que não for corpo válido.

A validação de DOMÍNIO (tipo errado em `options`) não está nos modelos: ela vive
nas camadas que sabem o que os valores significam e chega ao cliente como
`Problem`, não como o erro de validação do Pydantic. Um 422 do Pydantic tem
formato próprio e quebraria o contrato compartilhado — o frontend cairia no ramo
degradado e mostraria "HTTP 422" sem explicação.
"""

from pydantic import BaseModel, Field


class IngestRequest(BaseModel):
    options: dict = Field(default_factory=dict)


class AskRequest(BaseModel):
    """Corpo do `POST /ask`.

    `question` NÃO declara `min_length` aqui, apesar de o contrato dizer
    `minLength: 1`. A verificação de pergunta vazia é feita na rota, para que o
    422 saia no formato `Problem`: um erro de validação do Pydantic tem formato
    próprio, e o frontend cairia no ramo degradado mostrando "HTTP 422" sem
    explicação. O contrato continua honrado — o que muda é quem escreve a
    resposta.
    """

    question: str
    options: dict = Field(default_factory=dict)
