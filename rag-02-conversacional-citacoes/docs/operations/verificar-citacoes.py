"""Confere cada [n] abrindo a pagina citada no PDF e procurando o trecho."""
import sys, re
sys.path.insert(0, "/home/arthu/code/projetos-rag/rag-02-conversacional-citacoes")
from pypdf import PdfReader
from rag import config
from composition import build_query_facade

p = config.load()
facade = build_query_facade(p, k=4)
reader = PdfReader(str(p.pdf_dir / "j-k-rowling-1-harry-potter-e-a-pedra-filosofal.pdf"))

def norm(s): return re.sub(r"\s+", " ", s).strip().lower()

perguntas = [
 "O que aconteceu quando Harry vestiu a capa de invisibilidade pela primeira vez?",
 "Quem eh o guardiao das chaves de Hogwarts?",
 "O que Harry viu no espelho de Ojesed?",
 "Como se chama o cao de tres cabecas?",
 "O que acontece com quem bebe sangue de unicornio?",
]
total = ok = 0
for q in perguntas:
    a = facade.ask(q)
    if a.refused:
        print(f"[recusou] {q}")
        continue
    for c in a.citations:
        total += 1
        pagina = norm(reader.pages[c.page - 1].extract_text() or "")
        # confere as primeiras 12 palavras do excerpt na pagina citada
        agulha = " ".join(norm(c.excerpt).split()[:12])
        achou = agulha in pagina
        ok += achou
        print(f"{'OK ' if achou else 'ERRO'} [{c.label}] p.{c.page} :: {agulha[:70]}...")
print(f"\n{ok}/{total} citacoes conferem com a pagina citada")
