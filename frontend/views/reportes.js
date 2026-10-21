/* Vista Reportes.

   El informe deja de ser un panel pegado al documento: se pinta aqui a pantalla
   completa. Los datos salen del editor (app.report()), que es quien analiza; la
   vista no calcula nada por su cuenta salvo el filtro por gravedad, el filtro
   por categoria, la busqueda y la paginacion.
 */
import { Router } from "../core/router.js";
import { Dom } from "../core/dom.js";

const { esc, icon } = Dom;

// Se usan letras y no iconos: "!" para lo que rompe la norma y "i" para lo
// que solo conviene mirar.
const SEV_ICON = { error: "!", warning: "!", info: "i" };
const SEV_TEXT = { error: "Error", warning: "Aviso", info: "Observación" };

const POR_PAGINA = 10;

let root = null;
let app = null;
let filtro = "all";
let categoria = "";
let busqueda = "";
let pagina = 1;

function estado() {
  const st = app && typeof app.report === "function" ? app.report() : null;
  return st || { ready: false, findings: [], counts: { all: 0 }, hasFile: false };
}

function contar(list) {
  const c = { all: list.length, error: 0, warning: 0, info: 0 };
  list.forEach((f) => (c[f.severity] = (c[f.severity] || 0) + 1));
  return c;
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

function nivel(score) {
  if (score == null) return { txt: "Sin datos", clase: "none" };
  if (score >= 75) return { txt: "Alto", clase: "alto" };
  if (score >= 50) return { txt: "Medio", clase: "medio" };
  return { txt: "Bajo", clase: "bajo" };
}

/* Una tarjeta de conteo: icono circular, numero y etiqueta. */
function tarjeta(clase, icono, valor, texto) {
  return `<div class="rv-card ${clase}">
      <span class="rv-card-icn">${icono}</span>
      <div class="pc-num">${esc(valor)}</div>
      <div class="pc-label">${esc(texto)}</div>
    </div>`;
}

/* Buscar sin tildes: "sangria" debe encontrar "sangria" y "sangria". */
function sinTildes(texto) {
  return String(texto || "")
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase();
}

function coincide(f, texto) {
  if (!texto) return true;
  const t = sinTildes(texto);
  return (
    sinTildes(f.message).includes(t) ||
    sinTildes(f.category).includes(t) ||
    sinTildes(f.location).includes(t) ||
    sinTildes(f.rule_id).includes(t) ||
    sinTildes(f.suggestion).includes(t)
  );
}

function visibles(lista) {
  return lista.filter(
    (f) =>
      (filtro === "all" || f.severity === filtro) &&
      (!categoria || f.category === categoria) &&
      coincide(f, busqueda)
  );
}

/* Ventana de paginas: 1 2 3 4 5 ... 160 (con la actual resaltada). */
function listaPaginas(total, actual) {
  if (total <= 1) return [1];
  const out = [];
  const add = (n) => {
    if (n >= 1 && n <= total && out[out.length - 1] !== n) out.push(n);
  };
  add(1);
  const desde = Math.max(2, actual - 2);
  const hasta = Math.min(total - 1, actual + 2);
  if (desde > 2) out.push("...");
  for (let n = desde; n <= hasta; n++) add(n);
  if (hasta < total - 1) out.push("...");
  if (total > 1) add(total);
  return out;
}

function paginacion(total, actual) {
  if (total <= 1) return "";
  const botones = listaPaginas(total, actual)
    .map((p) =>
      p === "..."
        ? `<span class="rv-gap">…</span>`
        : `<button data-pag="${p}" class="${p === actual ? "active" : ""}">${p}</button>`
    )
    .join("");
  return `<div class="rv-pages">
      <button data-pag="${actual - 1}" class="rv-pg-arrow" ${actual <= 1 ? "disabled" : ""}
        aria-label="Pagina anterior">${icon("chevron")}</button>
      ${botones}
      <button data-pag="${actual + 1}" class="rv-pg-arrow next" ${actual >= total ? "disabled" : ""}
        aria-label="Pagina siguiente">${icon("chevron")}</button>
    </div>`;
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
  const pag = String(f.location || "").match(/[Pp][áa]g\.?\s*([\d]+)/);
  const chip = pag ? `Pág. ${esc(pag[1])}` : esc(f.location || "");
  return `<article class="finding ${esc(f.severity)}${esIa ? " ai" : ""}" data-i="${indice}">
      <div class="finding-rail">
        <span class="dot">${SEV_ICON[f.severity] || ""}</span>
        <span class="finding-sev">${SEV_TEXT[f.severity] || ""}</span>
      </div>
      <div class="finding-body">
        <div class="finding-head">
          <span class="finding-cat">${esc(f.category || "")}</span>
          ${badge}${conf}
          <span class="finding-rule">${esc(f.rule_id || "")}</span>
        </div>
        <p class="finding-msg">${esc(f.message || "")}</p>
        ${falta}
        ${f.excerpt ? `<p class="finding-excerpt">"${esc(f.excerpt)}"</p>` : ""}
        ${
          f.suggestion
            ? `<p class="finding-sug"><span class="icn">${icon("bulb")}</span><b>Sugerencia:</b> ${esc(f.suggestion)}</p>`
            : ""
        }
      </div>
      <div class="finding-side">${chip ? `<span class="finding-page">${chip}</span>` : ""}</div>
    </article>`;
}

function render() {
  const st = estado();
  const lista = st.findings || [];
  const cuentas = contar(lista);
  const score =
    st.summary && st.summary.compliance_score != null
      ? st.summary.compliance_score
      : null;
  const nivelTxt = nivel(score);

  const filtrada = visibles(lista);
  const totalPaginas = Math.max(1, Math.ceil(filtrada.length / POR_PAGINA));
  if (pagina > totalPaginas) pagina = totalPaginas;
  if (pagina < 1) pagina = 1;
  const desde = (pagina - 1) * POR_PAGINA;
  const enPagina = filtrada.slice(desde, desde + POR_PAGINA);

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

  // chips de categoria (se despliegan con el boton Filtros)
  const cats = contarCategorias(lista);
  const catChips = cats.length
    ? `<div class="rv-cats">
        <button data-cat="" class="${categoria ? "" : "active"}">Todas <b>${lista.length}</b></button>
        ${cats
          .map(
            ([c, n]) =>
              `<button data-cat="${esc(c)}" class="${categoria === c ? "active" : ""}">${esc(c)} <b>${n}</b></button>`
          )
          .join("")}
      </div>`
    : "";

  const cuerpo = !st.ready
    ? `<p class="empty-pane">Aún no se ha verificado el documento.</p>`
    : enPagina.length
      ? enPagina.map((f) => hallazgo(f, lista.indexOf(f))).join("")
      : `<p class="empty-pane">Sin hallazgos con estos filtros.</p>`;

  const pie = st.ready
    ? `<div class="rv-foot">
        <span class="rv-count">Mostrando ${filtrada.length ? desde + 1 : 0} de ${filtrada.length} hallazgos${
          filtrada.length !== lista.length ? ` (de ${lista.length})` : ""
        }</span>
        ${paginacion(totalPaginas, pagina)}
      </div>`
    : "";

  return `
    <div class="rv-view">
      <div class="rv-head">
        <span class="rv-head-icn">${icon("chart")}</span>
        <div>
          <h1>Reportes</h1>
          <p>Resumen del cumplimiento y el detalle de los hallazgos del documento.</p>
        </div>
        <button class="rv-back" data-act="volver">Volver al documento</button>
        <button class="pane-dl" data-act="descargar" ${st.hasFile ? "" : "disabled"}
          title="Descargar el informe APA en un documento Word (.docx)"
          aria-label="Descargar el informe APA en Word">${icon("download")}</button>
      </div>

      <div class="pane-body">
        <div class="rv-cards">
          <div class="rv-card rv-card-score">
            <div class="score-ring"><span>${score == null ? "--" : esc(score)}</span><small>%</small></div>
            <div class="rv-score-txt">
              <div class="rv-score-title">Nivel de cumplimiento</div>
              <span class="rv-level ${nivelTxt.clase}">${esc(nivelTxt.txt)}</span>
            </div>
          </div>
          ${tarjeta("error", "✕", cuentas.error || 0, "Errores")}
          ${tarjeta("warning", "!", cuentas.warning || 0, "Avisos")}
          ${tarjeta("info", "i", cuentas.info || 0, "Observaciones")}
          ${tarjeta("total", icon("clipboard"), cuentas.all || 0, "Total de hallazgos")}
        </div>

        <div class="rv-toolbar">
          <div class="pane-filters">${filtros}</div>
          <div class="rv-search-wrap">
            <span class="rv-search-icn">${icon("search")}</span>
            <input class="rv-search" type="search" placeholder="Buscar en los hallazgos..."
              value="${esc(busqueda)}" aria-label="Buscar en los hallazgos" />
          </div>
          <button class="rv-filters-btn ${categoria ? "active" : ""}" data-act="filtros"
            aria-expanded="${categoria ? "true" : "false"}">${icon("filter")}<span>Filtros</span></button>
        </div>

        ${catChips ? `<div class="rv-catbar" ${categoria ? "" : "hidden"}>${catChips}</div>` : ""}

        <div class="findings">${cuerpo}</div>
        ${pie}
      </div>
    </div>`;
}

function contarCategorias(lista) {
  const c = new Map();
  lista.forEach((f) => {
    const k = f.category || "Sin categoría";
    c.set(k, (c.get(k) || 0) + 1);
  });
  return Array.from(c.entries()).sort((a, b) => b[1] - a[1]);
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
      pagina = 1;
      pintar();
    })
  );

  el.querySelectorAll(".rv-cats [data-cat]").forEach((b) =>
    b.addEventListener("click", () => {
      categoria = b.dataset.cat || "";
      pagina = 1;
      pintar();
    })
  );

  el.querySelectorAll(".rv-pages [data-pag]").forEach((b) =>
    b.addEventListener("click", () => {
      const n = Number(b.dataset.pag);
      if (!n || n < 1) return;
      pagina = n;
      pintar();
      const vista = document.getElementById("view");
      if (vista) vista.scrollTop = 0;
    })
  );

  const busquedaEl = el.querySelector(".rv-search");
  if (busquedaEl) {
    busquedaEl.addEventListener("input", (e) => {
      busqueda = e.target.value;
      pagina = 1;
      pintar();
    });
  }

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
      else if (act === "filtros") {
        const barra = el.querySelector(".rv-catbar");
        if (barra) {
          const visible = barra.hasAttribute("hidden");
          if (visible) barra.removeAttribute("hidden");
          else barra.setAttribute("hidden", "");
          b.classList.toggle("active", visible);
          b.setAttribute("aria-expanded", visible ? "true" : "false");
        }
      }
    })
  );
}

// Repinta sin perder la posicion del scroll: el editor avisa de cada cambio.
function pintar() {
  if (!root) return;
  const vista = document.getElementById("view");
  const scroll = vista ? vista.scrollTop : 0;
  // al escribir en el buscador se repinta todo: se devuelve el foco al campo
  const activo = document.activeElement;
  const enBusqueda = activo && activo.classList && activo.classList.contains("rv-search");
  const pos = enBusqueda ? activo.selectionStart : null;
  root.innerHTML = render();
  Dom.hydrate(root);
  mount(root);
  if (enBusqueda) {
    const inp = root.querySelector(".rv-search");
    if (inp) {
      inp.focus();
      try {
        inp.setSelectionRange(pos, pos);
      } catch (e) {
        /* algunos navegadores no lo permiten con type=search */
      }
    }
  }
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
