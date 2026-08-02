import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import Trecho from "./Trecho";

/**
 * T5.2 e T5.3 — a renderização do trecho no contrato 1.3.0 e a aditividade.
 *
 * Renderiza no DOM de verdade (não em string) porque a pergunta é justamente se
 * a tabela chega como ELEMENTO ou como tag escapada, e as duas coisas são a
 * mesma string até alguém pedir `querySelector("table")`.
 */

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

function renderiza(hit) {
  act(() => root.render(<Trecho hit={hit} />));
  return container;
}

const TABELA =
  "<table><tr><th>Indicador</th><th>3T24</th></tr>" +
  "<tr><td>Receita de vendas</td><td>129,6</td></tr></table>";

describe("Trecho com kind=tabela", () => {
  it("renderiza uma tabela real a partir do content_html", () => {
    const dom = renderiza({
      source: "petrobras-3t24.pdf",
      page: 12,
      kind: "tabela",
      excerpt: "A tabela apresenta dados financeiros da empresa no 3T24.",
      content_html: TABELA,
    });

    const tabela = dom.querySelector(".trecho-tabela table");
    expect(tabela).not.toBeNull();
    expect(tabela.querySelectorAll("tr")).toHaveLength(2);
    expect(tabela.querySelectorAll("td")).toHaveLength(2);
    expect(tabela.textContent).toContain("129,6");
    // O resumo é o que casou com a busca, mas quem tem a tabela mostra a tabela.
    expect(dom.querySelector(".trecho-texto")).toBeNull();
  });

  it("mostra o selo de tabela no cabeçalho", () => {
    const dom = renderiza({ source: "a.pdf", kind: "tabela", excerpt: "resumo", content_html: TABELA });

    expect(dom.querySelector(".trecho-cabecalho .selo-kind").textContent).toBe("tabela");
  });

  it("não deixa script do content_html chegar ao DOM", () => {
    const dom = renderiza({
      source: "a.pdf",
      kind: "tabela",
      excerpt: "resumo",
      content_html: '<table><tr><td onclick="alert(1)">129,6<script>alert(2)</script></td></tr></table>',
    });

    expect(dom.querySelector("script")).toBeNull();
    expect(dom.querySelector("td").getAttribute("onclick")).toBeNull();
    expect(dom.innerHTML).not.toContain("alert");
  });

  // US-010.EC-1: o unstructured erra a tabela de vez em quando. A UI não pode
  // sumir com o hit por causa disso.
  it("com HTML malformado renderiza o que der, sem esconder o hit", () => {
    const dom = renderiza({
      source: "a.pdf",
      kind: "tabela",
      excerpt: "resumo",
      content_html: "<table><tr><td>129,6<td>122,2</tr><tr><td>sem fechar",
    });

    const tabela = dom.querySelector(".trecho-tabela table");
    expect(tabela).not.toBeNull();
    expect(tabela.textContent).toContain("129,6");
    expect(tabela.textContent).toContain("sem fechar");
  });

  // Sanitizar até sobrar nada (HTML que era só script) também degrada.
  it("com content_html que some na sanitização cai para o excerpt", () => {
    const dom = renderiza({
      source: "a.pdf",
      kind: "tabela",
      excerpt: "resumo da tabela",
      content_html: "<script>alert(1)</script>",
    });

    expect(dom.querySelector("table")).toBeNull();
    expect(dom.querySelector(".trecho-texto").textContent).toBe("resumo da tabela");
  });

  // US-010.EC-3: inconsistência do emissor degrada, não some com o hit.
  it("sem content_html cai para o excerpt como texto", () => {
    const dom = renderiza({ source: "a.pdf", kind: "tabela", excerpt: "resumo da tabela" });

    expect(dom.querySelector("table")).toBeNull();
    expect(dom.querySelector(".trecho-texto").textContent).toBe("resumo da tabela");
    expect(dom.querySelector(".selo-kind").textContent).toBe("tabela");
  });
});

describe("Trecho com os demais kinds", () => {
  it("kind=imagem mostra a descrição como texto, com selo", () => {
    const dom = renderiza({ source: "a.pdf", kind: "imagem", excerpt: "Gráfico de barras da receita." });

    expect(dom.querySelector("table")).toBeNull();
    expect(dom.querySelector(".trecho-texto").textContent).toBe("Gráfico de barras da receita.");
    expect(dom.querySelector(".selo-kind").textContent).toBe("imagem");
  });

  it("kind desconhecido não renderiza selo e não quebra", () => {
    const dom = renderiza({ source: "a.pdf", kind: "formula", excerpt: "trecho" });

    expect(dom.querySelector(".selo-kind")).toBeNull();
    expect(dom.querySelector(".trecho-texto").textContent).toBe("trecho");
  });

  // T5.3 / US-010.AC-4 — payload dos projetos 1 a 3, sem nenhum campo 1.3.0.
  it("hit sem kind renderiza como antes, sem selo", () => {
    const dom = renderiza({
      source: "harry-potter.pdf",
      page: 7,
      distance: 0.3123,
      excerpt: "A Pedra Filosofal transforma metal em ouro.",
    });

    expect(dom.querySelector(".selo-kind")).toBeNull();
    expect(dom.querySelector("table")).toBeNull();
    expect(dom.querySelector(".fonte").textContent).toBe("harry-potter.pdf · p.7");
    expect(dom.querySelector(".trecho-texto").textContent).toBe(
      "A Pedra Filosofal transforma metal em ouro.",
    );
    // A procedência do 1.2.0 continua inteira.
    expect(dom.querySelector(".procedencia .distancia").textContent).toBe("dist 0.3123");
  });
});
