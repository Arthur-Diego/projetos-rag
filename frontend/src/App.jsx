import { useCallback, useEffect, useState } from "react";
import { api, ErroDaApi } from "./api";
import { Parametros } from "./Parametros";
import "./App.css";

const BACKEND_PADRAO = "http://localhost:8080";

/**
 * Cliente genérico do contrato RAG.
 *
 * Não conhece nenhum projeto. Descobre o que o backend sabe fazer por
 * /capabilities e se adapta: esconde a aba de indexação se o backend não
 * declarar `ingest`, e desenha os controles a partir do descritor.
 */
export default function App() {
  const [backend, setBackend] = useState(
    () => localStorage.getItem("backend") ?? BACKEND_PADRAO,
  );
  const [saude, setSaude] = useState(null);
  const [capacidades, setCapacidades] = useState(null);
  const [erroDeConexao, setErroDeConexao] = useState(null);

  const [operacao, setOperacao] = useState("ask");
  const [opcoes, setOpcoes] = useState({});
  const [pergunta, setPergunta] = useState("");

  const [ocupado, setOcupado] = useState(false);
  const [resposta, setResposta] = useState(null);
  const [relatorio, setRelatorio] = useState(null);
  const [erro, setErro] = useState(null);

  const conectar = useCallback(async (url) => {
    setSaude(null);
    setCapacidades(null);
    setErroDeConexao(null);
    try {
      const [s, c] = await Promise.all([api.saude(url), api.capacidades(url)]);
      setSaude(s);
      setCapacidades(c);
      // Preenche os defaults declarados pelo backend.
      const padroes = {};
      for (const [nome, spec] of Object.entries(c.parameters ?? {})) {
        if (spec.default !== undefined) padroes[nome] = spec.default;
      }
      setOpcoes(padroes);
      if (!c.features?.includes("ask") && c.features?.includes("ingest")) {
        setOperacao("ingest");
      }
    } catch (e) {
      setErroDeConexao(
        e instanceof ErroDaApi ? e : new ErroDaApi("Falha", String(e), "UNKNOWN", 0),
      );
    }
  }, []);

  useEffect(() => {
    localStorage.setItem("backend", backend);
    conectar(backend);
  }, [backend, conectar]);

  const mudarOpcao = (nome, valor) =>
    setOpcoes((atual) => ({ ...atual, [nome]: valor }));

  async function enviar(e) {
    e.preventDefault();
    setErro(null);
    setResposta(null);
    setRelatorio(null);
    setOcupado(true);
    try {
      if (operacao === "ask") {
        setResposta(await api.perguntar(backend, pergunta, opcoes));
      } else {
        setRelatorio(await api.indexar(backend, opcoes));
        await conectar(backend); // a contagem de chunks mudou
      }
    } catch (e) {
      setErro(e);
    } finally {
      setOcupado(false);
    }
  }

  const conectado = Boolean(saude && capacidades);
  const podeIndexar = capacidades?.features?.includes("ingest");
  const podePerguntar = capacidades?.features?.includes("ask");

  return (
    <div className="app">
      <header className="cabecalho">
        <div>
          <h1>Cliente RAG</h1>
          <p className="subtitulo">
            Genérico por contrato. Os controles abaixo vêm do <code>/capabilities</code>{" "}
            do backend, não deste código.
          </p>
        </div>
        <label className="campo-backend">
          <span>Backend</span>
          <input
            value={backend}
            onChange={(e) => setBackend(e.target.value.trim())}
            spellCheck={false}
          />
        </label>
      </header>

      <section className={`estado ${conectado ? "ok" : "ruim"}`}>
        {conectado ? (
          <>
            <strong>{capacidades.project}</strong>
            <span>
              {saude.indexed_chunks} chunks em “{saude.collection}”
            </span>
            <span>
              {saude.embedding_model} · {saude.embedding_dimensions}d
            </span>
            <span className="etiquetas">
              {capacidades.features.map((f) => (
                <em key={f}>{f}</em>
              ))}
            </span>
          </>
        ) : (
          <>
            <strong>{erroDeConexao?.titulo ?? "Conectando…"}</strong>
            {erroDeConexao && <span>{erroDeConexao.detalhe}</span>}
          </>
        )}
      </section>

      {conectado && (
        <form onSubmit={enviar} className="formulario">
          <div className="abas" role="tablist">
            {podePerguntar && (
              <button
                type="button"
                role="tab"
                aria-selected={operacao === "ask"}
                className={operacao === "ask" ? "aba ativa" : "aba"}
                onClick={() => setOperacao("ask")}
              >
                Perguntar
              </button>
            )}
            {podeIndexar && (
              <button
                type="button"
                role="tab"
                aria-selected={operacao === "ingest"}
                className={operacao === "ingest" ? "aba ativa" : "aba"}
                onClick={() => setOperacao("ingest")}
              >
                Indexar
              </button>
            )}
          </div>

          <Parametros
            especificacoes={capacidades.parameters}
            operacao={operacao}
            valores={opcoes}
            aoMudar={mudarOpcao}
            desabilitado={ocupado}
          />

          {operacao === "ask" ? (
            <div className="linha-pergunta">
              <input
                className="pergunta"
                value={pergunta}
                onChange={(e) => setPergunta(e.target.value)}
                placeholder="Segundo o texto, o que a Pedra Filosofal faz?"
                disabled={ocupado}
              />
              <button type="submit" disabled={ocupado || !pergunta.trim()}>
                {ocupado ? "Buscando…" : "Perguntar"}
              </button>
            </div>
          ) : (
            <div className="linha-pergunta">
              <p className="aviso">
                Indexar <strong>apaga o índice atual</strong> e reconstrói do zero. Gasta
                chamadas de embedding.
              </p>
              <button type="submit" disabled={ocupado}>
                {ocupado ? "Indexando…" : "Reindexar"}
              </button>
            </div>
          )}
        </form>
      )}

      {erro && (
        <section className="erro">
          <strong>{erro.titulo}</strong>
          <p>{erro.detalhe}</p>
          <code>{erro.codigo}</code>
        </section>
      )}

      {resposta && <Resposta dados={resposta} />}
      {relatorio && <Relatorio dados={relatorio} />}
    </div>
  );
}

function Resposta({ dados }) {
  return (
    <section className="resposta">
      <div className={dados.refused ? "texto recusou" : "texto"}>
        {dados.refused && <span className="selo">recusou</span>}
        {dados.text}
      </div>

      <div className="metricas">
        <span>busca {dados.timings.search_s}s</span>
        <span>geração {dados.timings.generation_s}s</span>
        <span>{dados.hits.length} chunks</span>
      </div>

      <ol className="trechos">
        {dados.hits.map((h, i) => (
          <li key={i}>
            <div className="trecho-cabecalho">
              <span className="fonte">
                {h.source}
                {h.page != null && ` · p.${h.page}`}
              </span>
              <span className="distancia">dist {h.distance}</span>
            </div>
            <p className="trecho-texto">{h.excerpt}</p>
          </li>
        ))}
      </ol>
      <p className="legenda">distância: menor é mais próximo</p>
    </section>
  );
}

function Relatorio({ dados }) {
  const linhas = [
    ["Páginas lidas", dados.pages],
    ["Chunks gerados", dados.chunks],
    ["Páginas sem texto", dados.discarded_pages],
    ["Chunks descartados", dados.previous_chunks],
    ["Tamanho do chunk", dados.chunk_size],
    ["Sobreposição", dados.chunk_overlap],
    ["Tempo", `${dados.seconds}s`],
  ];
  return (
    <section className="resposta">
      <dl className="relatorio">
        {linhas.map(([rotulo, valor]) => (
          <div key={rotulo}>
            <dt>{rotulo}</dt>
            <dd>{valor ?? "—"}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
}
