/* Menú lateral.

- Inicio      -> panel de situación (lo que hay ahora mismo en el editor)
- Correcciones-> el editor con su cinta de opciones
- Las demás secciones están vacías a la espera de decidir su contenido.

Nada de lo que se muestra es inventado: todo sale del estado real del
documento abierto y del último análisis.
*/
(function () {
  "use strict";

  let app = null;
  let view = null;
  let inner = null;
  let nav = null;
  let current = "inicio";

  const EDITOR = "correcciones";

  const TITLES = {
    inicio: { icon: "home", t: "Inicio", s: "" },
    tesis: { icon: "files", t: "Mis tesis", s: "" },
    correcciones: { icon: "wand", t: "Correcciones", s: "" },
    reportes: { icon: "chart", t: "Reportes", s: "" },
    ajustes: { icon: "gear", t: "Configuraciones", s: "" },
  };

  function $(id) {
    return document.getElementById(id);
  }

  function esc(s) {
    const d = document.createElement("div");
    d.textContent = s == null ? "" : String(s);
    return d.innerHTML;
  }

  function icon(name) {
    return `<span data-icon="${name}"></span>`;
  }

  function s() {
    return app && app.state ? app.state() : {};
  }

  /* ---------- Cambio de vista ---------- */
  function go(name) {
    current = name;
    if (nav) {
      nav.querySelectorAll(".sb-item").forEach((b) => {
        b.classList.toggle("is-active", b.dataset.view === name);
      });
    }
    const editor = name === EDITOR;
    const ribbon = $("ribbon");
    const ws = document.querySelector(".workspace");
    const bar = document.querySelector(".statusbar");
    if (ribbon) ribbon.hidden = !editor;
    if (ws) ws.hidden = !editor;
    if (bar) bar.hidden = !editor;

    if (view) {
      view.hidden = editor;
      if (!editor) {
        inner.innerHTML = name === "inicio" ? renderInicio() : renderVacio(name);
        if (window.Icons) window.Icons.hydrate(inner);
        if (name === "inicio") {
          bindInicio();
          pintarReglas();
        }
      }
    }
    document.title = (TITLES[name] ? TITLES[name].t + " · " : "") + "APA Studio";
  }

  function renderVacio(name) {
    const t = TITLES[name];
    return `<div class="view-head"><h1>${icon(t.icon)}${esc(t.t)}</h1></div>
      <div class="vempty">Esta seccion todavia no tiene contenido.</div>`;
  }

  /* ---------- Panel de Inicio ---------- */
  // el numero de reglas lo pide el propio panel: el editor lo consulta aparte
  let ruleCount = 0;

  function loadRuleCount() {
    fetch("/api/rules")
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => {
        if (d && Array.isArray(d.rules)) ruleCount = d.rules.length;
        pintarReglas();
      })
      .catch(() => pintarReglas());
  }

  function pintarReglas() {
    const n = ruleCount || "?";
    inner.querySelectorAll("[data-reglas]").forEach((el) => {
      el.textContent = n;
    });
  }

  function renderInicio() {
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
           <button class="vbtn primary" data-go="${EDITOR}">Ir al editor</button>
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
            ${stat("error", "search", error, "Errores", EDITOR)}
            ${stat("warning", "clipboard", avisa, "Avisos", EDITOR)}
            ${stat("", "docs", total, "Hallazgos en total", "pane")}
          </section>

          <section class="card">
            <div class="card-head">
              <h2>${icon("docs")} Tu tesis</h2>
              ${conDoc ? `<button class="card-link" data-go="${EDITOR}">Ir al editor</button>` : ""}
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
            <p class="card-text">Como segunda opinión, la IA clasifica las referencias y
               detecta detalles de estilo y redacción. <b>Nunca escribe en el documento.</b></p>
            <ul class="check">
              <li>Ortografía y gramática</li>
              <li>Coherencia y estructura</li>
              <li>Estilo académico</li>
              <li>Citas y referencias</li>
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
            </ul>
          </section>
        </aside>
      </div>`;
  }

  function fecha(iso) {
    try {
      return new Date(iso).toLocaleString("es", {
        day: "2-digit",
        month: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
      });
    } catch (e) {
      return "";
    }
  }

  /* ---------- Acciones del panel ---------- */
  function bindInicio() {
    inner.querySelectorAll("[data-act]").forEach((b) => {
      b.addEventListener("click", () => {
        if (b.dataset.act === "open") {
          if (app.pickFile) app.pickFile();
        }
      });
    });
    inner.querySelectorAll("[data-go]").forEach((b) => {
      b.addEventListener("click", () => {
        if (b.dataset.go === "pane") {
          go(EDITOR);
          if (app.openReport) app.openReport();
        } else {
          go(b.dataset.go);
        }
      });
    });
    loadHealth();
  }

  // el editor avisa cuando cambia el estado (abrir, verificar, corregir) para
  // que el panel no se quede con numeros viejos
  function refresh() {
    if (current !== "inicio") return;
    const scroll = view ? view.scrollTop : 0;
    inner.innerHTML = renderInicio();
    if (window.Icons) window.Icons.hydrate(inner);
    bindInicio();
    pintarReglas();
    if (view) view.scrollTop = scroll;
  }

  function loadHealth() {
    const el = $("dash-ai");
    if (!el) return;
    fetch("/api/health")
      .then((r) => (r.ok ? r.json() : null))
      .then((h) => {
        if (!h) throw new Error("sin respuesta");
        el.textContent = h.ai_enabled
          ? "Activa (" + (h.ai_provider || "") + " · " + (h.ai_model || "") + ")"
          : "No activada: falta configurar la clave en .env";
      })
      .catch(() => {
        el.textContent = "No se pudo contactar con el servidor";
      });
  }

  /* ---------- Menú plegado ---------- */
  function toggleMenu() {
    // si esta oculto se muestra, y al reves: el valor actual decide el destino
    setMenu(document.querySelector(".app").classList.contains("sb-hidden"));
  }

  function setMenu(show) {
    const appEl = document.querySelector(".app");
    if (!appEl) return;
    appEl.classList.toggle("sb-hidden", !show);
    try {
      localStorage.setItem("apa.menu.hidden", show ? "0" : "1");
    } catch (e) {
      /* modo privado */
    }
    const label = show ? "Ocultar menú" : "Mostrar menú";
    const btn = $("sb-collapse");
    if (btn) {
      const t = btn.querySelector("strong");
      if (t) t.textContent = label;
      const s2 = btn.querySelector("small");
      if (s2) s2.textContent = show ? "Amplía el área de edición" : "Volver a mostrar el menú";
      btn.querySelector("[data-icon]")?.setAttribute("data-icon", show ? "chevron" : "menu");
      if (window.Icons) window.Icons.hydrate(btn);
    }
    const showBtn = $("sb-show");
    if (showBtn) showBtn.title = show ? "Menú visible" : "Mostrar el menú";
  }

  /* ---------- Arranque ---------- */
  function init(api) {
    app = api;
    nav = $("sb-nav");
    view = $("view");
    inner = $("view-inner");

    if (nav) {
      nav.addEventListener("click", (e) => {
        const b = e.target.closest(".sb-item");
        if (b) go(b.dataset.view);
      });
    }
    const card = $("sb-collapse");
    if (card) card.addEventListener("click", toggleMenu);

    const showBtn = $("sb-show");
    if (showBtn) showBtn.addEventListener("click", () => setMenu(true));

    try {
      if (localStorage.getItem("apa.menu.hidden") === "1") setMenu(false);
    } catch (e) {
      /* sin persistencia */
    }
    loadRuleCount();
    go("inicio");
  }

  window.Sidebar = { init, go, setMenu, refresh, current: () => current };
})();