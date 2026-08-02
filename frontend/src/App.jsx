import { useCallback, useEffect, useState } from "react";
import { api, ErroDaApi } from "./api";
import { Conversa } from "./Conversa";
import { Parametros } from "./Parametros";
import { Tempos } from "./Procedencia";
import Relatorio from "./Relatorio";
import Trecho from "./Trecho";
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
  // Os turnos já ocorridos: `{ pergunta, dados }`. Num backend sem a feature
  // `history` a lista nunca passa de um item, e a tela fica idêntica à de antes.
  const [turnos, setTurnos] = useState([]);
  const [relatorio, setRelatorio] = useState(null);
  const [erro, setErro] = useState(null);

  const conectar = useCallback(async (url) => {
    setSaude(null);
    setCapacidades(null);
    setErroDeConexao(null);
    // Trocar de backend descarta a conversa: a transcrição só faz sentido
    // contra o corpus e o modelo que a produziram.
    setTurnos([]);
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

  const conectado = Boolean(saude && capacidades);
  const podeIndexar = capacidades?.features?.includes("ingest");
  const podePerguntar = capacidades?.features?.includes("ask");
  // A feature `history` significa: guarde a transcrição e devolva a cada
  // pergunta. O backend não guarda conversa nenhuma.
  const podeConversar = capacidades?.features?.includes("history");

  async function enviar(e) {
    e.preventDefault();
    setErro(null);
    setRelatorio(null);
    setOcupado(true);
    try {
      if (operacao === "ask") {
        const enviados = podeConversar
          ? {
              ...opcoes,
              // A transcrição vai INTEIRA; quem trunca é o servidor, pela
              // janela que ele declarou em /capabilities.
              history: turnos.map((t) => ({
                question: t.pergunta,
                answer: t.dados.text,
              })),
            }
          : opcoes;

        const dados = await api.perguntar(backend, pergunta, enviados);
        const turno = { pergunta, dados };
        // Sem conversa, cada pergunta substitui a anterior, como antes.
        setTurnos((atuais) => (podeConversar ? [...atuais, turno] : [turno]));
        if (podeConversar) setPergunta("");
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
                placeholder={
                  podeConversar && turnos.length
                    ? "E se eu vender dez?"
                    : "Segundo o texto, o que a Pedra Filosofal faz?"
                }
                disabled={ocupado}
              />
              <button type="submit" disabled={ocupado || !pergunta.trim()}>
                {ocupado ? "Buscando…" : podeConversar ? "Enviar" : "Perguntar"}
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

      {podeConversar
        ? <Conversa turnos={turnos} aoLimpar={() => setTurnos([])} />
        : turnos.length > 0 && <Resposta dados={turnos[turnos.length - 1].dados} />}
      {relatorio && <Relatorio dados={relatorio} />}
    </div>
  );
}

/**
 * Resposta única, para backends que não declaram a feature `history`.
 *
 * Os acessos a `timings` e `hits` são protegidos: eles são obrigatórios no
 * contrato, mas um backend em desenvolvimento pode não emiti-los, e uma tela
 * que quebra inteira por causa de um campo ausente esconde o erro de verdade.
 */
function Resposta({ dados }) {
  return (
    <section className="resposta">
      <div className={dados.refused ? "texto recusou" : "texto"}>
        {dados.refused && <span className="selo">recusou</span>}
        {dados.text}
      </div>

      <div className="metricas">
        <Tempos timings={dados.timings} />
        <span>{dados.hits?.length ?? 0} chunks</span>
      </div>

      <ol className="trechos">
        {(dados.hits ?? []).map((h, i) => (
          <li key={i}>
            <Trecho hit={h} />
          </li>
        ))}
      </ol>
      <p className="legenda">
        distância: menor é mais próximo · rrf e rerank: maior é melhor
      </p>
    </section>
  );
}

