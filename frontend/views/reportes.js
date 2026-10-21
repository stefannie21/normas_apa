/* Vista Reportes.

   El informe deja de ser un panel pegado al documento: se pinta aqui a pantalla
   completa. Los datos salen del editor (app.report()), que es quien analiza; la
   vista no calcula nada por su cuenta salvo el filtro por gravedad.
  */
import { Router } from "../core/router.js";
import { Dom } from "../core/dom.js";

const { esc, icon } = Dom;

// Se usan letras y no iconos: "!" para lo que rompe la norma y "i" para lo
// que solo conviene mirar.
const SEV_ICON = { error: "!", warning: "!", info: "i" };

let root = null;
let app = null;
let filtro = "all";

function estado() {
  const st = app && typeof app.report === "function" ? app.report() : null;
  return st || { ready: false, findings: [], counts: { all: 0 }, hasFile: false };
}

function contar(list) {
  const c = { all: list.length, error: 0, warning: 0, info: 0 };
  list.forEach((f) => (c[f.severity] = (c[f.severity] || 0) + 1));
  return c;
}

function tarjeta(valor, texto, clase) {
  return `<div class="pane-card ${clase || ""}">
      <div class="pc-num">${esc(valor)}</div>
      <div class="pc-label">${esc(texto)}</div>
    </div>`;
}

/* El anillo avanza segun el cumplimiento. El valor viaja como variable CSS
   para no repintar bordes desde JS. */
function pintarAnillo(score) {
  const ring = document.querySelector(".score-ring");
  if (!ring) return;
  const pct = score == null ? 0 : Math.max(0, Math.min(100, Number(score) || 0));
  ring.style.setProperty("--pct", String(pct));
  const color =
    score == null
      ? "var(--accent-soft)"
      : pct < 50
        ? "var(--error)"
        : pct < 75
          ? "var(--warning)"
          : "var(--accent)";
  ring.style.setProperty("--ring-color", color);
}

function hallazgo(f, indice) {
  const extra = f.extra || {};
  const esIa = String(f.rule_id || "").startsWith("AI-");
  const badge = esIa
    ? `<span class="ai-badge" title="Sugerencia de la IA: no se aplica automaticamente">IA</span>`
    : "";
  const conf =
    esIa && extra.ai_confidence != null
      ? `<span class="ai-conf">confianza ${Math.round(extra.ai_confidence * 100)}%</span>`
      : "";
  const falta =
    esIa && extra.ai_missing && extra.ai_missing.length
      ? `<p class="finding-missing">Falta: ${esc(extra.ai_missing.join(" · "))}</p>`
      : "";
  return `<article class="finding ${esc(f.severity)}${esIa ? " ai" : ""}" data-i="${indice}">
      <div class="finding-head">
        <span class="dot">${SEV_ICON[f.severity] || ""}</span>
        <span class="finding-cat">${esc(f.category || "")}</span>
        ${badge}${conf}
        <span class="finding-rule">${esc(f.rule_id || "")}</span>
      </div>
      <p class="finding-msg">${esc(f.message || "")}</p>
      ${falta}
      ${f.excerpt ? `<p class="finding-excerpt">"${esc(f.excerpt)}"</p>` : ""}
      ${f.suggestion ? `<p class="finding-sug">Sugerencia: ${esc(f.suggestion)}</p>` : ""}
      <p class="finding-loc">${esc(f.location || "")}</p>
    </article>`;
}

function render() {
  const st = estado();
  const lista = st.findings || [];
  const cuentas = contar(lista);
  const score = st.summary && st.summary.compliance_score != null
    ? st.summary.compliance_score
    : null;

  const visibles = lista.filter((f) => filtro === "all" || f.severity === filtro);

  const filtros = [
    ["all", "Todos"],
    ["error", "Errores"],
    ["warning", "Avisos"],
    ["info", "Observ."],
  ]
    .map(
      ([k, texto]) =>
        `<button data-filter="${k}" class="${filtro === k ? "active" : ""}">${texto} <b>${cuentas[k] || 0}</b></button>`
    )
    .join("");

  const cuerpo = !st.ready
    ? `<p class="empty-pane">Aún no se ha verificado el documento.</p>`
    : visibles.length
      ? visibles
          .map((f) => hallazgo(f, lista.indexOf(f)))
          .join("")
      : `<p class="empty-pane">Sin hallazgos en esta categoría.</p>`;

  return `
    <div class="rv-view">
      <div class="rv-head">
        <span class="rv-head-icn">${icon("chart")}</span>
        <div>
          <h1>Reportes</h1>
          <p>Resumen del cumplimiento y el detalle de los hallazgos del documento.</p>
        </div>
        <button class="rv-back" data-act="volver">Volver a Corrección</button>
        <button class="pane-dl" data-act="descargar" ${st.hasFile ? "" : "disabled"}
          title="Descargar el informe APA en un documento Word (.docx)"
          aria-label="Descargar el informe APA en Word">${icon("download")}</button>
      </div>

      <div class="pane-body">
        <div class="score">
          <div class="score-ring"><span>${score == null ? "--" : esc(score)}</span><small>%</small></div>
          <div class="score-label">Nivel de cumplimiento</div>
        </div>
        <div class="pane-cards">
          ${tarjeta(cuentas.error || 0, "Errores", "error")}
          ${tarjeta(cuentas.warning || 0, "Avisos", "warning")}
          ${tarjeta(cuentas.info || 0, "Observ.", "info")}
          ${tarjeta(cuentas.all || 0, "Total")}
        </div>
        <div class="pane-filters">${filtros}</div>
        <div class="findings">${cuerpo}</div>
      </div>
    </div>`;
}

function mount(el) {
  root = el;
  pintarAnillo(
    (estado().summary && estado().summary.compliance_score) != null
      ? estado().summary.compliance_score
      : null
  );

  el.querySelectorAll(".pane-filters [data-filter]").forEach((b) =>
    b.addEventListener("click", () => {
      filtro = b.dataset.filter;
      pintar();
    })
  );

  el.querySelectorAll(".findings .finding").forEach((art) =>
    art.addEventListener("click", () => {
      const lista = estado().findings || [];
      if (app && app.jumpToFinding) app.jumpToFinding(lista[Number(art.dataset.i)]);
    })
  );

  el.querySelectorAll("[data-act]").forEach((b) =>
    b.addEventListener("click", () => {
      const act = b.dataset.act;
      if (act === "volver") Router.go("correcciones");
      else if (act === "descargar" && app && app.downloadReport) app.downloadReport();
    })
  );
}

// Repinta sin perder la posicion del scroll: el editor avisa de cada cambio.
function pintar() {
  if (!root) return;
  const vista = document.getElementById("view");
  const scroll = vista ? vista.scrollTop : 0;
  root.innerHTML = render();
  Dom.hydrate(root);
  mount(root);
  if (vista) vista.scrollTop = scroll;
}

function refresh() {
  pintar();
}

Router.register("reportes", {
  title: "Reportes",
  icon: "chart",
  order: 40,
  render,
  mount,
  refresh,
  setup(api) {
    app = api;
  },
});
