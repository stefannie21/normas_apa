/* Menú lateral.

Solo la navegación: cada sección abre un área de trabajo distinta sobre el
mismo editor. El contenido de cada vista se decide más adelante, así que aquí
no se inventa nada: se muestra únicamente el encabezado de la sección.
*/
(function () {
  "use strict";

  let app = null;
  let view = null;
  let inner = null;
  let nav = null;
  let current = "inicio";

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
        const t = TITLES[name];
        inner.innerHTML =
          `<div class="view-head">
             <h1>${icon(t.icon)}${esc(t.t)}</h1>
           </div>
           <div class="vempty">Esta seccion todavia no tiene contenido.</div>`;
        if (window.Icons) window.Icons.hydrate(inner);
      }
    }
    document.title = (TITLES[name] ? TITLES[name].t + " · " : "") + "APA Studio";
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
      const s = btn.querySelector("small");
      if (s) s.textContent = show ? "Amplía el área de edición" : "Volver a mostrar el menú";
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
    go("inicio");
  }

  window.Sidebar = { init, go, setMenu, current: () => current };
})();