"""Camada de apresentação: o único lugar que escreve para o usuário.

Uma política, um lugar: **stdout carrega o resultado, stderr carrega o
diagnóstico** (regra 2.3 da guideline). É o que permite
`python ask.py "..." > saida.txt` gravar só a resposta.

`console_reporter.py` (log estruturado por estágio da ingestão e da consulta) e
`json_presenter.py` (serialização do contrato 1.3.0, com campo opcional ausente
OMITIDO do JSON, nunca `null`) entram na task_04.
"""
