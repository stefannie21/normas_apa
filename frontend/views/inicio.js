/* Vista Inicio: panel de situación.

Nada de lo que se muestra es inventado: todo sale del estado real del
documento abierto y del último análisis.
  */
import { Router } from "../core/router.js";
import { Dom } from "../core/dom.js";
import { Library } from "../library.js";

(function () {
    "use strict";

    const { esc, icon } = Dom;

  let root = null;
  let app = null;
  // ultimos documentos de la biblioteca, ya ordenados y recortados a tres
  let recientes = [];
  let filtroBuscar = "";
  let filtroEstado = "";

  function s() {
    return app && typeof app.state === "function" ? app.state() : {};
  }

  /* ---------- Lista de "Recién abiertos" ---------- */

  // La misma fila sirve para el documento abierto y para los de la biblioteca:
  // icono, nombre, linea de datos y pildora de estado.
  function filaDoc(r, st) {
    const abierta = !!(st && st.name && st.name === r.name);
    const meta = [];
    if (abierta) {
      meta.push("Abierta");
      if (st.pages) meta.push(st.pages === 1 ? "1 página" : st.pages + " páginas");
      if (st.words) meta.push(st.words === 1 ? "1 palabra" : st.words.toLocaleString("es") + " palabras");
      if (st.dirty) meta.push("cambios sin guardar");
    }
    if (r.analyzedAt) meta.push("Revisada el " + Library.stamp(r.analyzedAt));
    else if (r.score == null) meta.push("Sin revisar");
    if (r.score != null) meta.push(r.score + " %");

    const estado = Library.LABEL[r.status] ? r.status : "pendiente";
    return `<li class="rec${abierta ? " actual" : ""}" data-rec="${esc(r.id || "")}"
                tabindex="0" role="button" title="Abrir este documento">
        <span class="doc-icn">${icon("docs")}</span>
        <span class="doc-body">
          <span class="doc-name">${esc(r.title || r.name)}</span>
          <span class="doc-meta">${esc(meta.join(" · "))}</span>
        </span>
        <span class="tv-pill ${estado}">${esc(Library.LABEL[estado])}</span>
      </li>`;
  }

  // Primer pintado, antes de que IndexedDB conteste: se usa el estado del
  // documento abierto para no dejar la tarjeta vacia ni un "cargando".
  function filaDelEstado(st, c) {
    return filaDoc(
      {
        id: "",
        name: st.name,
        title: st.name,
        addedAt: st.savedAt,
        analyzedAt: null,
        score: st.score,
        status: st.score == null ? "pendiente" : c.error ? "proceso" : "completada",
      },
      st
    );
  }

  function render() {
    const st = s();
    const c = st.counts || {};
    const conDoc = !!st.name;
    const analizado = st.score != null;

    // sin documento no se inventan ceros: se muestra "—", que significa
    // "todavia no hay nada que medir"
    const val = (x) => (conDoc ? x : "—");
    const error = conDoc ? (analizado ? c.error || 0 : "—") : "—";
    const avisa = conDoc ? (analizado ? c.warning || 0 : "—") : "—";
    const total = conDoc ? (analizado ? c.all || 0 : "—") : "—";

    // sin dato no hay nada que ver: el enlace se oculta en vez de llevar a una
    // pantalla vacia
    const stat = (tone, ico, num, label, enlace) => {
      let extra = "";
      if (label === "Cumplimiento" && conDoc && analizado) {
        const pct = Math.max(0, Math.min(100, Number(st.score) || 0));
        extra = `<div class="stat-bar"><div class="stat-bar-fill" style="width:${pct}%"></div></div>`;
      }
      return `
      <div class="stat ${tone}${num === "—" ? " vacio" : ""}">
        <span class="stat-icn">${icon(ico)}</span>
        <span class="stat-num">${esc(num)}</span>
        <span class="stat-label">${esc(label)}</span>
        ${extra}
        ${enlace && num !== "—" ? `<button class="stat-link" data-go="${enlace}">${esc(enlace === "pane" ? "Ver informe" : "Ver en el editor")}</button>` : ""}
      </div>`;
    };

    // la lista se rellena al momento con el documento abierto y, en cuanto la
    // biblioteca responde, se cambia por los tres ultimos documentos
    const documento = conDoc
      ? filaDelEstado(st, c)
      : `<li class="rec-vacio">Todavía no abriste ninguna tesis.<br>
           Usa <b>Abrir tesis .docx</b> para empezar.</li>`;

    return `
      <div class="dash">
        <div class="dash-main">

          <section class="hero">
            <div class="hero-text">
              <h1>Tu tesis, en mejores manos</h1>
              <p>Verifica el cumplimiento de las normas APA y mejora tu documento con correcciones guiadas.</p>
              <button class="hero-btn" data-act="open">${conDoc ? "Abrir otra tesis .docx" : "Abrir tesis .docx"} <span class="btn-arrow">›</span></button>
            </div>
          </section>

          <div class="drop-zone" data-act="open" role="button" tabindex="0">
            <div class="dz-cloud">
              <svg viewBox="0 0 24 24" width="48" height="48" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M5 12a5 5 0 0 1 5-5h2a2 2 0 0 1 2 2v2a5 5 0 0 1 5 5v1a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2z"/>
                <path d="M12 14V8M12 8l-3 3M12 8l3 3"/>
              </svg>
            </div>
            <h2 class="dz-title">Arrastra aquí tu tesis .docx</h2>
            <p class="dz-sub">o haz clic para explorar en tu computadora</p>
            <span class="dz-badge">${icon("shield")} Cifrado de extremo a extremo · Ningún texto es publicado</span>
          </div>

          <section class="stats">
            ${stat("", "chart", val(st.score != null ? st.score + " %" : "—"), "Cumplimiento", "pane")}
            ${stat("error", "search", error, "Errores", "correcciones")}
            ${stat("warning", "clipboard", avisa, "Avisos", "correcciones")}
            ${stat("", "docs", total, "Hallazgos en total", "pane")}
          </section>

          <section class="card">
            <div class="card-head">
              <h2>${icon("docs")} Documentos recientes</h2>
            </div>
            <div class="rec-filtros">
              <div class="rec-buscar">
                ${icon("search")}
                <input type="text" id="rec-buscar-input" placeholder="Buscar documento..." value="${esc(filtroBuscar || "")}">
              </div>
              <select id="rec-estado-select">
                <option value="">Todos los estados</option>
                <option value="pendiente">Pendiente</option>
                <option value="proceso">En proceso</option>
                <option value="completada">Completada</option>
              </select>
            </div>
            <ul class="recientes" id="dash-recientes">${documento}</ul>
          </section>
        </div>
      </div>`;
  }

  /* ---------- Acciones del panel ---------- */
  function mount(el) {
    root = el;
    root.querySelectorAll("[data-act]").forEach((b) => {
      b.addEventListener("click", () => {
        if (b.dataset.act === "open" && app.pickFile) app.pickFile();
      });
    });

    root.querySelectorAll("[data-go]").forEach((b) => {
      b.addEventListener("click", () => {
        const dest = b.dataset.go;
        if (dest === "pane") {
          Router.go("correcciones");
          if (app.openReport) app.openReport();
        } else {
          Router.go(dest);
        }
      });
    });

    const lista = document.getElementById("dash-recientes");
    if (lista) {
      lista.addEventListener("click", (e) => {
        const li = e.target.closest(".rec");
        if (li) abrirReciente(li.dataset.rec || "");
      });
      lista.addEventListener("keydown", (e) => {
        if (e.key !== "Enter" && e.key !== " ") return;
        const li = e.target.closest(".rec");
        if (!li) return;
        e.preventDefault();
        abrirReciente(li.dataset.rec || "");
      });
    }

    cargarRecientes();
    loadHealth();

    const inpBuscar = document.getElementById("rec-buscar-input");
    const selEstado = document.getElementById("rec-estado-select");
    if (inpBuscar) {
      inpBuscar.addEventListener("input", (e) => {
        filtroBuscar = e.target.value;
        cargarRecientes();
      });
    }
    if (selEstado) {
      selEstado.addEventListener("change", (e) => {
        filtroEstado = e.target.value;
        cargarRecientes();
      });
    }
  }

  // Abre un documento de la lista. Sin id (la fila del documento que ya esta
  // cargado) solo se cambia de vista.
  function abrirReciente(id) {
    const st = s();
    if (!id) {
      Router.go("correcciones");
      return;
    }
    const rec = recientes.find((r) => r.id === id);
    if (!rec || !rec.blob) return;
    if (st.name === rec.name) {
      Router.go("correcciones");
      return;
    }
    // abrir otra tesis descarta lo que haya sin guardar: se avisa antes
    if (st.name && st.dirty) {
      const seguir = window.confirm(
        "Hay cambios sin guardar en «" + st.name + "».\n¿Abrir «" + rec.name + "» igualmente?"
      );
      if (!seguir) return;
    }
    app.openFile(new File([rec.blob], rec.name));
    Router.go("correcciones");
  }

  // Los tres documentos mas recientes de la biblioteca. Manda la fecha del
  // ultimo analisis (los "que se revisaron"); si nunca se reviso, la de cuando
  // se abrio.
  async function cargarRecientes() {
    const lista = document.getElementById("dash-recientes");
    if (!lista) return;
    let docs = [];
    try {
      docs = await Library.list();
    } catch (e) {
      return; // si la biblioteca falla se queda lo que ya estaba pintado
    }
    if (!docs.length) return;

    const cuando = (r) => String(r.analyzedAt || r.addedAt || "");
    const fb = (filtroBuscar || "").toLowerCase();
    recientes = docs
      .filter((r) => {
        const texto = String(r.title || r.name || "").toLowerCase();
        if (fb && !texto.includes(fb)) return false;
        if (filtroEstado && r.status !== filtroEstado) return false;
        return true;
      })
      .sort((a, b) => cuando(b).localeCompare(cuando(a)));
    const st = s();
    lista.innerHTML = recientes.map((r) => filaDoc(r, st)).join("");
    Dom.hydrate(lista);
  }

  // el editor avisa cuando cambia el estado (abrir, verificar, corregir) para
  // que el panel no se quede con numeros viejos
  function refresh() {
    if (!root) return;
    const view = document.getElementById("view");
    const scroll = view ? view.scrollTop : 0;
    root.innerHTML = render();
    Dom.hydrate(root);
    mount(root);
    if (view) view.scrollTop = scroll;
  }

  function loadHealth() {
    const el = document.getElementById("dash-ai");
    if (!el) return;
    fetch("/api/health")
      .then((r) => (r.ok ? r.json() : null))
      .then((h) => {
        if (!h) throw new Error("sin respuesta");
        el.textContent = h.ai_enabled
          ? "Activa (" + (h.ai_provider || "") + " · " + (h.ai_model || "") + ") · Solo citas y referencias"
          : "No activada: falta configurar la clave en .env";
      })
      .catch(() => {
        el.textContent = "No se pudo contactar con el servidor";
      });
  }

  Router.register("inicio", {
    title: "Inicio",
    icon: "home",
    order: 10,
    render,
    mount,
    refresh,
    setup: (api) => {
      app = api;
    },
  });
})();
