/**
 * Procedência de um trecho recuperado, do contrato 1.2.0.
 *
 * Responde à pergunta "por que este trecho está nesta posição?", que num funil
 * híbrido não é óbvia: o trecho pode estar em primeiro por ter vencido a busca
 * semântica, por ter vencido a léxica, por ter aparecido no meio das duas e
 * sido promovido pela fusão, ou por ter subido na reordenação.
 *
 * **Tudo aqui é opcional, e é o que mantém o frontend genérico.** Os projetos
 * que fazem busca densa e nada mais (rag-01, rag-02) não publicam nenhum destes
 * campos, e para eles este componente não renderiza nada além da distância que
 * já renderizava antes. Nenhum deles precisou de uma linha de alteração.
 *
 * **`distance` e `score` NUNCA compartilham rótulo.** Têm sentidos opostos:
 * menor é melhor na distância, maior é melhor na pontuação. Exibir os dois sob
 * o mesmo nome inverteria a leitura de quem procura "o mais próximo".
 */

/** Formata número com casas fixas, tolerando ausência e valor não numérico. */
function num(valor, casas) {
  return typeof valor === "number" ? valor.toFixed(casas) : null;
}

export default function Procedencia({ hit }) {
  const p = hit.provenance;

  // Ranks são 1-based e vêm por caminho. Ausente significa "não veio deste
  // caminho", nunca "veio em primeiro": zero aqui seria uma afirmação diferente.
  const caminhos = [];
  if (p?.dense_rank != null) caminhos.push(`densa #${p.dense_rank}`);
  if (p?.keyword_rank != null) caminhos.push(`bm25 #${p.keyword_rank}`);

  const rrf = num(p?.rrf_score, 5);
  const rerank = num(p?.rerank_score, 3);
  const distancia = num(hit.distance, 4);

  return (
    <span className="procedencia">
      {caminhos.length > 0 && (
        <span
          className="caminhos"
          title="Em que posição cada busca encontrou este trecho"
        >
          {caminhos.join(" + ")}
        </span>
      )}
      {rrf != null && (
        <span className="fusao" title="Fusão por posição: maior é melhor">
          rrf {rrf}
        </span>
      )}
      {rerank != null && (
        <span className="rerank" title="Reordenação: maior é melhor">
          rerank {rerank}
        </span>
      )}
      {distancia != null && (
        <span className="distancia" title="Distância vetorial: MENOR é mais próximo">
          dist {distancia}
        </span>
      )}
    </span>
  );
}

/**
 * Tempos por estágio, do contrato 1.2.0.
 *
 * `search_s` é o TOTAL da recuperação; os quatro campos novos o decompõem, e por
 * isso somar os cinco contaria a recuperação duas vezes. O rótulo diz "busca
 * total" para que ninguém tente somar.
 *
 * Estágio que não rodou vem AUSENTE da resposta, nunca zerado, e aqui isso
 * aparece como ausência de badge. É a diferença entre "a busca léxica foi
 * instantânea" e "a busca léxica não rodou".
 */
export function Tempos({ timings }) {
  if (!timings) return null;

  const estagios = [
    ["reescrita", timings.rewrite_s],
    ["densa", timings.dense_s],
    ["bm25", timings.keyword_s],
    ["fusão", timings.fusion_s],
    ["rerank", timings.rerank_s],
    ["busca total", timings.search_s],
    ["geração", timings.generation_s],
  ];

  return estagios
    .filter(([, valor]) => valor != null)
    .map(([nome, valor]) => (
      <span key={nome}>
        {nome} {valor}s
      </span>
    ));
}
