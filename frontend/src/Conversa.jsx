import { useState } from "react";

/**
 * Interface de conversa, ativada pela feature `history` do contrato.
 *
 * Genérica por contrato, como o resto do cliente: nada aqui conhece o
 * rag-02. O que liga esta tela é o backend declarar `history` em `features`, e
 * um backend que não declare (o rag-01, por exemplo) continua vendo a tela de
 * pergunta única, sem alteração nenhuma.
 *
 * **A transcrição é propriedade deste cliente.** O backend não guarda conversa:
 * o `App` mantém os turnos e os devolve em `options.history` a cada pergunta.
 * Recarregar a página esquece a conversa, e isso é o comportamento correto.
 */

/**
 * Renderiza o texto quebrando os rótulos [n] em botões clicáveis.
 *
 * O rótulo só vira botão se existir em `citations`. Um [n] que o backend não
 * resolveu fica como texto puro e aparece no aviso de rótulos não resolvidos:
 * fingir que é uma citação seria oferecer procedência que não existe.
 */
function TextoComCitacoes({ texto, citacoes, aoClicar }) {
  const porRotulo = new Map((citacoes ?? []).map((c) => [c.label, c]));
  const partes = texto.split(/(\[\d+\])/g);

  return (
    <>
      {partes.map((parte, i) => {
        const casou = parte.match(/^\[(\d+)\]$/);
        if (!casou) return <span key={i}>{parte}</span>;

        const rotulo = Number(casou[1]);
        if (!porRotulo.has(rotulo)) return <span key={i}>{parte}</span>;

        return (
          <button
            key={i}
            type="button"
            className="citacao-rotulo"
            onClick={() => aoClicar(rotulo)}
            title={`${porRotulo.get(rotulo).source} · p.${porRotulo.get(rotulo).page}`}
          >
            {parte}
          </button>
        );
      })}
    </>
  );
}

/** A pergunta que foi de fato buscada, e por que ela difere da digitada. */
function Reescrita({ dados }) {
  if (!dados) return null;

  if (!dados.rewritten) {
    return (
      <details className="reescrita">
        <summary>
          buscou a pergunta como digitada <em>({dados.reason})</em>
        </summary>
        <p className="reescrita-linha">
          <span>buscado</span>
          <code>{dados.used}</code>
        </p>
      </details>
    );
  }

  return (
    <details className="reescrita reescreveu" open>
      <summary>
        a pergunta foi reescrita antes de buscar <em>({dados.reason})</em>
      </summary>
      <p className="reescrita-linha">
        <span>você digitou</span>
        <code>{dados.original}</code>
      </p>
      <p className="reescrita-linha">
        <span>foi buscado</span>
        <code>{dados.used}</code>
      </p>
    </details>
  );
}

function Citacoes({ citacoes, indice, destaque }) {
  if (!citacoes?.length) return null;

  return (
    <ol className="citacoes">
      {citacoes.map((c) => (
        <li
          // O id é o alvo do clique no rótulo [n] dentro do texto. Sem ele o
          // getElementById devolve null e o scrollIntoView não roda em silêncio,
          // que foi o defeito da primeira versão. O índice do turno entra na
          // chave porque numa conversa há vários [1], um por turno.
          id={`citacao-${indice}-${c.label}`}
          key={c.label}
          className={destaque === c.label ? "citacao destacada" : "citacao"}
        >
          <div className="trecho-cabecalho">
            <span className="rotulo">[{c.label}]</span>
            <span className="fonte">
              {c.source}
              {c.page != null && ` · p.${c.page}`}
            </span>
          </div>
          <p className="trecho-texto">{c.excerpt}</p>
        </li>
      ))}
    </ol>
  );
}

/** Um turno: a pergunta digitada e a resposta completa do backend. */
export function Turno({ pergunta, dados, indice }) {
  const naoResolvidos = dados.meta?.unresolved_labels ?? [];
  const [destaque, setDestaque] = useState(null);

  return (
    <article className="turno">
      <p className="turno-pergunta">
        <span className="turno-numero">{indice}</span>
        {pergunta}
      </p>

      <Reescrita dados={dados.rewritten_question} />

      <div className={dados.refused ? "texto recusou" : "texto"}>
        {dados.refused && <span className="selo">recusou</span>}
        <TextoComCitacoes
          texto={dados.text}
          citacoes={dados.citations}
          aoClicar={(rotulo) => {
            document
              .getElementById(`citacao-${indice}-${rotulo}`)
              ?.scrollIntoView({ behavior: "smooth", block: "center" });
            setDestaque(rotulo);
          }}
        />
      </div>

      {naoResolvidos.length > 0 && (
        <p className="aviso-citacao">
          o modelo citou {naoResolvidos.map((n) => `[${n}]`).join(", ")} sem trecho
          correspondente. citação sem procedência não é citação.
        </p>
      )}

      <Citacoes citacoes={dados.citations} indice={indice} destaque={destaque} />

      <div className="metricas">
        {dados.timings?.rewrite_s != null && (
          <span>reescrita {dados.timings.rewrite_s}s</span>
        )}
        {dados.timings?.search_s != null && <span>busca {dados.timings.search_s}s</span>}
        {dados.timings?.generation_s != null && (
          <span>geração {dados.timings.generation_s}s</span>
        )}
        <span>{dados.hits?.length ?? 0} chunks</span>
      </div>

      <details className="trechos-recuperados">
        <summary>trechos recuperados pela busca</summary>
        <ol className="trechos">
          {(dados.hits ?? []).map((h, i) => (
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
        <p className="legenda">
          distância: menor é mais próximo. estes são os candidatos da busca, não a
          procedência das afirmações.
        </p>
      </details>
    </article>
  );
}

export function Conversa({ turnos, aoLimpar }) {
  if (!turnos.length) return null;

  return (
    <section className="conversa">
      <div className="conversa-cabecalho">
        <h2>Conversa</h2>
        <button type="button" className="secundario" onClick={aoLimpar}>
          Limpar conversa
        </button>
      </div>
      {turnos.map((t, i) => (
        <Turno key={i} indice={i + 1} pergunta={t.pergunta} dados={t.dados} />
      ))}
    </section>
  );
}
