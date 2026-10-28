/* Vista Reportes.

   El informe deja de ser un panel pegado al documento: se pinta aqui a pantalla
   completa. Los datos salen del editor (app.report()), que es quien analiza; la
   vista no calcula nada por su cuenta salvo el filtro por gravedad, el filtro
   por categoria, la busqueda y la paginacion.
*/
import { Router } from "../core/router.js";
import { Dom } from "../core/dom.js";

const { esc, icon } = Dom;

const SEV_TEXT = { error: "Error", warning: "Aviso", info: "Observación" };
const SEV_COLOR = { error: "#e53e3e", warning: "#d69e2e", info: "#3182ce" };
const SEV_ICON = { error: "error", warning: "alert", info: "info" };

const POR_PAGINA = 6;

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
        aria-label="Pagina anterior">&#10094;</button>
      ${botones}
      <button data-pag="${actual + 1}" class="rv-pg-arrow next" ${actual >= total ? "disabled" : ""}
        aria-label="Pagina siguiente">&#10095;</button>
    </div>`;
}

function sevChip(sev) {
  const color = SEV_COLOR[sev] || "#9aa5b1";
  const label = SEV_TEXT[sev] || sev;
  const svgName = SEV_ICON[sev] || "info";
  return `<span class="rv-sev-chip" style="--c:${color}">${icon(svgName)} ${esc(label)}</span>`;
}

function filaHallazgo(f, indice) {
  const sev = f.severity || "info";
  const color = SEV_COLOR[sev] || "#9aa5b1";
  const regla = esc(f.rule_id || "");
  const categoriaTexto = esc(f.category || "");
  const mensaje = esc(f.message || "");
  const excerpt = f.excerpt ? `<div class="rv-excerpt">"${esc(f.excerpt)}"</div>` : "";
  const sugerencia = f.suggestion
    ? `<div class="rv-sug"><span class="icn">${icon("bulb")}</span><b>Sugerencia:</b> ${esc(f.suggestion)}</div>`
    : "";
  const pag = String(f.location || "").match(/[Pp][áa]g\.?\s*([\d]+)/);
  const ubic = pag ? `Párrafo ${esc(pag[1])}` : esc(f.location || "");

  return `<tr class="rv-row rv-${sev}" data-i="${indice}">
      <td class="rv-tipo">
        ${sevChip(sev)}
      </td>
      <td class="rv-desc">
        <div class="rv-desc-titulo">${categoriaTexto} ${regla ? `<span class="rv-regla">${esc(regla)}</span>` : ""}</div>
        <div class="rv-desc-texto">${mensaje}</div>
        ${excerpt}
        ${sugerencia}
      </td>
      <td class="rv-ubi">
        <div class="rv-ubi-icono">${icon("mapPin")}</div>
        <div class="rv-ubi-texto">${ubic}</div>
      </td>
      <td class="rv-prio">
        <span class="rv-prio-chip rv-prio-${sev}">${SEV_TEXT[sev]}</span>
      </td>
      <td class="rv-acc">
        <button class="rv-iconbtn" data-act="ver" data-i="${indice}" title="Ver">${icon("eye")}</button>
        <button class="rv-iconbtn rv-more" data-act="mas" data-i="${indice}" title="Mas opciones">${icon("more")}</button>
        <div class="rv-more-pop" id="rv-pop-${indice}" hidden>
          <button class="rv-pop-item" data-act="corregir" data-i="${indice}">${icon("fix")} Corregir</button>
          <button class="rv-pop-item" data-act="descartar" data-i="${indice}">${icon("xCircle")} Descartar</button>
        </div>
      </td>
    </tr>`;
}

function nivel(score) {
  if (score == null) return { txt: "Sin datos", clase: "none" };
  if (score >= 75) return { txt: "Alto", clase: "alto" };
  if (score >= 50) return { txt: "Medio", clase: "medio" };
  return { txt: "Bajo", clase: "bajo" };
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

function tarjeta(clase, icono, valor, texto, subtexto) {
  return `<div class="rv-card ${clase}">
      <span class="rv-card-icn">${icono}</span>
      <div class="rv-card-info">
        <div class="rv-card-num">${esc(valor)}</div>
        <div class="rv-card-label">${esc(texto)}</div>
        ${subtexto ? `<div class="rv-card-sub">${esc(subtexto)}</div>` : ""}
      </div>
    </div>`;
}

function render() {
  const st = estado();
  const lista = st.findings || [];
  const cuentas = contar(lista);
  const score =
    st.summary && st.summary.compliance_score != null
      ? st.summary.compliance_score
      : null;

  const filtrada = visibles(lista);
  const totalPaginas = Math.max(1, Math.ceil(filtrada.length / POR_PAGINA));
  if (pagina > totalPaginas) pagina = totalPaginas;
  if (pagina < 1) pagina = 1;
  const desde = (pagina - 1) * POR_PAGINA;
  const enPagina = filtrada.slice(desde, desde + POR_PAGINA);

  // Chips de estado (como la imagen de referencia)
  const chips = [
    ["all", "Todos", cuentas.all || 0, "var(--accent)"],
    ["error", "Errores", cuentas.error || 0, "var(--error)"],
    ["warning", "Avisos", cuentas.warning || 0, "var(--warning)"],
    ["info", "Observaciones", cuentas.info || 0, "var(--info)"],
  ]
    .map(
      ([k, texto, n, col]) =>
        `<button data-filter="${k}" class="rv-chip ${filtro === k ? "active" : ""}" style="--c:${col}">
          ${texto} <b>${n}</b>
        </button>`
    )
    .join("");

  const cuerpo = !st.ready
    ? `<tr><td colspan="5" class="rv-vacio">Aun no se ha verificado el documento.</td></tr>`
    : enPagina.length
      ? enPagina.map((f) => filaHallazgo(f, lista.indexOf(f))).join("")
      : `<tr><td colspan="5" class="rv-vacio">Sin hallazgos con estos filtros.</td></tr>`;

  const inicioRango = filtrada.length ? desde + 1 : 0;
  const finRango = Math.min(desde + POR_PAGINA, filtrada.length);

  const pie = st.ready
    ? `<div class="rv-foot">
        <span class="rv-count">Mostrando ${inicioRango} - ${finRango} de ${filtrada.length} hallazgos${
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
          <p>Revise los hallazgos, el porcentaje de cumplimiento y el detalle de cada correccion.</p>
        </div>
        <div class="rv-head-search">
          <span class="rv-search-icn">${icon("search")}</span>
          <input class="rv-search-header" type="search" placeholder="Buscar tesis, autor o codigo..."
            value="${esc(busqueda)}" aria-label="Buscar tesis, autor o codigo">
        </div>
        <div class="rv-head-actions">
          <span class="rv-notif">${icon("bell")}</span>
          <div class="rv-user">
            <span class="rv-user-icn">${icon("docs")}</span>
            <div>
              <div class="rv-user-name">Josi Maza</div>
              <div class="rv-user-email">josimaza21@gmail.com</div>
            </div>
            <span class="rv-user-arrow">&#9660;</span>
          </div>
        </div>
      </div>

      <!-- Tarjetas de estadisticas -->
      <div class="rv-cards">
        ${tarjeta("rv-card-score",
          `<div class="score-ring"><span>${score == null ? "--" : esc(score)}</span><small>%</small></div>`,
          esc(score == null ? "--" : score),
          "Nivel de cumplimiento APA",
          score == null ? "Su documento tiene un bajo avance." : `Su documento tiene un ${nivel(score).txt.toLowerCase()} avance.`
        )}
        ${tarjeta("rv-card-error",
          `<span class="rv-sev-chip rv-sev-error">${icon("error")} Error</span>`,
          cuentas.error || 0,
          "Errores",
          "Requieren correccion"
        )}
        ${tarjeta("rv-card-warning",
          `<span class="rv-sev-chip rv-sev-warning">${icon("alert")} Aviso</span>`,
          cuentas.warning || 0,
          "Avisos",
          "Revisar y validar"
        )}
        ${tarjeta("rv-card-info",
          `<span class="rv-sev-chip rv-sev-info">${icon("info")} Observacion</span>`,
          cuentas.info || 0,
          "Observaciones",
          "Informacion adicional"
        )}
        ${tarjeta("rv-card-total",
          icon("clipboard"),
          cuentas.all || 0,
          "Total de hallazgos",
          "En todo el documento"
        )}
      </div>

      <!-- Chips de filtro + descargar -->
      <div class="rv-filtros-bar">
        <div class="rv-header-chips">${chips}</div>
        <button class="pane-dl" data-act="descargar" ${st.hasFile ? "" : "disabled"}
          title="Descargar el informe APA en un documento Word (.docx)"
          aria-label="Descargar el informe APA en Word">${icon("download")} Descargar informe</button>
      </div>

      <!-- Barra de filtros -->
      <div class="rv-toolbar">
        <div class="rv-search-wrap">
          <span class="rv-search-icn">${icon("search")}</span>
          <input class="rv-search" type="search" placeholder="Buscar por regla, texto o referencia..."
            value="${esc(busqueda)}" aria-label="Buscar en los hallazgos" />
        </div>
        <div class="rv-select-wrap">
          <label class="rv-select-lbl">Tipo de hallazgo</label>
          <select id="rv-tipo" aria-label="Tipo de hallazgo">
            <option value="">Todos</option>
            <option value="error">Error</option>
            <option value="warning">Aviso</option>
            <option value="info">Observacion</option>
          </select>
        </div>
        <div class="rv-select-wrap">
          <label class="rv-select-lbl">Prioridad</label>
          <select id="rv-prioridad" aria-label="Prioridad">
            <option value="">Todas</option>
            <option value="error">Alta</option>
            <option value="warning">Media</option>
            <option value="info">Baja</option>
          </select>
        </div>
        <button class="rv-btn-limpiar" data-act="limpiar">${icon("xCircle")} Limpiar filtros</button>
      </div>

      <!-- Tabla CRUD -->
      <div class="rv-tablewrap">
        <table class="rv-table">
          <thead>
            <tr>
              <th scope="col">Tipo</th>
              <th scope="col">Descripcion del hallazgo</th>
              <th scope="col">Ubicacion</th>
              <th scope="col">Prioridad</th>
              <th scope="col" class="rv-acc-col">Acciones</th>
            </tr>
          </thead>
          <tbody id="rv-body">${cuerpo}</tbody>
        </table>
      </div>
      ${pie}
    </div>`;
}

function mount(el) {
  root = el;

  // Chips de severidad del header
  el.querySelectorAll(".rv-chip[data-filter]").forEach((b) =>
    b.addEventListener("click", () => {
      filtro = b.dataset.filter;
      pagina = 1;
      pintar();
    })
  );

  // Buscador
  const busquedaEl = el.querySelector(".rv-search");
  if (busquedaEl) {
    busquedaEl.addEventListener("input", (e) => {
      busqueda = e.target.value;
      pagina = 1;
      pintar();
    });
  }

  // Filtro tipo de hallazgo
  const tipoEl = el.querySelector("#rv-tipo");
  if (tipoEl) {
    tipoEl.addEventListener("change", (e) => {
      filtro = e.target.value || "all";
      pagina = 1;
      pintar();
    });
  }

  // Filtro prioridad (mapea a severidad)
  const prioEl = el.querySelector("#rv-prioridad");
  if (prioEl) {
    prioEl.addEventListener("change", (e) => {
      const v = e.target.value;
      filtro = v || "all";
      pagina = 1;
      pintar();
    });
  }

  // Limpiar filtros
  el.querySelectorAll("[data-act=limpiar]").forEach((b) =>
    b.addEventListener("click", () => {
      filtro = "all";
      busqueda = "";
      const inp = el.querySelector(".rv-search");
      if (inp) inp.value = "";
      const t = el.querySelector("#rv-tipo");
      if (t) t.value = "";
      const p = el.querySelector("#rv-prioridad");
      if (p) p.value = "";
      pagina = 1;
      pintar();
    })
  );

  // Paginacion
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

  // Acciones de filas: ver / mas
  el.querySelectorAll(".rv-iconbtn[data-act]").forEach((b) =>
    b.addEventListener("click", (e) => {
      e.stopPropagation();
      const i = Number(b.dataset.i);
      const lista = estado().findings || [];
      const f = lista[i];
      if (!f) return;
      if (b.dataset.act === "ver") {
        if (app && app.jumpToFinding) app.jumpToFinding(f);
      } else if (b.dataset.act === "mas") {
        const pop = el.querySelector(`#rv-pop-${i}`);
        document.querySelectorAll(".rv-more-pop").forEach((m) => m.hidden = true);
        if (pop) pop.hidden = !pop.hidden;
      }
    })
  );

  // Items del menu mas
  el.querySelectorAll(".rv-pop-item[data-act]").forEach((b) =>
    b.addEventListener("click", (e) => {
      e.stopPropagation();
      const i = Number(b.dataset.i);
      const lista = estado().findings || [];
      const f = lista[i];
      if (!f) return;
      if (b.dataset.act === "corregir") {
        if (app && app.openFixModal) app.openFixModal();
      } else if (b.dataset.act === "descartar") {
        if (app && app.toast) app.toast("Hallazgo descartado", "ok");
        document.getElementById(`rv-pop-${i}`).hidden = true;
      }
    })
  );

  // Cerrar pop al hacer click fuera
  document.addEventListener("click", () => {
    document.querySelectorAll(".rv-more-pop").forEach((m) => m.hidden = true);
  });

  // Acciones globales
  el.querySelectorAll("[data-act]").forEach((b) => {
    if (b.closest(".rv-iconbtn, .rv-pop-item")) return;
    b.addEventListener("click", () => {
      const act = b.dataset.act;
      if (act === "volver") Router.go("correcciones");
      else if (act === "descargar" && app && app.downloadReport) app.downloadReport();
    });
  });
}

function pintar() {
  if (!root) return;
  const vista = document.getElementById("view");
  const scroll = vista ? vista.scrollTop : 0;
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
