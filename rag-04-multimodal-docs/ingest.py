"""Entrypoint de ingestão: partição -> enriquecimento -> indexação dupla.

Faz duas coisas, e só duas (regra 2.6 da guideline): adapta o mundo externo
(argumentos e configuração) e monta o grafo pelo `composition.py`, delegando
tudo à facade. Nenhuma lógica de pipeline aqui.

Uso:

    .venv/bin/python ingest.py
    .venv/bin/python ingest.py --sem-descrever-imagens

A primeira execução leva MINUTOS: o `hi_res` roda modelo de layout, Table
Transformer e OCR por página. A segunda acerta o cache da partição (ADR-005) e,
se o corpus não mudou, não gasta uma única chamada paga (ADR-003).
"""

import argparse
import sys

from composition import build_chroma_client, build_ingestion_facade
from rag import config
from rag.exceptions import RagException
from rag.presenter.console_reporter import ConsoleReporter


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Ingere os PDFs de pdfs/ nos dois armazéns do rag-04."
    )
    parser.add_argument(
        "--sem-descrever-imagens",
        action="store_true",
        help=(
            "não chama o modelo de visão. As imagens continuam sendo extraídas "
            "e contadas no relatório, mas não são descritas nem indexadas nesta "
            "execução: ficam pendentes para uma ingestão futura."
        ),
    )
    return parser.parse_args()


def main() -> int:
    """Devolve código de saída; quem encerra o processo é o bloco `__main__`.

    Só `RagException` é tratada: é a hierarquia dos erros PREVISTOS, e cada uma
    delas já carrega a receita na mensagem. Qualquer outra exceção sobe com o
    traceback inteiro, porque aí o defeito é deste código e o traceback é a
    informação útil.
    """
    args = parse_args()
    reporter = ConsoleReporter()

    try:
        properties = config.load()
        if properties.partition_strategy == "fast":
            # Contingência do risco 2 do FDD, DECLARADA no log. Silenciar isto
            # faria o `tabelas: 0` do relatório parecer falha de detecção
            # (risco 1) quando a detecção nem chegou a ser ligada.
            reporter.diagnostic(
                "ATENÇÃO: PARTITION_STRATEGY=fast — contingência ligada. "
                "Nenhuma tabela será detectada. Não use para medir."
            )

        facade = build_ingestion_facade(
            properties, build_chroma_client(properties), reporter
        )
        reporter.files(facade.files())
        reporter.ingestion(
            facade.ingest(descrever_imagens=not args.sem_descrever_imagens)
        )
    except RagException as e:
        reporter.failure(str(e))
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
