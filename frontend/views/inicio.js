/* Vista Inicio: panel de situación.

Nada de lo que se muestra es inventado: todo sale del estado real del
documento abierto y del último análisis.
  */
import { Router } from "../core/router.js";
import { Dom } from "../core/dom.js";

(function () {
    "use strict";

    const { esc, icon, fecha } = Dom;

  let root = null;
  let app = null;

  // el numero de reglas lo pide el propio panel: el editor lo consulta aparte
  let ruleCount = 0;
  let rulesAsked = false;

  function s() {
    return app && typeof app.state === "function" ? app.state() : {};
  }

  function loadRuleCount() {
    if (rulesAsked) return;
    rulesAsked = true;
    fetch("/api/rules")
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => {
        if (d && Array.isArray(d.rules)) ruleCount = d.rules.length;
        pintarReglas();
      })
      .catch(() => pintarReglas());
  }

  function pintarReglas() {
    if (!root) return;
    const n = ruleCount || "?";
    root.querySelectorAll("[data-reglas]").forEach((el) => {
      el.textContent = n;
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

    // sin dato no hay nada que ver: el enlace se oculta en vez de llevar a una
    // pantalla vacia
    const stat = (tone, ico, num, label, enlace) => `
      <div class="stat ${tone}${num === "—" ? " vacio" : ""}">
        <span class="stat-icn">${icon(ico)}</span>
        <span class="stat-num">${esc(num)}</span>
        <span class="stat-label">${esc(label)}</span>
        ${enlace && num !== "—" ? `<button class="stat-link" data-go="${enlace}">${esc(enlace === "pane" ? "Ver informe" : "Ver en el editor")}</button>` : ""}
      </div>`;

    const documento = conDoc
      ? `<div class="doc-item">
           <span class="doc-icn">${icon("docs")}</span>
           <span class="doc-body">
             <span class="doc-name">${esc(st.name)}</span>
             <span class="doc-meta">${st.pages} páginas · ${st.words.toLocaleString("es")} palabras${st.savedAt ? " · guardado el " + esc(fecha(st.savedAt)) : " · sin guardar"}${st.dirty ? " · <b>cambios sin guardar</b>" : ""}</span>
           </span>
           <span class="doc-estado ${st.dirty ? "pendiente" : "ok"}">${st.dirty ? "Sin guardar" : "Guardado"}</span>
         </div>
         <div class="doc-acciones">
           <button class="vbtn" data-act="open">Cambiar de tesis</button>
           <button class="vbtn primary" data-go="correcciones">Ir al editor</button>
         </div>`
      : `<div class="vempty">No hay ninguna tesis abierta.<br>
           Usa <b>Abrir tesis .docx</b> para empezar.</div>`;

    return `
      <div class="dash">
        <div class="dash-main">

          <section class="hero">
            <div class="hero-text">
              <h1>Tu tesis, en mejores manos</h1>
              <p>Abre tu proyecto de tesis, verifica el cumplimiento de las normas
                 APA (7.ª edición) y corrige de forma automática lo que se puede
                 corregir sin criterio humano.</p>
              <button class="hero-btn" data-act="open">${icon("folder")} ${conDoc ? "Abrir otra tesis .docx" : "Abrir tesis .docx"}</button>
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
              <h2>${icon("docs")} Tu tesis</h2>
              ${conDoc ? `<button class="card-link" data-go="correcciones">Ir al editor</button>` : ""}
            </div>
            ${documento}
          </section>

          <section class="card">
            <div class="card-head"><h2>${icon("check")} Cómo funciona</h2></div>
            <ol class="pasos">
              <li><b>Abre</b> tu archivo .docx en el editor, con su cinta de opciones.</li>
              <li><b>Verifica</b> contra las <span data-reglas>…</span> reglas de las normas APA 7.</li>
              <li><b>Corrige</b> de forma automática el formato y la puntuación, y resuelve a mano lo demás.</li>
              <li><b>Descarga</b> la tesis corregida en .docx, o el informe en Word.</li>
            </ol>
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
    loadRuleCount();
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

    loadHealth();
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
    pintarReglas();
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
