/* Menú lateral y vistas.

Cada sección del menú muestra una pantalla distinta sobre la misma área de
trabajo. "Inicio" es el editor con su cinta de opciones; el resto agrupa las
herramientas alrededor de la tesis que esté abierta.
*/
(function () {
  "use strict";

  let app = null;
  let view = null;
  let inner = null;
  let nav = null;
  let current = "inicio";
  let lastReport = null;

  const TITLES = {
    inicio: { icon: "home", t: "Inicio", s: "Edita la tesis como en Word y verifica el cumplimiento de las normas APA 7." },
    tesis: { icon: "files", t: "Mis tesis", s: "Documentos abiertos y sesión guardada en este navegador." },
    correcciones: { icon: "wand", t: "Correcciones", s: "Todo el proceso de revisión: verificar, corregir y señalar." },
    reportes: { icon: "chart", t: "Reportes", s: "Resultado de la última verificación del documento." },
    ajustes: { icon: "gear", t: "Configuraciones", s: "Estado del servicio, vista y datos locales." },
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

  function hasDoc() {
    const s = app && app.state ? app.state() : null;
    return !!(s && s.name);
  }

  /* ---------- Cambio de vista ---------- */
  function go(name) {
    current = name;
    if (nav) {
      nav.querySelectorAll(".sb-item").forEach((b) => {
        b.classList.toggle("is-active", b.dataset.view === name);
      });
    }
    const editor = name === "inicio";
    const ribbon = $("ribbon");
    const ws = document.querySelector(".workspace");
    const bar = document.querySelector(".statusbar");
    if (ribbon) ribbon.hidden = !editor;
    if (ws) ws.hidden = !editor;
    if (bar) bar.hidden = !editor;

    if (view) {
      view.hidden = editor;
      if (!editor) {
        inner.innerHTML = render(name);
        if (window.Icons) window.Icons.hydrate(inner);
        bind(name);
      }
    }
    document.title = (TITLES[name] ? TITLES[name].t + " · " : "") + "APA Studio";
  }

  function head(name) {
    const t = TITLES[name];
    return `<div class="view-head">
      <h1>${icon(t.icon)}${esc(t.t)}</h1>
      <p>${esc(t.s)}</p>
    </div>`;
  }

  /* ---------- Pantallas ---------- */
  function render(name) {
    if (name === "tesis") return renderTesis();
    if (name === "correcciones") return renderCorrecciones();
    if (name === "reportes") return renderReportes();
    if (name === "ajustes") return renderAjustes();
    return "";
  }

  function renderTesis() {
    const s = app.state();
    const card = s.name
      ? `<div class="vgrid">
          <div class="vcard">
            <span class="vcard-icn">${icon("docs")}</span>
            <span class="vcard-body">
              <span class="vcard-title">${esc(s.name)}</span>
              <span class="vcard-text">${esc(s.pages)} páginas · ${esc(s.words)} palabras${s.savedAt ? " · guardado el " + esc(s.savedAt) : ""}${s.dirty ? " · <b>cambios sin guardar</b>" : ""}</span>
              <span class="vcard-actions">
                <button class="vbtn primary" data-act="open">Abrir en el editor</button>
                <button class="vbtn" data-act="save">Guardar</button>
              </span>
            </span>
          </div>
        </div>`
      : "";
    return (
      head("tesis") +
      `<input class="view-search" id="v-search" placeholder="Buscar tesis..." disabled>` +
      `<div class="view-section-title">Sesión actual</div>` +
      (card ||
        '<div class="vempty">Todavía no hay ninguna tesis abierta.<br>Selecciona un archivo <b>.docx</b> para empezar.</div>') +
      `<div class="view-section-title">Abrir documento</div>
       <div class="vgrid">
         <div class="vcard">
           <span class="vcard-icn">${icon("folder")}</span>
           <span class="vcard-body">
             <span class="vcard-title">Seleccionar archivo .docx</span>
             <span class="vcard-text">Abre una tesis o proyecto de tesis y la carga en el editor.</span>
             <span class="vcard-actions"><button class="vbtn primary" data-act="open">Abrir archivo</button></span>
           </span>
         </div>
       </div>`
    );
  }

  function renderCorrecciones() {
    const s = app.state();
    const off = s.name ? "" : " disabled";
    const warn = s.name
      ? ""
      : '<div class="vempty" style="margin-bottom:16px">Abre una tesis para poder verificar y corregir.</div>';
    return (
      head("correcciones") +
      warn +
      `<div class="view-section-title">Revisar</div>
       <div class="vgrid">
         <div class="vcard">
           <span class="vcard-icn">${icon("search")}</span>
           <span class="vcard-body">
             <span class="vcard-title">Verificar normas APA</span>
             <span class="vcard-text">Analiza la tesis contra las ${s.ruleCount} reglas APA y marca cada problema en el texto.</span>
             <span class="vcard-actions">
               <button class="vbtn primary" data-act="analyze"${off}>Verificar</button>
               <button class="vbtn" data-act="detail"${off}>Panel de informe</button>
             </span>
           </span>
         </div>
         <div class="vcard tone-purple">
           <span class="vcard-icn">${icon("spark")}</span>
           <span class="vcard-body">
             <span class="vcard-title">Revisión con IA</span>
             <span class="vcard-text">Segunda opinión de estilo y redacción. Clasifica las referencias. No modifica el documento.</span>
             <span class="vcard-actions"><button class="vbtn" data-act="ai"${off}>Revisar con IA</button></span>
           </span>
         </div>
         <div class="vcard tone-ok">
           <span class="vcard-icn">${icon("wand")}</span>
           <span class="vcard-body">
             <span class="vcard-title">Corregir documento</span>
             <span class="vcard-text">Interlineado, espacios, sangrías, márgenes, ${"&"} en citas, orden de referencias y cursivas. Con vista previa y deshacer.</span>
             <span class="vcard-actions"><button class="vbtn primary" data-act="fix"${off}>Corregir</button></span>
           </span>
         </div>
         <div class="vcard tone-warning">
           <span class="vcard-icn">${icon("clipboard")}</span>
           <span class="vcard-body">
             <span class="vcard-title">Señalamiento de errores</span>
             <span class="vcard-text">Resalta los errores en el texto y explica la regla al hacer clic. "Quitar marcas" solo borra los colores: no resuelve nada.</span>
             <span class="vcard-actions">
               <button class="vbtn" data-act="mark"${off}>Marcar ahora</button>
               <button class="vbtn" data-act="unmark">Quitar marcas</button>
             </span>
           </span>
         </div>
       </div>

       <div class="view-section-title">Páginas</div>
       <div class="vgrid">
         <div class="vcard">
           <span class="vcard-icn">${icon("pageBreak")}</span>
           <span class="vcard-body">
             <span class="vcard-title">Salto de página</span>
             <span class="vcard-text">Inserta un salto donde esté el cursor y reorganiza la paginación.</span>
             <span class="vcard-actions"><button class="vbtn" data-act="pagebreak"${off}>Insertar salto</button></span>
           </span>
         </div>
         <div class="vcard">
           <span class="vcard-icn">${icon("ruler")}</span>
           <span class="vcard-body">
             <span class="vcard-title">Reorganizar páginas</span>
             <span class="vcard-text">Vuelve a calcular las hojas tras editar. No cambia el texto.</span>
             <span class="vcard-actions"><button class="vbtn" data-act="repaginate"${off}>Reorganizar</button></span>
           </span>
         </div>
       </div>

       <div class="view-section-title">Estilo APA</div>
       <div class="vgrid">
         <div class="vcard tone-error">
           <span class="vcard-icn">${icon("docs")}</span>
           <span class="vcard-body">
             <span class="vcard-title">Aplicar formato base</span>
             <span class="vcard-text">Pisa en todo el documento: Times New Roman 12, interlineado 2.0, alineado a la izquierda, sangría 1.27 cm y márgenes internos 0. Ojo: si tu fuente ya era válida en APA, esto te empeora el documento.</span>
             <span class="vcard-actions"><button class="vbtn" data-act="apadefaults"${off}>Aplicar formato</button></span>
           </span>
         </div>
         <div class="vcard">
           <span class="vcard-icn">${icon("undo")}</span>
           <span class="vcard-body">
             <span class="vcard-title">Deshacer y rehacer</span>
             <span class="vcard-text">Vuelve a un estado anterior tras cualquier cambio, formato o corrección.</span>
             <span class="vcard-actions">
               <button class="vbtn" data-act="undo"${off}>Deshacer</button>
               <button class="vbtn" data-act="redo"${off}>Rehacer</button>
             </span>
           </span>
         </div>
       </div>

       <div class="view-section-title">Guardar y entregar</div>
       <div class="vgrid">
         <div class="vcard">
           <span class="vcard-icn">${icon("save")}</span>
           <span class="vcard-body">
             <span class="vcard-title">Guardar en el navegador</span>
             <span class="vcard-text">Conserva la sesión en este equipo para continuar más tarde.</span>
             <span class="vcard-actions"><button class="vbtn primary" data-act="save"${off}>Guardar</button></span>
           </span>
         </div>
         <div class="vcard tone-ok">
           <span class="vcard-icn">${icon("download")}</span>
           <span class="vcard-body">
             <span class="vcard-title">Descargar tesis corregida</span>
             <span class="vcard-text">Aplica las correcciones sobre el archivo original y descarga un <b>.docx</b> nuevo.</span>
             <span class="vcard-actions"><button class="vbtn primary" data-act="export"${off}>Descargar .docx</button></span>
           </span>
         </div>
         <div class="vcard">
           <span class="vcard-icn">${icon("chart")}</span>
           <span class="vcard-body">
             <span class="vcard-title">Informe en Word</span>
             <span class="vcard-text">Resumen de cumplimiento, desglose por categoría y tabla de hallazgos.</span>
             <span class="vcard-actions"><button class="vbtn" data-act="report"${off}>Descargar informe</button></span>
           </span>
         </div>
       </div>`
    );
  }

  function renderReportes() {
    const s = app.state();
    if (!s.counts || !s.counts.all) {
      return (
        head("reportes") +
        '<div class="vempty">Todavía no hay ningún análisis.<br>Ve a <b>Correcciones</b> y pulsa <b>Verificar</b>.</div>'
      );
    }
    const c = s.counts;
    return (
      head("reportes") +
      `<div class="vbig">
         <div class="score-ring"><span>${esc(s.score)}</span><small>%</small></div>
         <div class="vstats">
           <div class="vstat error"><div class="vstat-num">${c.error || 0}</div><div class="vstat-label">Errores</div></div>
           <div class="vstat warning"><div class="vstat-num">${c.warning || 0}</div><div class="vstat-label">Avisos</div></div>
           <div class="vstat"><div class="vstat-num">${c.info || 0}</div><div class="vstat-label">Observaciones</div></div>
           <div class="vstat"><div class="vstat-num">${c.all || 0}</div><div class="vstat-label">Total</div></div>
         </div>
         <div>
           <div class="vcard-actions">
             <button class="vbtn primary" data-act="detail">Ver informe completo</button>
             <button class="vbtn" data-act="report">Descargar en Word</button>
           </div>
         </div>
       </div>

       <div class="view-section-title">Hallazgos por regla</div>
       <div class="vgrid">
         ${Object.keys(s.byRule || {})
           .sort()
           .map(
             (k) => `<div class="vcard">
              <span class="vcard-icn">${icon("clipboard")}</span>
              <span class="vcard-body">
                <span class="vcard-title">${esc(k)}</span>
                <span class="vcard-text">${s.byRule[k]} hallazgo(s)</span>
              </span>
            </div>`
           )
           .join("") || '<div class="vempty">Sin datos.</div>'}
       </div>

       <div class="view-section-title">Aviso importante</div>
       <div class="vempty">El análisis se hizo sobre el archivo <b>.docx</b> original que abriste.<br>Para que la puntuación refleje las correcciones, descarga la tesis corregida y vuelve a abrirla.</div>`
    );
  }

  function renderAjustes() {
    const s = app.state();
    return (
      head("ajustes") +
      `<div class="view-section-title">Servicio</div>
       <div class="vbig" style="display:block">
         <div class="vinfo"><span>Estado del servidor</span><b id="cfg-health">Comprobando…</b></div>
         <div class="vinfo"><span>Revisión con IA</span><b id="cfg-ai">—</b></div>
         <div class="vinfo"><span>Motor de reglas</span><b>${esc(s.ruleCount)} reglas APA 7</b></div>
       </div>

       <div class="view-section-title">Vista</div>
       <div class="vgrid">
         <div class="vcard">
           <span class="vcard-icn">${icon("home")}</span>
           <span class="vcard-body">
             <span class="vcard-title">Menú lateral</span>
             <span class="vcard-text">Ocultarlo amplía el área de edición.</span>
             <span class="vcard-actions"><button class="vbtn" data-act="menu">Ocultar / mostrar</button></span>
           </span>
         </div>
         <div class="vcard">
           <span class="vcard-icn">${icon("docs")}</span>
           <span class="vcard-body">
             <span class="vcard-title">Cinta de opciones</span>
             <span class="vcard-text">Se puede plegar desde la flecha de la cinta.</span>
             <span class="vcard-actions"><button class="vbtn" data-act="ribbon">Plegar / desplegar</button></span>
           </span>
         </div>
       </div>

       <div class="view-section-title">Datos locales</div>
       <div class="vgrid">
         <div class="vcard tone-error">
           <span class="vcard-icn">${icon("save")}</span>
           <span class="vcard-body">
             <span class="vcard-title">Borrar la sesión guardada</span>
             <span class="vcard-text">Elimina el documento guardado en este navegador. No afecta a tu archivo original.</span>
             <span class="vcard-actions"><button class="vbtn" data-act="wipe">Borrar sesión</button></span>
           </span>
         </div>
       </div>`
    );
  }

  /* ---------- Acciones ---------- */
  function bind(name) {
    inner.querySelectorAll("[data-act]").forEach((b) => {
      b.addEventListener("click", () => {
        const a = b.dataset.act;
        if (a === "open") {
          app.pickFile();
          go("inicio");
        } else if (a === "analyze") {
          go("inicio");
          app.analyze();
        } else if (a === "ai") {
          go("inicio");
          app.aiReview();
        } else if (a === "fix") {
          go("inicio");
          app.fix();
        } else if (a === "mark") {
          go("inicio");
          app.mark();
        } else if (a === "unmark") {
          app.unmark();
        } else if (a === "pagebreak") {
          go("inicio");
          app.pageBreak();
        } else if (a === "repaginate") {
          go("inicio");
          app.repaginate();
        } else if (a === "apadefaults") {
          go("inicio");
          app.apaDefaults();
        } else if (a === "undo") {
          app.undo();
        } else if (a === "redo") {
          app.redo();
        } else if (a === "save") {
          app.save();
          go(name);
        } else if (a === "export") {
          app.exportDocx();
        } else if (a === "report") {
          app.exportReport();
        } else if (a === "detail") {
          go("inicio");
          app.openReport();
        } else if (a === "menu") {
          toggleMenu();
        } else if (a === "ribbon") {
          app.toggleRibbon();
        } else if (a === "wipe") {
          app.wipe();
          go(name);
        }
      });
    });
    if (name === "ajustes") loadHealth();
  }

  function loadHealth() {
    fetch("/api/health")
      .then((r) => r.json())
      .then((h) => {
        const el = document.getElementById("cfg-health");
        if (el) el.textContent = h.status === "ok" ? "En línea" : "Con incidencias";
        const ai = document.getElementById("cfg-ai");
        if (ai) {
          ai.textContent = h.ai_enabled
            ? "Activada (" + (h.ai_provider || "") + " · " + (h.ai_model || "") + ")"
            : "Desactivada (sin clave configurada)";
        }
      })
      .catch(() => {
        const el = document.getElementById("cfg-health");
        if (el) el.textContent = "No se pudo contactar con el servidor";
      });
  }

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
    const btn = document.getElementById("sb-collapse");
    if (btn) {
      const t = btn.querySelector("strong");
      if (t) t.textContent = label;
      const s = btn.querySelector("small");
      if (s) s.textContent = show ? "Amplía el área de edición" : "Volver a mostrar el menú";
      btn.querySelector("[data-icon]")?.setAttribute("data-icon", show ? "chevron" : "menu");
      if (window.Icons) window.Icons.hydrate(btn);
    }
    const showBtn = document.getElementById("sb-show");
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
    go("inicio");
  }

  window.Sidebar = { init, go, setMenu, current: () => current };
})();