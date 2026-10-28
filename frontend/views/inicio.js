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
    const stat = (tone, ico, num, label, enlace) => `
      <div class="stat ${tone}${num === "—" ? " vacio" : ""}">
        <span class="stat-icn">${icon(ico)}</span>
        <span class="stat-num">${esc(num)}</span>
        <span class="stat-label">${esc(label)}</span>
        ${enlace && num !== "—" ? `<button class="stat-link" data-go="${enlace}">${esc(enlace === "pane" ? "Ver informe" : "Ver en el editor")}</button>` : ""}
      </div>`;

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
              <p>Abre tu proyecto de tesis, verifica el cumplimiento de las normas
                 APA (7.ª edición) y corrige de forma automática lo que se puede
                 corregir sin criterio humano.</p>
              <div class="drop-zone" data-act="open" role="button" tabindex="0">
                <div class="dz-cloud">
                  <svg viewBox="0 0 24 24" width="56" height="56" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M5 12a5 5 0 0 1 5-5h2a2 2 0 0 1 2 2v2a5 5 0 0 1 5 5v1a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2z"/>
                    <path d="M12 14V8M12 8l-3 3M12 8l3 3"/>
                  </svg>
                </div>
                <h2 class="dz-title">Arrastra aquí tu tesis .docx</h2>
                <p class="dz-sub">o haz clic para explorar en tu computadora</p>
                <span class="dz-badge">${icon("shield")} Cifrado de extremo a extremo · Ningún texto es publicado</span>
              </div>
            </div>
            <span class="hero-art">${icon("cap")}</span>
          </section>

          <section class="stats">
            ${stat("", "chart", val(st.score != null ? st.score + " %" : "—"), "Nivel de cumplimiento", "pane")}
            ${stat("error", "search", error, "Errores", "correcciones")}
            ${stat("warning", "clipboard", avisa, "Avisos", "correcciones")}
            ${stat("", "docs", total, "Hallazgos en total", "pane")}
          </section>

          <section class="card">
            <div class="card-head">
              <h2>${icon("docs")} Recién abiertos</h2>
            </div>
            <ul class="recientes" id="dash-recientes">${documento}</ul>
          </section>
        </div>

        <aside class="dash-side">
          <section class="card">
            <div class="card-head"><h2>${icon("spark")} Revisión con IA</h2></div>
            <p class="card-text">Como segunda opinión, la IA clasifica citas y referencias
               para detectar elementos APA ausentes. <b>Nunca escribe en el documento.</b></p>
            <ul class="check">
              <li>Formato y estructura APA</li>
              <li>Citas en el texto</li>
              <li>Lista de referencias</li>
              <li>Solo envía citas y referencias, no el texto completo</li>
            </ul>
            <p class="card-note" id="dash-ai">Comprobando el estado del servicio…</p>
          </section>

          <section class="card">
            <div class="card-head"><h2>${icon("spark")} Consejos rápidos</h2></div>
            <ul class="tips">
              <li>Usa palabras clave relevantes en la introducción.</li>
              <li>Revisa la coherencia entre objetivos, metodología y conclusiones.</li>
              <li>Evita el uso excesivo de citas textuales.</li>
              <li>Mantén un estilo de redacción claro y formal.</li>
              <li>Verifica que cada cita tenga su entrada en Referencias.</li>
              <li>En APA 7, con 3 o más autores se usa <em>et al.</em> desde la primera mención.</li>
            </ul>
          </section>
        </aside>
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
    recientes = docs.sort((a, b) => cuando(b).localeCompare(cuando(a))).slice(0, 3);
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
