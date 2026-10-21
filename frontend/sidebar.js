/* Menú lateral: solo plegado y despliegue. Las secciones viven en views/ y las
   maneja core/router.js.

   Plegado no es "ocultar": el menú se queda en una franja de iconos, de modo que
   siempre hay un sitio visible donde volver a desplegarlo. El estado se recuerda
   entre recargas. */
const Sidebar = (function () {
  "use strict";

  const KEY = "apa.sidebar.collapsed";

  function setCollapsed(collapsed) {
    const sidebar = document.getElementById("sidebar");
    if (sidebar) sidebar.classList.toggle("is-collapsed", collapsed);

    const toggle = document.getElementById("sb-collapse");
    if (toggle) {
      toggle.title = collapsed ? "Desplegar el menú" : "Plegar el menú";
      toggle.setAttribute("aria-label", toggle.title);
      toggle.setAttribute("aria-expanded", collapsed ? "false" : "true");
    }

    try {
      localStorage.setItem(KEY, collapsed ? "1" : "0");
    } catch (e) {
      /* modo privado: el plegado dura solo esta sesion */
    }
  }

  function toggle() {
    const sidebar = document.getElementById("sidebar");
    if (!sidebar) return;
    setCollapsed(!sidebar.classList.contains("is-collapsed"));
  }

  function init() {
    const btn = document.getElementById("sb-collapse");
    if (btn) btn.addEventListener("click", toggle);

    let guardada = "0";
    try {
      guardada = localStorage.getItem(KEY) || "0";
    } catch (e) {
      /* sin persistencia: se queda desplegado */
    }
    setCollapsed(guardada === "1");
  }

  return { init, setCollapsed, toggle };
})();

export { Sidebar };
