"""A suíte é um pacote.

Existe por causa dos dublês compartilhados (`tests/fakes.py`): sem este arquivo,
o mypy enxerga o mesmo arquivo sob dois nomes de módulo (`fakes` e
`tests.fakes`) e recusa a verificação inteira antes de checar qualquer coisa.
"""
