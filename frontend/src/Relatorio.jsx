/**
 * Relatório de ingestão.
 *
 * As sete primeiras linhas são as de sempre. As três de `elements` são 1.3.0 e
 * só aparecem quando o backend as emite: um projeto que não separa a fonte por
 * tipo não ganha três linhas zeradas afirmando que procurou tabela e não achou.
 *
 * **Dentro de `elements`, zero é dado, não ausência.** O contrato exige as três
 * contagens sempre que o objeto existe, justamente porque `tabelas: 0` num
 * relatório financeiro é o sinal de que a detecção não rodou — e some se for
 * confundido com "campo vazio". O `?? "—"` compartilhado com as demais linhas é
 * inofensivo aqui: `0` não é nullish e é exibido como `0`; o travessão só
 * apareceria se o backend violasse o `required` do próprio objeto.
 */
export default function Relatorio({ dados }) {
  const linhas = [
    ["Páginas lidas", dados.pages],
    ["Chunks gerados", dados.chunks],
    ["Páginas sem texto", dados.discarded_pages],
    ["Chunks descartados", dados.previous_chunks],
    ["Tamanho do chunk", dados.chunk_size],
    ["Sobreposição", dados.chunk_overlap],
    ["Tempo", `${dados.seconds}s`],
  ];

  const e = dados.elements;
  if (e != null) {
    linhas.push(["Textos", e.textos], ["Tabelas", e.tabelas], ["Imagens", e.imagens]);
  }

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
