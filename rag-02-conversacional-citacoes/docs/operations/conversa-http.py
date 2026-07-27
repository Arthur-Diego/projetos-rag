"""Simula exatamente o que o frontend faz: guarda a transcricao e a devolve."""
import json, urllib.request

BASE = "http://localhost:8080"
def post(caminho, corpo):
    r = urllib.request.Request(BASE + caminho, method="POST",
        data=json.dumps(corpo).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(r, timeout=120) as resp:
        return json.load(resp)

historico = []   # o CLIENTE e dono da transcricao
for pergunta in ["O que aconteceu quando Harry vestiu a capa de invisibilidade pela primeira vez?",
                 "E como eles a usaram para lidar com o dragao?",
                 "E o que aconteceu com o Norberto depois?"]:
    d = post("/ask", {"question": pergunta, "options": {"k": 4, "history": historico}})
    rq = d["rewritten_question"]
    print(f"\nturno {len(historico)+1}: {pergunta}")
    print(f"  reason={rq['reason']}  rewritten={rq['rewritten']}")
    if rq["rewritten"]:
        print(f"  buscado: {rq['used']}")
    print(f"  refused={d['refused']}  citations={len(d.get('citations', []))}  timings={d['timings']}")
    for c in d.get("citations", []):
        print(f"    [{c['label']}] {c['source']} p.{c['page']}")
    historico.append({"question": pergunta, "answer": d["text"]})

print(f"\ntranscricao final no cliente: {len(historico)} turnos")
