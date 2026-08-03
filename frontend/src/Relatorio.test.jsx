import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import Relatorio from "./Relatorio";

/** T5.4 — as contagens `elements` aparecem só quando o backend as emite. */

let container;
let root;

beforeEach(() => {
  globalThis.IS_REACT_ACT_ENVIRONMENT = true;
  container = document.createElement("div");
  document.body.appendChild(container);
  root = createRoot(container);
});

afterEach(() => {
  act(() => root.unmount());
  container.remove();
});

function renderiza(dados) {
  act(() => root.render(<Relatorio dados={dados} />));
  return container;
}

function rotulos(dom) {
  return [...dom.querySelectorAll("dt")].map((dt) => dt.textContent);
}

function valorDe(dom, rotulo) {
  const dt = [...dom.querySelectorAll("dt")].find((n) => n.textContent === rotulo);
  return dt?.nextElementSibling.textContent;
}

const BASE = {
  pages: 30,
  chunks: 50,
  discarded_pages: 0,
  previous_chunks: 0,
  chunk_size: 1000,
  chunk_overlap: 0,
  seconds: 12.5,
};

describe("Relatorio", () => {
  it("sem elements mantém as sete linhas de sempre", () => {
    const dom = renderiza(BASE);

    expect(rotulos(dom)).toHaveLength(7);
    expect(rotulos(dom)).not.toContain("Tabelas");
    expect(valorDe(dom, "Chunks gerados")).toBe("50");
  });

  it("com elements acrescenta as três contagens", () => {
    const dom = renderiza({ ...BASE, elements: { textos: 36, tabelas: 9, imagens: 5 } });

    expect(rotulos(dom)).toHaveLength(10);
    expect(valorDe(dom, "Textos")).toBe("36");
    expect(valorDe(dom, "Tabelas")).toBe("9");
    expect(valorDe(dom, "Imagens")).toBe("5");
  });

  // Zero é o sinal de que a detecção não rodou; virar travessão o esconderia.
  it("exibe zero explícito, não travessão", () => {
    const dom = renderiza({ ...BASE, elements: { textos: 41, tabelas: 0, imagens: 0 } });

    expect(valorDe(dom, "Tabelas")).toBe("0");
    expect(valorDe(dom, "Imagens")).toBe("0");
  });
});
