import Procedencia from "./Procedencia";
import { sanitizaHtml } from "./sanitiza";

/**
 * Um trecho recuperado, do contrato 1.3.0.
 *
 * Existia duplicado em `App.jsx` e `Conversa.jsx` (a mesma lista de hits, uma
 * na resposta única e outra dentro do turno). A renderização de tabela seria a
 * terceira coisa a copiar entre os dois, então virou componente.
 *
 * **Tudo que é 1.3.0 aqui é opcional, no molde da `Procedencia`.** Um backend
 * dos projetos 1 a 3 não emite `kind` nem `content_html`, e para ele este
 * componente renderiza exatamente o que a lista renderizava antes: fonte,
 * página, procedência e o excerpt como texto.
 */

const KINDS_CONHECIDOS = new Set(["texto", "tabela", "imagem"]);

/**
 * Selo do tipo da fonte.
 *
 * Ausente significa "este backend não separa a fonte por tipo", não "é texto":
 * o contrato manda tratar a ausência como texto para EXIBIÇÃO, e exibir um selo
 * "texto" que o backend não afirmou seria inventar procedência. `kind`
 * desconhecido (contrato futuro) também não renderiza nada — o cliente é
 * genérico e não pode quebrar por causa de um valor que ainda não conhece.
 */
export function SeloKind({ kind }) {
  if (kind == null || !KINDS_CONHECIDOS.has(kind)) return null;

  return (
    <span className={`selo-kind ${kind}`} title="Que tipo de fonte é este trecho">
      {kind}
    </span>
  );
}

/**
 * A tabela original, renderizada de verdade.
 *
 * O HTML passa pela sanitização SEMPRE, e é o resultado dela — nunca o
 * `content_html` cru — que chega ao `dangerouslySetInnerHTML`. Sanitização que
 * devolve vazio (sem DOM, ou HTML que era só script) faz o chamador degradar
 * para o excerpt: melhor o resumo em texto do que um bloco em branco.
 *
 * A rolagem horizontal é do contêiner. Uma tabela de balanço tem oito colunas e
 * estoura a coluna de fontes; sem `overflow-x` aqui, quem ganha barra lateral é
 * a página inteira, e aí todo o resto da tela anda junto.
 */
function TabelaOriginal({ html }) {
  return (
    <div
      className="trecho-tabela"
      // `html` é sempre o retorno de `sanitizaHtml`. Este é o único
      // `dangerouslySetInnerHTML` do cliente, e a auditoria é um grep.
      dangerouslySetInnerHTML={{ __html: html }}
    />
  );
}

export default function Trecho({ hit }) {
  // Só `kind=tabela` tem `content_html` no contrato. Sanitizar antes de decidir
  // deixa a degradação da EC-3 (tabela sem HTML) e a de HTML vazio no mesmo
  // caminho: sem tabela para mostrar, mostra o excerpt.
  const tabela = hit.kind === "tabela" ? sanitizaHtml(hit.content_html) : "";

  return (
    <>
      <div className="trecho-cabecalho">
        <span className="fonte">
          {hit.source}
          {hit.page != null && ` · p.${hit.page}`}
        </span>
        {/* Sem invólucro de propósito: um hit dos projetos 1 a 3 não tem selo, e
            sem selo o cabeçalho volta a ser exatamente `fonte` + `procedência`,
            byte por byte. Quem encosta o selo à direita é o `margin-left: auto`
            no CSS, não um `<span>` a mais no markup de quem não usa o campo. */}
        <SeloKind kind={hit.kind} />
        <Procedencia hit={hit} />
      </div>
      {tabela ? (
        <TabelaOriginal html={tabela} />
      ) : (
        <p className="trecho-texto">{hit.excerpt}</p>
      )}
    </>
  );
}
