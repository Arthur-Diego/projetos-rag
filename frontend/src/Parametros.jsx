/**
 * Renderiza controles a partir do `parameters` de /capabilities.
 *
 * **Este arquivo é o coração do desacoplamento.** Ele não conhece `k`,
 * `chunk_size`, `rerank_top_n` nem `max_hops`. Recebe um descritor e desenha.
 * Um projeto novo acrescenta uma entrada no /capabilities dele e o controle
 * aparece aqui sozinho, sem uma linha alterada.
 *
 * Se algum dia aparecer um `if (nome === "k")` neste arquivo, o desacoplamento
 * terá acabado.
 */

export function Parametros({ especificacoes, operacao, valores, aoMudar, desabilitado }) {
  const relevantes = Object.entries(especificacoes ?? {}).filter(
    ([, spec]) => !spec.applies_to || spec.applies_to.includes(operacao),
  );

  if (relevantes.length === 0) return null;

  return (
    <div className="parametros">
      {relevantes.map(([nome, spec]) => (
        <label key={nome} className="parametro" title={spec.help ?? ""}>
          <span className="parametro-rotulo">{spec.label ?? nome}</span>
          <Controle
            nome={nome}
            spec={spec}
            valor={valores[nome] ?? spec.default}
            aoMudar={aoMudar}
            desabilitado={desabilitado}
          />
          {spec.help && <span className="parametro-ajuda">{spec.help}</span>}
        </label>
      ))}
    </div>
  );
}

function Controle({ nome, spec, valor, aoMudar, desabilitado }) {
  const comum = { id: nome, disabled: desabilitado };

  if (spec.type === "boolean") {
    return (
      <input
        {...comum}
        type="checkbox"
        checked={Boolean(valor)}
        onChange={(e) => aoMudar(nome, e.target.checked)}
      />
    );
  }

  if (spec.type === "enum") {
    return (
      <select {...comum} value={valor ?? ""} onChange={(e) => aoMudar(nome, e.target.value)}>
        {(spec.values ?? []).map((v) => (
          <option key={v} value={v}>{v}</option>
        ))}
      </select>
    );
  }

  if (spec.type === "integer" || spec.type === "number") {
    return (
      <input
        {...comum}
        type="number"
        value={valor ?? ""}
        min={spec.minimum}
        max={spec.maximum}
        step={spec.type === "integer" ? 1 : "any"}
        onChange={(e) => {
          const bruto = e.target.value;
          aoMudar(nome, bruto === "" ? undefined : Number(bruto));
        }}
      />
    );
  }

  return (
    <input
      {...comum}
      type="text"
      value={valor ?? ""}
      onChange={(e) => aoMudar(nome, e.target.value)}
    />
  );
}
