"""Criterios 5 e 6: custo da reescrita condicional e efeito da janela."""
import sys
sys.path.insert(0, "/home/arthu/code/projetos-rag/rag-02-conversacional-citacoes")
from rag import config
from rag.domain.models import Conversation, Turn, REASONS_WITHOUT_CALL
from composition import build_query_facade

p = config.load()
PERGUNTAS = [
  "O que aconteceu quando Harry vestiu a capa de invisibilidade pela primeira vez?",
  "E o que ela faz?",
  "E como eles a usaram para lidar com o dragao?",
  "Descreva o que Harry sentiu ao tocar em Quirrell no confronto final do livro",
]

def conversa(conditional, janela=6):
    f = build_query_facade(p, k=4, history_window=janela, conditional_rewrite=conditional)
    c, chamadas, linhas = Conversation(), 0, []
    for q in PERGUNTAS:
        a = f.ask(q, c)
        houve = a.rewrite.reason not in REASONS_WITHOUT_CALL
        chamadas += 1 + (1 if houve else 0)   # geracao + reescrita
        linhas.append((q[:34], a.rewrite.reason, "recusou" if a.refused else "respondeu"))
        c = Conversation(c.turns + (Turn(q, a.text),))
    return chamadas, linhas

print("=== CRITERIO 5: custo da reescrita condicional ===")
for cond in (False, True):
    n, linhas = conversa(cond)
    print(f"\nconditional_rewrite={cond} -> {n} chamadas de LLM em {len(PERGUNTAS)} turnos")
    for q, r, s in linhas:
        print(f"   {q:36} {r:26} {s}")

print("\n=== CRITERIO 6: janela de historico ===")
for janela in (0, 2, 20):
    f = build_query_facade(p, k=4, history_window=janela)
    c = Conversation((
      Turn("O que aconteceu quando Harry vestiu a capa pela primeira vez?", "Ele ficou invisivel [2]."),
      Turn("Quem estava com ele?", "Rony [2]."),
      Turn("O que Rony disse?", "Que era uma capa da invisibilidade [2]."),
    ))
    a = f.ask("E como eles a usaram para lidar com o dragao?", c)
    print(f"  janela={janela:2} -> reason={a.rewrite.reason:20} buscado: {a.rewrite.used[:70]}")
