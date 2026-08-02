import { describe, expect, it } from "vitest";
import { sanitizaHtml } from "./sanitiza";

/**
 * T5.1 — o HTML de documento nunca entra cru no DOM.
 *
 * Estes casos são o contrato de segurança do `content_html`: o que precisa
 * sobreviver (a tabela) e o que não pode sobreviver de jeito nenhum.
 */
describe("sanitizaHtml", () => {
  it("preserva a tabela intacta", () => {
    const limpo = sanitizaHtml(
      "<table><tr><th>Indicador</th><th>3T24</th></tr>" +
        "<tr><td>Receita de vendas</td><td>129,6</td></tr></table>",
    );

    expect(limpo).toContain("<table>");
    expect(limpo).toContain("<td>Receita de vendas</td>");
    expect(limpo).toContain("129,6");
  });

  it("preserva colspan, rowspan e scope de célula mesclada", () => {
    const limpo = sanitizaHtml(
      '<table><tr><th scope="col" colspan="2">3T24</th></tr>' +
        '<tr><td rowspan="2">Receita</td><td>129,6</td></tr></table>',
    );

    expect(limpo).toContain('colspan="2"');
    expect(limpo).toContain('rowspan="2"');
    expect(limpo).toContain('scope="col"');
  });

  it("remove script", () => {
    const limpo = sanitizaHtml(
      "<table><tr><td>ok<script>window.roubado = 1</script></td></tr></table>",
    );

    expect(limpo).not.toContain("script");
    expect(limpo).not.toContain("roubado");
    expect(limpo).toContain("ok");
  });

  it("remove handlers on*", () => {
    const limpo = sanitizaHtml(
      '<table><tr><td onclick="alert(1)" onmouseover="alert(2)">129,6</td></tr></table>',
    );

    expect(limpo).not.toContain("onclick");
    expect(limpo).not.toContain("onmouseover");
    expect(limpo).not.toContain("alert");
    expect(limpo).toContain("129,6");
  });

  it("remove atributos e tags perigosas fora da lista de permissão", () => {
    const limpo = sanitizaHtml(
      '<table><tr><td style="position:fixed">a</td></tr></table>' +
        '<img src=x onerror="alert(1)">' +
        '<iframe src="http://mal"></iframe>' +
        '<a href="javascript:alert(1)">clique</a>',
    );

    expect(limpo).not.toContain("style");
    expect(limpo).not.toContain("<img");
    expect(limpo).not.toContain("<iframe");
    expect(limpo).not.toContain("javascript:");
    expect(limpo).not.toContain("href");
  });

  it("degrada para vazio em entrada ausente ou não textual", () => {
    expect(sanitizaHtml(undefined)).toBe("");
    expect(sanitizaHtml(null)).toBe("");
    expect(sanitizaHtml("")).toBe("");
    expect(sanitizaHtml(42)).toBe("");
  });
});
