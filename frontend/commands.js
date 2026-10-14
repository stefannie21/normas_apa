/* Comandos de edicion del documento. Independientes de la interfaz: los usa
   el panel lateral y tambien funcionan si en el futuro se anade una barra. */
(function () {
  "use strict";

  function page() {
    return document.getElementById("page");
  }

  function focusPage() {
    const p = page();
    if (p && !p.isContentEditable) p.contentEditable = "true";
    if (p) p.focus();
  }

  function exec(cmd) {
    focusPage();
    try {
      document.execCommand("styleWithCSS", false, true);
      document.execCommand(cmd, false, null);
    } catch (e) {
      /* comando no soportado por el navegador */
    }
    refresh();
  }

  function applyColor(prop, value) {
    focusPage();
    document.execCommand("styleWithCSS", false, true);
    document.execCommand(prop, false, value);
    refresh();
  }

  // Bloques de contenido reales: nunca las hojas, el numero de pagina ni el indice.
// (Tomar #page.children sin mas devolvia las .sheet completas y Applying un estilo
//  sin seleccion habria destruido el documento entero.)
function contentBlocks() {
    const p = page();
    if (!p) return [];
    return Array.from(p.querySelectorAll("p,h1,h2,h3,h4,h5,h6,li,blockquote,div")).filter((el) => {
      if (el.classList.contains("sheet")) return false;
      if (el.classList.contains("sheet-num")) return false;
      if (el.classList.contains("doc-toc")) return false;
      // solo los bloques que no contienen otros bloques
      return !el.querySelector("p,h1,h2,h3,h4,h5,h6,li,blockquote,.sheet");
    });
  }

  function selectedBlocks() {
    const p = page();
    if (!p) return [];
    const sel = window.getSelection();
    if (!sel || !sel.rangeCount || !p.contains(sel.anchorNode)) return [];
    const range = sel.getRangeAt(0);
    const blocks = Array.from(p.querySelectorAll("p,h1,h2,h3,h4,h5,h6,li,blockquote")).filter(
      (el) => range.intersectsNode(el) && !el.classList.contains("sheet-num")
    );
    if (blocks.length) return blocks;
    const walk = sel.anchorNode.nodeType === 1 ? sel.anchorNode : sel.anchorNode.parentElement;
    return walk && walk !== p && p.contains(walk) ? [walk] : [];
  }

  // Aplica una propiedad de estilo a los bloques del documento (no a los runs).
  function applyToBlocks(prop, value) {
    const blocks = selectedBlocks();
    const targets = blocks.length ? blocks : contentBlocks();
    targets.forEach((b) => (b.style[prop] = value));
  }

  function applyFontFamily(value) {
    applyToBlocks("fontFamily", /[a-zA-Z]/.test(value) && !/^["']/.test(value) ? "'" + value + "'" : value);
  }

  function applyFontSize(value) {
    applyToBlocks("fontSize", value + "pt");
  }

  function refresh() {
    document.querySelectorAll("[data-toggle='1']").forEach((btn) => {
      let state = false;
      try {
        state = document.queryCommandState(btn.dataset.cmd);
      } catch (e) {
        state = false;
      }
      btn.classList.toggle("on", state);
    });
  }

  window.Commands = {
    exec,
    applyColor,
    applyToBlocks,
    applyFontFamily,
    applyFontSize,
    focusPage,
    refresh,
    contentBlocks,
    selectedBlocks,
  };
})();