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
  // la biblioteca completa, sin filtros (es la que se cuenta en el resumen)
  let biblioteca = [];
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

  // Conteo por estado de TODA la biblioteca, igual que hace "Mis tesis".
  // Antes solo se miraba el documento abierto, por eso la tarjeta de
  // "Pendientes" marcaba 0 mientras la lista de abajo mostraba pendientes.
  function conteoEstados() {
    const estados = { proceso: 0, completada: 0, pendiente: 0 };
    const st = s();
    const c = st.counts || {};
    const conDoc = !!st.name;

    if (biblioteca.length) {
      biblioteca.forEach((r) => {
        const e = Library.LABEL[r.status] ? r.status : "pendiente";
        if (estados[e] != null) estados[e]++;
      });
    }

    // El documento abierto cuenta aunque todavia no este en la biblioteca
    // (aun no ha responden IndexedDB).
    if (conDoc && !biblioteca.some((r) => r.name === st.name)) {
      const e = st.score == null ? "pendiente" : (c.error ? "proceso" : "completada");
      if (estados[e] != null) estados[e]++;
    }

    const total = biblioteca.length || (conDoc ? 1 : 0);
    const pct = total
      ? Math.round(((estados.completada + estados.proceso * 0.5) / total) * 100)
      : 0;
    return { c: estados, pct };
  }

  // Vuelca el conteo en el DOM. Se llama aparte porque los datos de la
  // biblioteca llegan despues del primer pintado.
  function pintarContadores() {
    const { c: estados, pct } = conteoEstados();
    const anillo = document.getElementById("resumen-ring-fill");
    if (anillo) anillo.style.strokeDashoffset = String(60 * (1 - pct / 100));
    const barra = document.getElementById("resumen-barra-lleno");
    if (barra) barra.style.width = pct + "%";
    const pctEl = document.getElementById("resumen-porcentaje");
    if (pctEl) pctEl.textContent = pct + "%";
    ["proceso", "completada", "pendiente"].forEach((k) => {
      const el = document.getElementById("resumen-num-" + k);
      if (el) el.textContent = String(estados[k]);
    });
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

    const { c: estados, pct } = conteoEstados();

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

          <section class="resumen">
            <div class="resumen-head">
              <div class="resumen-text">
                <h2>Resumen de tu actividad</h2>
                <p>Últimos movimientos y progreso de tus tesis.</p>
              </div>
              <a class="resumen-ver" href="#" data-act="ver-todas">Ver todas <span class="resumen-arrow">→</span></a>
            </div>
            <div class="resumen-body">
              <div class="resumen-doc-icon">
                  <svg class="resumen-doc-ring" viewBox="0 0 24 24">
                    <circle class="resumen-doc-ring-bg" cx="12" cy="12" r="9.5" fill="none" stroke="#e8edf3" stroke-width="2" stroke-linecap="round"/>
                    <circle class="resumen-doc-ring-fill" id="resumen-ring-fill" cx="12" cy="12" r="9.5" fill="none" stroke="var(--accent)" stroke-width="2" stroke-linecap="round" stroke-dasharray="60" style="stroke-dashoffset:${60 * (1 - pct / 100)}"/>
                  </svg>
                  ${icon("docs")}
                </div>
              <div class="resumen-content">
                <div class="resumen-progreso">
                  <div class="resumen-detalle">
                    <div class="resumen-titulo">Progreso general de tus tesis</div>
                    <div class="resumen-barra">
                      <div class="resumen-barra-lleno" id="resumen-barra-lleno" style="width:${pct}%"></div>
                    </div>
                    <span class="resumen-porcentaje" id="resumen-porcentaje">${pct}%</span>
                  </div>
                </div>
                <div class="resumen-estados">
                  <div class="resumen-estado resumen-estado-proceso">
                    <div class="resumen-estado-icn">${icon("clock")}</div>
                    <div class="resumen-num" id="resumen-num-proceso">${estados.proceso}</div>
                    <div class="resumen-label">Tesis en proceso</div>
                  </div>
                  <div class="resumen-estado resumen-estado-completada">
                    <div class="resumen-estado-icn">${icon("fix")}</div>
                    <div class="resumen-num" id="resumen-num-completada">${estados.completada}</div>
                    <div class="resumen-label">Completada</div>
                  </div>
                  <div class="resumen-estado resumen-estado-pendiente">
                    <div class="resumen-estado-icn">${icon("pending")}</div>
                    <div class="resumen-num" id="resumen-num-pendiente">${estados.pendiente}</div>
                    <div class="resumen-label">Pendientes</div>
                  </div>
                </div>
              </div>
            </div>
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
      </div>

      <!-- Modal de subida de tesis (drag & drop) -->
      <div class="tv-upload-modal" id="tv-upload-modal" hidden>
        <div class="tv-upload-backdrop"></div>
        <div class="tv-upload-panel">
          <button class="tv-upload-close" id="tv-upload-close">&times;</button>
          <div class="tv-upload-dropzone" id="tv-upload-dropzone">
            <span class="tv-upload-icn" data-icon="cloudUp"></span>
            <h2>Arrastra aqu\u00ed tu tesis .docx</h2>
            <p>o haz clic para explorar en tu computadora</p>
            <button class="tv-upload-btn" id="tv-upload-btn">Seleccionar archivo .docx</button>
            <p class="tv-upload-badge">
              <span class="tv-upload-badge-dot"></span>
              Cifrado de extremo a extremo \u00b7 Ning\u00fan texto es publicado
            </p>
          </div>
        </div>
      </div>
    </div>`;
  }

  /* ---------- Acciones del panel ---------- */
  function mount(el) {
    root = el;

    // "Ver todas" lleva a Mis tesis, que es la vista con la biblioteca
    // completa y los filtros por estado.
    const verTodas = root.querySelector("[data-act='ver-todas']");
    if (verTodas) {
      verTodas.addEventListener("click", (e) => {
        e.preventDefault();
        Router.go("tesis");
      });
    }

    // El boton "Abrir tesis .docx" abre el modal de drag & drop.
    root.querySelectorAll("[data-act='open']").forEach((b) => {
      b.addEventListener("click", (e) => {
        if (b.classList.contains("hero-btn")) {
          const modal = document.getElementById("tv-upload-modal");
          if (modal) modal.hidden = false;
          return;
        }
        if (b.dataset.act === "open" && app.pickFile) {
          const fileInput = document.getElementById("file");
          const onPicked = () => {
            fileInput.removeEventListener("change", onPicked);
            Router.go("correcciones");
          };
          fileInput.addEventListener("change", onPicked, { once: true });
          app.pickFile();
        }
      });
    });

    /* ---------- Modal de subida de tesis ---------- */
    const modal = document.getElementById("tv-upload-modal");
    const backdrop = document.getElementById("tv-upload-backdrop");
    const closeBtn = document.getElementById("tv-upload-close");
    const dropzone = document.getElementById("tv-upload-dropzone");
    const uploadBtn = document.getElementById("tv-upload-btn");

    function cerrarModal() { if (modal) modal.hidden = true; }

    if (closeBtn) closeBtn.addEventListener("click", cerrarModal);
    if (backdrop) backdrop.addEventListener("click", cerrarModal);

    // Abrir explorador y cerrar modal
    function subirArchivo() {
      cerrarModal();
      if (app && app.pickFile) app.pickFile();
    }

    // Al hacer clic en el area de drop o en el boton, abrir el explorador
    if (dropzone) dropzone.addEventListener("click", (e) => {
      if (e.target.closest("#tv-upload-close")) return;
      subirArchivo();
    });
    if (uploadBtn) uploadBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      subirArchivo();
    });

    // Drag & drop visual: resaltar al arrastrar, abrir explorador al soltar
    if (dropzone) {
      ["dragenter","dragover"].forEach(ev => dropzone.addEventListener(ev, (e) => {
        e.preventDefault(); dropzone.classList.add("tv-drag-active");
      }));
      ["dragleave","drop"].forEach(ev => dropzone.addEventListener(ev, (e) => {
        e.preventDefault(); dropzone.classList.remove("tv-drag-active");
      }));
      dropzone.addEventListener("drop", (e) => {
        e.preventDefault();
        subirArchivo();
      });
    }

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

  // La biblioteca completa, sin filtros. Los contadores del resumen se
  // cuentan sobre esta, no sobre la vista filtrada, para que buscar o
  // filtrar no cambie los numeros.
  async function cargarRecientes() {
    const lista = document.getElementById("dash-recientes");
    if (!lista) return;
    let docs = [];
    try {
      docs = await Library.list();
    } catch (e) {
      return; // si la biblioteca falla se queda lo que ya estaba pintado
    }
    biblioteca = docs || [];
    if (!biblioteca.length) {
      recientes = [];
      pintarContadores();
      return;
    }

    const cuando = (r) => String(r.analyzedAt || r.addedAt || "");
    const fb = (filtroBuscar || "").toLowerCase();
    recientes = biblioteca
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
    // la biblioteca ya respondio: los contadores de "Resumen de tu actividad"
    // tienen que reflejar el total real, no solo el documento abierto
    pintarContadores();
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
