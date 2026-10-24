/* Vista Mis Tesis.

   La biblioteca de documentos. Los datos y el guardado viven en library.js
   (IndexedDB); aqui solo se pinta la tabla, el resumen y las acciones.
  */
import { Router } from "../core/router.js";
import { Dom } from "../core/dom.js";
import { Icons } from "../ui/icons.js";
import { Library } from "../library.js";

const { esc, icon } = Dom;

let root = null;
let app = null;
let rows = [];
let tabActual = "";

function filtradas() {
  const q = (document.getElementById("tv-q").value || "").trim().toLowerCase();
  const estado = document.getElementById("tv-estado").value;
  const orden = document.getElementById("tv-orden").value;

  let out = rows.slice();
  if (tabActual) out = out.filter((r) => r.status === tabActual);
  if (estado) out = out.filter((r) => r.status === estado);
  if (q) out = out.filter((r) => Library.searchText(r).includes(q));

  const porFecha = (a, b) => String(b.addedAt || "").localeCompare(String(a.addedAt || ""));
  if (orden === "antiguos") out.reverse();
  else if (orden === "titulo") out.sort((a, b) => a.title.localeCompare(b.title));
  else if (orden === "cumplimiento")
    out.sort((a, b) => (b.score == null ? -1 : b.score) - (a.score == null ? -1 : a.score));
  else out.sort(porFecha);
  return out;
}

function cuentas() {
  const c = { completada: 0, proceso: 0, pendiente: 0 };
  rows.forEach((r) => {
    if (c[r.status] != null) c[r.status]++;
  });
  return c;
}

function tabsHtml() {
  const c = cuentas();
  return [
    ["", "Todas"],
    ["proceso", "En proceso"],
    ["completada", "Completadas"],
    ["pendiente", "Pendientes"],
  ]
    .map(([valor, texto]) => {
      const n = valor ? c[valor] : rows.length;
      return `<button class="tv-tab${tabActual === valor ? " active" : ""}" data-tv-tab="${valor}">${texto} <b>${n}</b></button>`;
    })
    .join("");
}

function leyendaHtml() {
  const c = cuentas();
  return ["completada", "proceso", "pendiente"]
    .map(
      (k) =>
        `<li><span class="dot" style="background:${Library.COLOR[k]}"></span>${Library.LABEL[k]} <b>${c[k]}</b></li>`
    )
    .join("");
}

function render() {
  return `
    <div class="tesis-view">
      <div class="tv-head">
        <span class="tv-head-icn">${icon("docs")}</span>
        <div>
          <h1>Mis tesis</h1>
          <p>Aquí puedes ver todas tus tesis, su estado y el progreso de corrección.</p>
        </div>
        <button class="tv-new" data-act="new"><span class="tv-new-plus">+</span> Nueva tesis</button>
      </div>

      <div class="tv-grid">
        <div class="tv-main">
          <div class="tv-tabs" id="tv-tabs">${tabsHtml()}</div>
          <div class="tv-toolbar">
            <div class="tv-search">
              ${icon("search")}
              <input type="search" id="tv-q" placeholder="Buscar por título, autor o código..." aria-label="Buscar tesis">
            </div>
            <label class="tv-select">
              <span>Estado</span>
              <select id="tv-estado" aria-label="Filtrar por estado">
                <option value="">Todos</option>
                <option value="completada">Completada</option>
                <option value="proceso">En proceso</option>
                <option value="pendiente">Pendiente</option>
              </select>
            </label>
            <label class="tv-select">
              <span>Fecha</span>
              <select id="tv-orden" aria-label="Ordenar por">
                <option value="recientes">Más recientes</option>
                <option value="antiguos">Más antiguas</option>
                <option value="titulo">Título (A-Z)</option>
                <option value="cumplimiento">Cumplimiento</option>
              </select>
            </label>
          </div>

          <div class="tv-tablewrap">
            <table class="tv-table">
              <thead>
                <tr>
                  <th scope="col">Título de la tesis</th>
                  <th scope="col">Autor</th>
                  <th scope="col">Fecha de subida</th>
                  <th scope="col">Estado</th>
                  <th scope="col" class="tv-acc-col">Acciones</th>
                </tr>
              </thead>
              <tbody id="tv-body"></tbody>
            </table>
            <div class="tv-empty" id="tv-empty" hidden></div>
          </div>

          <div class="tv-foot"><span id="tv-count">Mostrando 0 de 0 tesis</span></div>
        </div>

        <aside class="tv-side">
          <div class="tv-card">
            <div class="tv-card-head">
              <span class="tv-card-icn">${icon("chart")}</span>
              <div>
                <h2>Resumen de tus tesis</h2>
                <p>Estado general de tus trabajos</p>
              </div>
            </div>
            <div class="tv-donut-wrap">
              <div class="tv-donut" id="tv-donut">
                <div class="tv-donut-hole"><strong id="tv-total">0</strong><span>Total</span></div>
              </div>
              <ul class="tv-legend" id="tv-legend">${leyendaHtml()}</ul>
            </div>
          </div>
        </aside>
      </div>
    </div>`;
}

/* ---------- Pintado de la tabla y el resumen ---------- */
function pintarTabla() {
  const body = document.getElementById("tv-body");
  if (!body) return;
  const list = filtradas();

  body.innerHTML = list
    .map((r) => {
      const ext = Library.extClass(r.name);
      const score = r.score == null ? "" : `<span class="tv-score">${esc(r.score)}%</span> `;
      return `<tr data-id="${esc(r.id)}">
        <td><span class="tv-file">
          <span class="tv-file-icn ${ext}">${Icons.svg("docs", 19)}</span>
          <span class="tv-file-txt">
            <span class="tv-file-titulo" title="${esc(r.title)}">${esc(r.title)}</span>
            <span class="tv-file-sub">${esc(r.name)} · ${esc(Library.humanSize(r.size))}</span>
          </span>
        </span></td>
        <td>${esc(r.author || "—")}</td>
        <td>${esc(Library.stamp(r.addedAt))}</td>
        <td><span class="tv-pill ${esc(r.status)}">${esc(Library.LABEL[r.status])}</span>${score}</td>
        <td class="tv-row-acc">
          <button data-tv-row="open" title="Abrir esta tesis">${Icons.svg("eye", 16)}</button>
          <button data-tv-row="download" title="Descargar el archivo original">${Icons.svg("save", 16)}</button>
          <button class="danger" data-tv-row="delete" title="Eliminar de la biblioteca">${Icons.svg("trash", 16)}</button>
        </td>
      </tr>`;
    })
    .join("");

  const vacio = document.getElementById("tv-empty");
  const hay = list.length > 0;
  body.parentElement.hidden = !hay;
  vacio.hidden = hay;
  if (!hay) {
    vacio.innerHTML = rows.length
      ? "Ninguna tesis coincide con el filtro."
      : "Todavía no hay tesis. Pulsa <b>+ Nueva tesis</b> para subir la primera.";
  }
  const contador = document.getElementById("tv-count");
  if (contador) contador.textContent = "Mostrando " + list.length + " de " + rows.length + " tesis";

  // resumen y pestanas: el marco se pinto antes de que llegaran los datos
  const tabsEl = document.getElementById("tv-tabs");
  if (tabsEl) tabsEl.innerHTML = tabsHtml();
  const leyendaEl = document.getElementById("tv-legend");
  if (leyendaEl) leyendaEl.innerHTML = leyendaHtml();

  const c = cuentas();
  const total = document.getElementById("tv-total");
  if (total) total.textContent = String(rows.length);
  const donut = document.getElementById("tv-donut");
  if (donut) {
    const partes = [];
    let acum = 0;
    ["completada", "proceso", "pendiente"].forEach((k) => {
      if (!c[k]) return;
      const desde = acum;
      acum += (c[k] / Math.max(rows.length, 1)) * 100;
      partes.push(Library.COLOR[k] + " " + desde.toFixed(2) + "% " + acum.toFixed(2) + "%");
    });
    donut.style.background = partes.length
      ? "conic-gradient(" + partes.join(",") + ")"
      : "conic-gradient(#e3e7ed 0 100%)";
  }
}

async function cargar() {
  rows = await Library.list();
  pintarTabla();
}

/* ---------- Eventos ---------- */
function mount(el) {
  root = el;

  const tabs = el.querySelector(".tv-tabs");
  if (tabs) {
    tabs.addEventListener("click", (e) => {
      const b = e.target.closest("[data-tv-tab]");
      if (!b) return;
      tabActual = b.dataset.tvTab || "";
      pintarTodo();
    });
  }

  ["tv-q", "tv-estado", "tv-orden"].forEach((id) => {
    const campo = document.getElementById(id);
    if (!campo) return;
    campo.addEventListener(campo.tagName === "INPUT" ? "input" : "change", pintarTabla);
  });

  const body = document.getElementById("tv-body");
  if (body) {
    body.addEventListener("click", async (e) => {
      const btn = e.target.closest("[data-tv-row]");
      if (!btn) return;
      const id = btn.closest("tr").dataset.id;
      const rec = rows.find((r) => r.id === id);
      if (!rec) return;

      if (btn.dataset.tvRow === "open") {
        if (!rec.blob) return;
        if (app && app.openFile) app.openFile(new File([rec.blob], rec.name));
        Router.go("correcciones");
      } else if (btn.dataset.tvRow === "download") {
        if (!rec.blob) return;
        const url = URL.createObjectURL(rec.blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = rec.name;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        setTimeout(() => URL.revokeObjectURL(url), 2000);
      } else if (btn.dataset.tvRow === "delete") {
        await Library.remove(id);
        await cargar();
        if (app && app.toast) app.toast("Tesis eliminada de la biblioteca", "ok");
      }
    });
  }

  el.querySelectorAll("[data-act]").forEach((b) =>
    b.addEventListener("click", () => {
      const act = b.dataset.act;
      if (act === "new") {
        if (app && app.pickFile) app.pickFile();
      } else if (act === "correccion") {
        Router.go("correcciones");
        if (app && app.openFixModal) app.openFixModal();
      } else if (act === "ia") {
        Router.go("correcciones");
        if (app && app.runAiReview) app.runAiReview();
      } else if (act === "plantillas") {
        if (app && app.toast) app.toast("Las plantillas llegan en la próxima versión.", "info");
      }
    })
  );

  // la tabla y el resumen se llenan cuando llega la biblioteca (IndexedDB es
  // asincrono, asi que el marco se pinta antes que los datos)
  cargar();
}

// Repinta conservando el scroll de la vista.
function pintarTodo() {
  if (!root) return;
  const vista = document.getElementById("view");
  const scroll = vista ? vista.scrollTop : 0;
  const foco = document.activeElement;
  const idFoco = foco && foco.id ? foco.id : "";
  const posFoco = foco && foco.selectionStart != null ? foco.selectionStart : null;

  root.innerHTML = render();
  Dom.hydrate(root);
  mount(root);
  pintarTabla();

  if (vista) vista.scrollTop = scroll;
  if (idFoco) {
    const campo = document.getElementById(idFoco);
    if (campo) {
      campo.focus();
      if (posFoco != null && campo.setSelectionRange) {
        try {
          campo.setSelectionRange(posFoco, posFoco);
        } catch (err) {
          /* algunos tipos de input no lo permiten */
        }
      }
    }
  }
}

async function refresh() {
  if (!root) return;
  // se recarga la lista porque el editor pudo abrir o analizar una tesis
  const previo = rows;
  await cargar();
  const nuevo = cuentas();
  const viejo = (() => {
    const c = { completada: 0, proceso: 0, pendiente: 0 };
    previo.forEach((r) => {
      if (c[r.status] != null) c[r.status]++;
    });
    return c;
  })();
  // solo se repinta entero si cambian los totales: si no, el buscador perderia
  // el foco en cada pulsacion
  if (
    previo.length !== rows.length ||
    nuevo.completada !== viejo.completada ||
    nuevo.proceso !== viejo.proceso ||
    nuevo.pendiente !== viejo.pendiente
  ) {
    pintarTodo();
  } else {
    pintarTabla();
  }
}

Router.register("tesis", {
  title: "Mis tesis",
  icon: "files",
  order: 20,
  render,
  mount,
  refresh,
  setup(api) {
    app = api;
  },
});
