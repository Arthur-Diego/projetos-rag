import DOMPurify from "dompurify";

/**
 * Sanitização do HTML de documento que chega no `content_html` (contrato 1.3.0).
 *
 * **Este é o único caminho pelo qual HTML entra no DOM deste cliente.** O
 * `content_html` é a tabela ORIGINAL extraída de um PDF de terceiro: nada
 * garante que o extrator não tenha carregado junto um `<script>` ou um
 * `onerror=`. Renderizar cru seria XSS com passo a passo publicado no contrato.
 *
 * A lista é de PERMISSÃO, não de bloqueio. Bloqueio exige prever o ataque;
 * permissão exige prever o conteúdo, e aqui o conteúdo é conhecido e pequeno:
 * uma tabela. `style`, `href`, `src` e todo `on*` ficam de fora por não estarem
 * na lista, não por terem sido lembrados um a um.
 */
const TAGS_PERMITIDAS = [
  "table",
  "thead",
  "tbody",
  "tfoot",
  "caption",
  "colgroup",
  "col",
  "tr",
  "th",
  "td",
  "p",
  "br",
  "span",
  "b",
  "i",
  "strong",
  "em",
  "sup",
  "sub",
];

const ATRIBUTOS_PERMITIDOS = ["colspan", "rowspan", "scope", "headers", "abbr"];

/**
 * Duas exceções do DOMPurify que `ALLOWED_ATTR` NÃO cobre e precisam de
 * decisão explícita: `data-*` e `aria-*` passam por padrão mesmo com a lista
 * definida. `data-*` fica bloqueado — é canal de contrabando sem função numa
 * tabela. `aria-*` fica permitido, deliberadamente: atributos de acessibilidade
 * não executam nada e uma tabela extraída pode carregá-los legitimamente.
 */
const EXCECOES = { ALLOW_DATA_ATTR: false, ALLOW_ARIA_ATTR: true };

/**
 * Devolve o HTML seguro para `dangerouslySetInnerHTML`, ou `""`.
 *
 * Falha FECHADO: sem DOM (render no servidor, teste sem jsdom) o DOMPurify
 * devolveria a entrada intacta, e um sanitizador que devolve o que recebeu é
 * pior que nenhum — dá a impressão de proteção. Aqui isso vira string vazia, e
 * quem chama degrada para o excerpt como texto.
 */
export function sanitizaHtml(html) {
  if (typeof html !== "string" || html === "") return "";
  if (!DOMPurify.isSupported) return "";
  return DOMPurify.sanitize(html, {
    ALLOWED_TAGS: TAGS_PERMITIDAS,
    ALLOWED_ATTR: ATRIBUTOS_PERMITIDOS,
    ...EXCECOES,
  });
}
