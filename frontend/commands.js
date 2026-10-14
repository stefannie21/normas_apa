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
    // Deshacer y rehacer los lleva el historial de la aplicacion: el del
    // navegador se vacia en cuanto el documento se repagina o se marca.
    if (cmd === "undo") return window.History && window.History.undo();
    if (cmd === "redo") return window.History && window.History.redo();
    // La sangria NO puede pasar por execCommand: el navegador envuelve el
    // contenido en <blockquote> y, como #page esta partido en hojas, arrastra
    // la hoja entera dentro: el documento se parte en dos paginas y dos
    // sangrias dejan un blockquote dentro de otro. Se ajusta el bloque.
    if (cmd === "indent") return applyIndent(1);
    if (cmd === "outdent") return applyIndent(-1);
    focusPage();
    try {
      document.execCommand("styleWithCSS", false, true);
      document.execCommand(cmd, false, null);
    } catch (e) {
      /* comando no soportado por el navegador */
    }
    refresh();
  }

  // El mismo paso que usa el formato base APA (sangria de primera linea).
  var INDENT_STEP_CM = 1.27;
  var unitCache = {};

  // Convierte cualquier longitud CSS a pixeles. marginLeft puede venir de la
  // propia cadena escrita antes (px, cm, in, em…), no solo de la hoja de estilos.
  function toPx(value, unit) {
    if (!unit || unit === "px") return value;
    var key = value + unit;
    if (unitCache[key] !== undefined) return unitCache[key];
    var probe = document.createElement("div");
    probe.style.cssText =
      "position:absolute;visibility:hidden;height:0;margin-left:" + key;
    document.body.appendChild(probe);
    var px = parseFloat(window.getComputedStyle(probe).marginLeft) || 0;
    document.body.removeChild(probe);
    unitCache[key] = px;
    return px;
  }

  function currentIndentPx(el) {
    var raw = el.style.marginLeft;
    if (!raw) return 0;
    var m = /(-?[\d.]+)\s*(px|cm|mm|in|pt|pc|em|rem|%)?/.exec(raw);
    if (!m) return 0;
    var n = parseFloat(m[1]);
    if (isNaN(n)) return 0;
    return toPx(n, m[2]);
  }

  // direction: +1 aumenta sangria, -1 la reduce.
  // Solo se toca el parrafo bajo el cursor o el seleccionado: al contrario que
  // la fuente o el interlineado, aqui no tiene sentido aplicarlo a todo el
  // documento, porque pulsarlo sin seleccion moveria la tesis entera.
  function applyIndent(direction) {
    var blocks = selectedBlocks();
    if (!blocks.length) return false;
    var step = toPx(INDENT_STEP_CM, "cm");
    blocks.forEach(function (el) {
      var next = currentIndentPx(el) + (direction > 0 ? step : -step);
      if (next < 0) next = 0;
      // Al volver a cero se borra la propiedad para que el bloque recupere el
      // valor de la hoja de estilos, en vez de dejar un "0px" en linea.
      if (next < step / 2) el.style.removeProperty("margin-left");
      else el.style.marginLeft = Math.round(next) + "px";
    });
    // Cada pulsacion es un paso propio de deshacer, y no se agrupa con la
    // siguiente: repetirla cuatro veces se deshace cuatro veces.
    if (window.History && window.History.flush) window.History.flush();
    return true;
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
    applyIndent,
    focusPage,
    refresh,
    contentBlocks,
    selectedBlocks,
  };
})();