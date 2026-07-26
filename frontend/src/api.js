/**
 * Cliente do contrato RAG compartilhado.
 *
 * Contrato: ../../docs/contracts/rag-api.yaml
 *
 * Esta é a ÚNICA camada que conhece HTTP. Ela não sabe o que é chunk, distância
 * ou embedding: só transporta. E, de propósito, não conhece nenhum parâmetro
 * específico de projeto — `options` é repassado como veio.
 */

const TEMPO_LIMITE_MS = 120_000;

/** Erro já traduzido para algo exibível. Nunca vaza `fetch` cru para a interface. */
export class ErroDaApi extends Error {
  constructor(titulo, detalhe, codigo, status) {
    super(detalhe || titulo);
    this.titulo = titulo;
    this.detalhe = detalhe;
    this.codigo = codigo;
    this.status = status;
  }
}

async function requisitar(baseUrl, caminho, opcoes = {}) {
  const controle = new AbortController();
  const relogio = setTimeout(() => controle.abort(), TEMPO_LIMITE_MS);

  let resposta;
  try {
    resposta = await fetch(`${baseUrl.replace(/\/$/, "")}${caminho}`, {
      ...opcoes,
      signal: controle.signal,
      headers: { "Content-Type": "application/json", ...opcoes.headers },
    });
  } catch (e) {
    clearTimeout(relogio);
    // Falha de rede não tem corpo JSON: o backend nem foi alcançado.
    throw new ErroDaApi(
      e.name === "AbortError" ? "Tempo esgotado" : "Backend inalcançável",
      e.name === "AbortError"
        ? `Nenhuma resposta em ${TEMPO_LIMITE_MS / 1000}s.`
        : `Não consegui falar com ${baseUrl}. O serviço está no ar?`,
      "NETWORK",
      0,
    );
  }
  clearTimeout(relogio);

  const corpo = await resposta.json().catch(() => null);

  if (!resposta.ok) {
    // O contrato define o formato de erro; se vier outra coisa, degradamos.
    throw new ErroDaApi(
      corpo?.title ?? `HTTP ${resposta.status}`,
      corpo?.detail ?? "O backend respondeu com erro, sem detalhe.",
      corpo?.code ?? "UNKNOWN",
      resposta.status,
    );
  }
  return corpo;
}

export const api = {
  saude: (base) => requisitar(base, "/health"),
  capacidades: (base) => requisitar(base, "/capabilities"),

  perguntar: (base, pergunta, options) =>
    requisitar(base, "/ask", {
      method: "POST",
      body: JSON.stringify({ question: pergunta, options }),
    }),

  indexar: (base, options) =>
    requisitar(base, "/ingest", {
      method: "POST",
      body: JSON.stringify({ options }),
    }),
};
