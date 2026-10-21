/* Comandos de edicion del documento. Independientes de la interfaz: los usa
     el panel lateral y tambien funcionan si en el futuro se anade una barra. */
import { History } from "./history.js";

const Commands = (function () {
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
    if (cmd === "undo") return History.undo();
    if (cmd === "redo") return History.redo();
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
    if (History.flush) History.flush();
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

  /* ---------- Estado de la cinta ----------
     Como en Word, los controles reflejan el texto que hay seleccionado:
     la fuente, el tamano, el interlineado y el estilo. Si la seleccion es
     heterogenea se deja el desplegable en blanco (selectedIndex = -1), que es
     como lo hace Word, en vez de mentir con el valor de un solo parrafo. */

  const FONT_ALIAS = {
    "times new roman": "Times New Roman",
    calibri: "Calibri",
    arial: "Arial",
    georgia: "Georgia",
    "lucida sans unicode": "Lucida Sans Unicode",
    "computer modern": "Computer Modern",
  };

  // Primer nombre de fuente real de un valor de font-family ("A", serif).
  function firstFamily(value) {
    const first = String(value || "").split(",")[0].trim().replace(/^["']|["']$/g, "");
    return FONT_ALIAS[first.toLowerCase()] || first;
  }

  // Normaliza a puntos. El estilo en linea viene en "12pt" y el computado en
  // pixeles ("16px"), y 12 != 16: hay que distinguir las unidades o el tamano
  // sale cambiado.
  function toPt(value) {
    const s = String(value || "").trim();
    const n = parseFloat(s);
    if (isNaN(n)) return null;
    if (/pt$/i.test(s)) return n;
    return (n / 96) * 72;
  }

  // Valor comun a todos los bloques, o null si difieren.
  function commonValue(blocks, read) {
    let first = null;
    for (const b of blocks) {
      const v = read(b);
      if (v == null) continue;
      if (first == null) first = v;
      else if (first !== v) return null;
    }
    return first;
  }

  // Fija un desplegable al valor del texto seleccionado. Si ese valor no esta
  // entre las opciones se agrega temporalmente y se muestra, que es lo que hace
  // Word: asi se ve que el texto usa "Courier New" en vez de una fuente APA, en
  // lugar de dejar el desplegable vacio sin explicación.
  function setSelect(sel, value) {
    if (!sel) return;
    // se limpian las opciones temporales de la pasada anterior
    Array.prototype.slice
      .call(sel.querySelectorAll("option[data-temp]"))
      .forEach((o) => o.remove());
    if (value == null) {
      sel.selectedIndex = -1;
      return;
    }
    const target = String(value);
    let i = Array.prototype.findIndex.call(sel.options, (o) => o.value === target);
    if (i === -1) {
      const o = document.createElement("option");
      o.value = target;
      o.textContent = target;
      o.dataset.temp = "1";
      sel.appendChild(o);
      i = sel.options.length - 1;
    }
    sel.selectedIndex = i;
  }

  const STYLE_BY_TAG = { P: "Normal", LI: "Párrafo de lista", H1: "Título 1", H2: "Título 2", H3: "Título 3" };

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

    const blocks = selectedBlocks();
    if (!blocks.length) {
      // sin seleccion se vuelve al valor con el que se dibuja la cinta, no al
      // primero de la lista (que en el tamano seria 8, no el 12 por defecto)
      ["fontName", "fontSize", "lineHeight", "style"].forEach((cmd) => {
        const sel = document.querySelector('.rselect[data-cmd="' + cmd + '"]');
        if (!sel) return;
        if (sel.dataset.touched === "1") return;
        setSelect(sel, sel.dataset.default != null ? sel.dataset.default : sel.options[0] && sel.options[0].value);
      });
      return;
    }

    const fuente = commonValue(blocks, (b) =>
      firstFamily(b.style.fontFamily || getComputedStyle(b).fontFamily)
    );
    setSelect(document.querySelector('.rselect[data-cmd="fontName"]'), fuente);

    const tamano = commonValue(blocks, (b) => {
      const pt = toPt(b.style.fontSize || getComputedStyle(b).fontSize);
      // 13.02 pt se muestra como 13: el desplegable no admite decimales y una
      // cifra larguisima no ayuda a leerlo
      return pt == null ? null : Math.round(pt);
    });
    // si el tamano no esta en la lista (p. ej. 14 pt) se deja en blanco
    setSelect(document.querySelector('.rselect[data-cmd="fontSize"]'), tamano);

    const interlineado = commonValue(blocks, (b) => {
      const cs = getComputedStyle(b);
      const lh = parseFloat(cs.lineHeight);
      const fs = parseFloat(cs.fontSize);
      if (isNaN(lh) || isNaN(fs) || !fs) return cs.lineHeight === "normal" ? "1" : null;
      const ratio = Math.round((lh / fs) * 100) / 100;
      return Math.abs(ratio - Math.round(ratio)) < 0.05 ? String(Math.round(ratio)) : ratio;
    });
    setSelect(document.querySelector('.rselect[data-cmd="lineHeight"]'), interlineado);

    const estilo = commonValue(blocks, (b) => STYLE_BY_TAG[b.tagName] || null);
    setSelect(document.querySelector('.rselect[data-cmd="style"]'), estilo);
  }

    return {
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

export { Commands };
