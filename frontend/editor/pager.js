/* Paginacion estilo Word: divide el flujo continuo en hojas apiladas respetando
   la geometria de cada seccion del documento (vertical u horizontal, tamaño y margenes).
   - Divide parrafos por lineas al final de cada hoja.
   - Titulos, tablas e imagenes NO se separan (se mueven a la siguiente hoja).
     - Respeta saltos de pagina manuales (div.page-break). */
const Pager = (function () {
  "use strict";

  // Tamano por defecto cuando el .docx no aporta geometria: A4 (21 x 29.7 cm),
  // que es el papel habitual en tesis. Antes caia en Carta (8.5 x 11 in).
  const A4_WIDTH_IN = 8.268;
  const A4_HEIGHT_IN = 11.693;

  const DEFAULT_SECTION = {
    width_in: A4_WIDTH_IN,
    height_in: A4_HEIGHT_IN,
    top_in: 1,
    bottom_in: 1,
    left_in: 1,
    right_in: 1,
    landscape: false,
    first_key: null,
  };
  const MIN_BREAK_PX = 16;

  let measurer = null;

  function toPx(inches) {
    return Math.round(inches * 96 * 100) / 100;
  }

  function geom(section) {
    const s = section || DEFAULT_SECTION;
    return {
      width: toPx(s.width_in),
      height: toPx(s.height_in),
      padTop: toPx(s.top_in),
      padBottom: toPx(s.bottom_in),
      padLeft: toPx(s.left_in),
      padRight: toPx(s.right_in),
      contentW: Math.max(80, toPx(s.width_in - s.left_in - s.right_in)),
      contentH: Math.max(80, toPx(s.height_in - s.top_in - s.bottom_in)),
      landscape: !!(s.is_landscape !== undefined ? s.is_landscape : s.landscape),
    };
  }

  function getMeasurer(root) {
    if (!measurer || !measurer.isConnected) {
      measurer = document.createElement("div");
      measurer.id = "apa-measurer";
      // La hoja se maqueta en flex column, y ahi los margenes de los hijos NO
      // colapsan. Medir el clon dentro de un contenedor block daba alturas
      // menores (los margenes se le escapaban al clon): dos listas salian 14 px
      // mas cortas y la hoja se pasaba de largo.
      measurer.style.cssText =
        "position:absolute;left:-12000px;top:0;visibility:hidden;pointer-events:none;z-index:-1;" +
        "display:flex;flex-direction:column;align-items:stretch;";
      document.body.appendChild(measurer);
    }
    // La fuente se refresca en CADA paginacion: si se congelara con la del primer
    // paginate(), al aplicar el formato APA los cortes de pagina se calcularian
    // con una tipografia que ya no es la del documento.
    const sheet = root.querySelector(".sheet") || root;
    const cs = getComputedStyle(sheet);
    measurer.style.fontFamily = cs.fontFamily;
    measurer.style.fontSize = cs.fontSize;
    measurer.style.lineHeight = cs.lineHeight;
    return measurer;
  }

  function measureNode(el, contentW) {
    const m = getMeasurer(el.closest("#page") || document.getElementById("page"));
    m.style.width = contentW + "px";
    const clone = el.cloneNode(true);
    m.appendChild(clone);
    const h = clone.offsetHeight;
    m.removeChild(clone);
    return h;
  }

  // Alto Y margenes verticales de un bloque, medidos sobre un clon ENGANCHADO
  // al documento.
  //
  // Importa hacerlo asi: mientras se pagina, el bloque todavia esta suelto (se
  // coloca en la hoja despues). Y getComputedStyle NO devuelve nada sobre un
  // elemento desconectado: los margenes salian a 0 y el paginador contaba el
  // documento entero sin ellos. Como al pintar si se aplican, las hojas se
  // desbordaban ~100 px y el texto se salia de la pagina.
  function measureBlock(el, contentW) {
    const m = getMeasurer(el.closest("#page") || document.getElementById("page"));
    m.style.width = contentW + "px";
    const clone = el.cloneNode(true);
    m.appendChild(clone);
    const cs = getComputedStyle(clone);
    const out = {
      h: clone.offsetHeight,
      top: parseFloat(cs.marginTop) || 0,
      bottom: parseFloat(cs.marginBottom) || 0,
    };
    m.removeChild(clone);
    return out;
  }

  // Espacio que hay entre dos bloques consecutivos.
  //
  // Word SUMA el espacio-despues de un parrafo y el espacio-antes del siguiente.
  // CSS, en cambio, los COLAPSA (solo cuenta el mayor de los dos). Por eso el
  // texto salia apelmazado: en una tesis con sa=6 y sb=24, Word deja 30pt de
  // hueco y el visor dejaba 24. Como la hoja se maqueta con flex (cuyos hijos no
  // colapsan sus margenes), aqui tambien se suman.
  function gapBetween(prevBottom, top) {
    return prevBottom + top;
  }

  function wordsOf(el) {
    return (el.textContent || "").trim().split(/\s+/).filter(Boolean);
  }

  // Escala una imagen para que quepa dentro del area util de la hoja (como Word).
  function scaleImage(img, g) {
    // El tamaño con el que el autor colocó la imagen en Word MANDA sobre sus
    // píxeles naturales. Mammoth no traslada <wp:extent> al HTML, así que sin
    // esto una figura declarada a 6 cm se pintaba ocupando toda la caja de
    // texto (y una captura de pantalla, mas grande todavia).
    const CM = 96 / 2.54;
    const declW = Number(img.dataset.docxW || 0);
    const declH = Number(img.dataset.docxH || 0);
    const pxW = img.naturalWidth || img.width || 0;
    const pxH = img.naturalHeight || img.height || 0;
    let w = declW > 0 ? declW * CM : pxW;
    let h = declH > 0 ? declH * CM : pxH;
    if (!w || !h) return false;
    // no se agranda mas alla de la resolucion real: solo se deforma hacia abajo
    if (pxW && w > pxW) { h = (h * pxW) / w; w = pxW; }
    const ratio = h / w;
    const before = img.style.width + "x" + img.style.height;
    if (w > g.contentW) { w = g.contentW; h = w * ratio; }
    if (h > g.contentH) { h = g.contentH; w = h / ratio; }
    const newW = Math.max(40, Math.round(w));
    const newH = Math.max(40, Math.round(h));
    img.style.width = newW + "px";
    img.style.height = newH + "px";
    img.dataset.fitW = String(newW);
    img.dataset.fitH = String(newH);
    return before !== newW + "x" + newH;
  }

  // Reduce las imagenes de un bloque cuando, pese a ajustarlas, el bloque no cabe
  // (por ejemplo, por los margenes del parrafo que las contiene).
  function shrinkImages(el, factor) {
    imagesOf(el).forEach((img) => {
      const w = Number(img.dataset.fitW || 0);
      const h = Number(img.dataset.fitH || 0);
      if (!w || !h) return;
      const nw = Math.max(40, Math.round(w * factor));
      const nh = Math.max(40, Math.round(h * factor));
      img.style.width = nw + "px";
      img.style.height = nh + "px";
      img.dataset.fitW = String(nw);
      img.dataset.fitH = String(nh);
    });
  }

  function imagesOf(el) {
    if (!el || el.nodeType !== 1) return [];
    if (el.tagName === "IMG") return [el];
    return Array.from(el.querySelectorAll("img"));
  }

  // Ajusta las imagenes del bloque y avisa si alguna cambio de tamaño.
  function fitImages(el, g) {
    let changed = false;
    imagesOf(el).forEach((img) => {
      if (img.complete && img.naturalWidth) {
        if (scaleImage(img, g)) changed = true;
      } else if (!img.dataset.fitBound) {
        img.dataset.fitBound = "1";
        img.addEventListener("load", () => scaleImage(img, currentGeom()), { once: true });
      }
    });
    return changed;
  }

  let lastSections = null;
  let currentGeomRef = null;
  function currentGeom() {
    return currentGeomRef || geom(DEFAULT_SECTION);
  }

  // Debe producir EXACTAMENTE la misma clave que routes._text_key del backend
  // (NFKD + sin diacriticos). Antes solo quitaba los signos de puntuacion y se
  // quedaba con los acentos: "investigación" != "investigacion", de modo que
  // NUNCA encontraba el primer parrafo de una seccion y los capitulos no
  // empeazaban en pagina nueva como en Word.
  function textKey(el) {
    return (el.textContent || "")
      .normalize("NFKD")
      .replace(/[\u0300-\u036f]/g, "")
      .toLowerCase()
      .replace(/[^\p{L}\p{N}]+/gu, " ")
      .trim()
      .slice(0, 48);
  }

  function isPageBreak(el) {
    return el && el.nodeType === 1 && el.classList.contains("page-break");
  }

  function isSplittable(el) {
    if (!el || el.nodeType !== 1) return false;
    if (!/^(P|DIV)$/.test(el.tagName)) return false;
    // el indice y los bloques con contenido estructurado nunca se parten
    if (el.classList && el.classList.contains("doc-toc")) return false;
    if (el.querySelector("img,table,li,p,h1,h2,h3,h4,ul,ol,hr")) return false;
    return wordsOf(el).length > 3;
  }

  // Mayor k tal que las primeras k palabras del elemento caben en limitPx.
  function maxWordsThatFit(el, limitPx, contentW) {
    const total = wordsOf(el).length;
    if (!total) return 0;
    // cloneNode(false) se lleva el estilo en LINEA (interlineado, tamano de
    // letra). Sin el, la sonda se mide con el interlineado normal del
    // navegador, mucho mas estrecho que el real, y caben mas lineas de las que
    // caben de verdad: el trozo que se queda en la hoja se salia de la pagina.
    const probe = el.cloneNode(false);
    probe.setAttribute("style", el.getAttribute("style") || "");
    let lo = 1, hi = total, best = 0;
    while (lo <= hi) {
      const mid = (lo + hi) >> 1;
      probe.textContent = wordsOf(el).slice(0, mid).join(" ");
      if (measureNode(probe, contentW) <= limitPx) {
        best = mid;
        lo = mid + 1;
      } else {
        hi = mid - 1;
      }
    }
    return best;
  }

  // Corta un parrafo en head [palabras 0..k) y tail [k..total), conservando
  // el formato (strong/em/span) de los tramos no recortados.
  function splitParagraph(el, k) {
    const words = wordsOf(el);
    if (k <= 0 || k >= words.length) return null;

    const nodes = [];
    const tw = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
    while (tw.nextNode()) if (tw.currentNode.data.trim()) nodes.push(tw.currentNode);

    let seen = 0, cutIdx = -1, cutJ = 0;
    for (let i = 0; i < nodes.length; i++) {
      const w = wordsOf(nodes[i]).length;
      if (seen + w >= k) { cutIdx = i; cutJ = k - seen; break; }
      seen += w;
    }
    if (cutIdx < 0) return null;

    const makePart = (part) => {
      const node = el.cloneNode(true);
      const cs = [];
      const cw = document.createTreeWalker(node, NodeFilter.SHOW_TEXT);
      while (cw.nextNode()) if (cw.currentNode.data.trim()) cs.push(cw.currentNode);
      cs.forEach((t, i) => {
        if (i < cutIdx) {
          if (part === "tail") t.data = "";
        } else if (i === cutIdx) {
          const wl = wordsOf(t).length;
          if (part === "head") t.data = wl ? wordsOf(t).slice(0, cutJ).join(" ") : "";
          else t.data = wl > cutJ ? wordsOf(t).slice(cutJ).join(" ") : "";
        } else if (part === "head") {
          t.data = "";
        }
      });
      return node;
    };
    return { head: makePart("head"), tail: makePart("tail") };
  }

  // Una tabla que no cabe en una hoja se parte por filas, como hace Word, y la
  // continuacion repite la fila de cabecera. Sin esto una tabla larga (por
  // ejemplo la de actividades de un cronograma) estiraba la hoja y el texto se
  // salia fuera del papel.
  function buildTable(tbl, headCount, from, to, withHead) {
    const out = tbl.cloneNode(false);
    out.innerHTML = "";
    const src = Array.prototype.slice.call(tbl.rows);
    // caption y colgroup se conservan: el colgroup fija el ancho de las columnas
    Array.prototype.forEach.call(tbl.children, function (c) {
      if (c.tagName === "CAPTION" || c.tagName === "COLGROUP") {
        out.appendChild(c.cloneNode(true));
      }
    });
    if (withHead && headCount > 0) {
      const thead = document.createElement("thead");
      for (let i = 0; i < headCount; i++) thead.appendChild(src[i].cloneNode(true));
      out.appendChild(thead);
    }
    const tbody = document.createElement("tbody");
    for (let i = from; i < to; i++) tbody.appendChild(src[i].cloneNode(true));
    out.appendChild(tbody);
    return out;
  }

  function splitTable(tbl, maxPx, contentW) {
    const src = Array.prototype.slice.call(tbl.rows);
    const headCount = tbl.tHead ? tbl.tHead.rows.length : 0;
    const bodyCount = src.length - headCount;
    // con una sola fila de cuerpo no hay nada que repartir
    if (bodyCount < 2) return null;
    let lo = 1, hi = bodyCount, best = 0;
    while (lo <= hi) {
      const mid = (lo + hi) >> 1;
      const probe = buildTable(tbl, headCount, headCount, headCount + mid, false);
      if (measureNode(probe, contentW) <= maxPx) {
        best = mid;
        lo = mid + 1;
      } else {
        hi = mid - 1;
      }
    }
    // si cabe entera o no cabe ni una fila, no se parte
    if (!best || best >= bodyCount) return null;
    return {
      head: buildTable(tbl, headCount, headCount, headCount + best, false),
      tail: buildTable(tbl, headCount, headCount + best, src.length, true),
    };
  }

  // El indice generado se parte por entradas. Es un unico bloque, asi que sin
  // esto una tabla de contenidos larga estiraba la hoja.
  function splitToc(toc, maxPx, contentW) {
    const entries = Array.prototype.slice.call(toc.children);
    if (entries.length < 2) return null;
    const build = (from, to) => {
      const c = toc.cloneNode(false);
      for (let i = from; i < to; i++) c.appendChild(entries[i].cloneNode(true));
      return c;
    };
    let lo = 1, hi = entries.length, best = 0;
    while (lo <= hi) {
      const mid = (lo + hi) >> 1;
      if (measureNode(build(0, mid), contentW) <= maxPx) {
        best = mid;
        lo = mid + 1;
      } else {
        hi = mid - 1;
      }
    }
    if (!best || best >= entries.length) return null;
    return { head: build(0, best), tail: build(best, entries.length) };
  }

  // Reparte una unidad que no cabe en limitePx. Cada tipo se corta por su
  // naturaleza: el indice por entradas, una tabla por filas y un parrafo por
  // palabras. Devuelve null si no se puede partir.
  function splitUnit(unit, limitPx, contentW) {
    if (!unit || unit.nodeType !== 1) return null;
    if (limitPx <= 0) return null;
    if (unit.classList && unit.classList.contains("doc-toc")) {
      return splitToc(unit, limitPx, contentW);
    }
    if (unit.tagName === "TABLE") return splitTable(unit, limitPx, contentW);
    if (unit.tagName === "OL" || unit.tagName === "UL") return splitList(unit, limitPx, contentW);
    if (isSplittable(unit)) {
      const k = maxWordsThatFit(unit, limitPx, contentW);
      if (k > 0) return splitParagraph(unit, k);
    }
    return null;
  }

  // Una lista que no cabe se parte por items, igual que una tabla por filas.
  function splitList(list, maxPx, contentW) {
    const items = Array.prototype.slice.call(list.children).filter(
      (c) => c.tagName === "LI"
    );
    if (items.length < 2) return null;
    const build = (from, to, withStart) => {
      const c = list.cloneNode(false);
      c.innerHTML = "";
      if (withStart && list.tagName === "OL") {
        // la numeracion debe continuar donde se dejo
        const n = list.start ? Number(list.start) : 1;
        c.setAttribute("start", String(n + from));
      }
      for (let i = from; i < to; i++) c.appendChild(items[i].cloneNode(true));
      return c;
    };
    let lo = 1, hi = items.length, best = 0;
    while (lo <= hi) {
      const mid = (lo + hi) >> 1;
      if (measureNode(build(0, mid, false), contentW) <= maxPx) {
        best = mid;
        lo = mid + 1;
      } else {
        hi = mid - 1;
      }
    }
    if (!best || best >= items.length) return null;
    return { head: build(0, best, false), tail: build(best, items.length, true) };
  }

  function collectUnits(root) {
    const units = [];
    // Se recorre en orden de documento: dentro de cada hoja se toman sus bloques
    // (sin el numero) y ademas cualquier elemento suelto en #page (por ejemplo un
    // indice recien generado que se antepuso antes de las hojas: si se ignorara,
    // el siguiente paginate() lo borraria).
    Array.from(root.children).forEach((child) => {
      if (child.classList && child.classList.contains("sheet")) {
        Array.from(child.children).forEach((c) => {
          if (c.classList.contains("sheet-num")) return;
          units.push(c);
        });
      } else {
        units.push(child);
      }
    });
    return units;
  }

  function makeSheet(root, g, sectionIndex) {
    const sheet = document.createElement("div");
    sheet.className = "sheet" + (g.landscape ? " landscape" : "");
    sheet.dataset.section = String(sectionIndex);
    sheet.style.setProperty("--content-h", g.contentH + "px");
    // el CSS fuerza el tamano de las hojas horizontales con !important: se le
    // pasa el ancho y alto reales de la seccion para que no sea un valor fijo
    sheet.style.setProperty("--landscape-w", g.width + "px");
    sheet.style.setProperty("--landscape-h", g.height + "px");
    sheet.style.width = g.width + "px";
    sheet.style.minHeight = g.height + "px";
    sheet.style.paddingTop = g.padTop + "px";
    sheet.style.paddingBottom = g.padBottom + "px";
    sheet.style.paddingLeft = g.padLeft + "px";
    sheet.style.paddingRight = g.padRight + "px";
    // no se marca contentEditable: #page es el unico host de edicion
    root.appendChild(sheet);
    return sheet;
  }

  function paginate(root, sections) {
    if (!root) return;
    const units = collectUnits(root);
    root.innerHTML = "";

    lastSections = sections && sections.length ? sections : null;
    const list = lastSections || [DEFAULT_SECTION];
    const geoms = list.map(geom);
    const keyToSection = {};
    list.forEach((s, i) => {
      if (s && s.first_key) keyToSection[s.first_key] = i;
    });

    const m = getMeasurer(root);
    m.innerHTML = "";

    let sheet = null;
    let used = 0;
    // margen inferior del ultimo bloque colocado: se necesita para saber cuanto
    // se junta (colapsa) con el margen superior del siguiente
    let lastBottom = 0;
    let sectionIndex = 0;
    let g = geoms[0];
    currentGeomRef = g;

    const nextSheet = () => {
      sheet = makeSheet(root, g, sectionIndex);
      used = 0;
      lastBottom = 0;
    };

    // cada bloque conserva la seccion a la que pertenece
    function resolveSection(unit) {
      if (unit.dataset && unit.dataset.section !== undefined && unit.dataset.section !== "") {
        return Number(unit.dataset.section);
      }
      let sec = sectionIndex;
      const k = textKey(unit);
      if (k && keyToSection[k] !== undefined && keyToSection[k] >= sec) sec = keyToSection[k];
      if (unit.dataset) unit.dataset.section = String(sec);
      return sec;
    }

    function placeUnit(unit) {
      if (isPageBreak(unit)) {
        const enEsta = sheet
          ? Array.prototype.filter.call(
              sheet.children,
              (c) => !c.classList.contains("sheet-num") && !c.classList.contains("page-break")
            ).length
          : 0;
        // El salto se CONSERVA en el flujo, al final de la hoja que termina.
        // Antes se descartaba y, en cuanto se repaginaba (recarga de imagenes,
        // ajuste de estilos, Ctrl+Z...) todos los saltos de pagina del .docx
        // desaparecian para siempre y el documento se rearmaba solo.
        const corta = !!sheet && (enEsta > 1 || used > MIN_BREAK_PX);
        if (!sheet) nextSheet();
        sheet.appendChild(unit);
        if (corta) nextSheet();
        used = 0;
        lastBottom = 0;
        return;
      }
      const sec = resolveSection(unit);
      if (sec !== sectionIndex) {
        sectionIndex = sec;
        g = geoms[Math.min(sec, geoms.length - 1)];
        currentGeomRef = g;
        nextSheet();
      }
      if (!sheet) nextSheet();

      // las imagenes se ajustan al area util antes de medir
      fitImages(unit, g);

      let blk = measureBlock(unit, g.contentW);
      let h = blk.h;
      if (h > g.contentH && imagesOf(unit).length) {
        for (let i = 0; i < 8 && h > g.contentH; i++) {
          shrinkImages(unit, (g.contentH / h) * 0.97);
          blk = measureBlock(unit, g.contentW);
          h = blk.h;
        }
      }

      // Espacio que ocupa el bloque respetando el colapso de margenes: entre el
      // bloque anterior y este solo cuenta el mayor de los dos margenes.
      const need = used - lastBottom + gapBetween(lastBottom, blk.top) + h;

      if (need + blk.bottom <= g.contentH) {
        sheet.appendChild(unit);
        used = need + blk.bottom;
        lastBottom = blk.bottom;
        return;
      }
      // No cabe en la hoja actual: primero se intenta llenar el hueco que
      // queda, y si no, cambiar de hoja y repetir alli.
      const intentarCorte = (limitePx) => {
        // El trozo que se queda en esta hoja conserva el margen inferior del
        // bloque original: hay que reservarlo o la cabeza se cuela por debajo
        // del margen y la hoja se alarga.
        const cut = splitUnit(unit, limitePx - blk.bottom, g.contentW);
        if (!cut) return false;
        sheet.appendChild(cut.head);
        nextSheet();
        placeUnit(cut.tail);
        return true;
      };

      const spaceLeft = g.contentH - used - gapBetween(lastBottom, blk.top);
      if (used > MIN_BREAK_PX && spaceLeft > 8 && intentarCorte(spaceLeft)) return;

      // Hoja actual casi vacia o unidad no divisible: pasar a hoja nueva.
      nextSheet();
      blk = measureBlock(unit, g.contentW);
      h = blk.h;
      if (h > g.contentH && intentarCorte(g.contentH - gapBetween(0, blk.top))) return;

      sheet.appendChild(unit);
      used = blk.top + h + blk.bottom;
      lastBottom = blk.bottom;
    }

    units.forEach(placeUnit);
    if (!sheet) nextSheet();

    // numerar hojas
    Array.from(root.querySelectorAll(".sheet")).forEach((s, i) => {
      let num = s.querySelector(".sheet-num");
      if (!num) {
        num = document.createElement("span");
        num.className = "sheet-num";
        s.appendChild(num);
      }
      num.contentEditable = "false";
      num.textContent = String(i + 1);
    });
  }

  function textOf(root) {
    return Array.from(root.querySelectorAll(".sheet"))
      .map((s) =>
        Array.from(s.children)
          .filter((c) => !c.classList.contains("sheet-num"))
          .map((c) => c.innerText || "")
          .join("\n")
      )
      .join("\n");
  }

  // Reajusta imagenes que terminaban de cargar despues de la paginacion inicial.
  function refit(root) {
    if (!root || !root.querySelector(".sheet")) return false;
    let changed = false;
    root.querySelectorAll(".sheet").forEach((s) => {
      const sec = Number(s.dataset.section || 0);
      const g = geom((lastSections && lastSections[sec]) || DEFAULT_SECTION);
      Array.from(s.children).forEach((c) => {
        if (c.classList.contains("sheet-num")) return;
        if (fitImages(c, g)) changed = true;
      });
    });
    return changed;
  }

  // Devuelve el contenido en orden de documento, sin las marcas de hoja:
  // sirve para guardar la sesion y volver a maquetar al restaurar.
  // skipSelector permite excluir lo que se regenera al cargar (el indice): si se
  // guarda, al restaurar buildIndex() genera otro encima y el indice se ve
  // duplicado.
  function toFlowHtml(root, skipSelector) {
    return collectUnits(root)
      .filter((el) => !(skipSelector && el.matches && el.matches(skipSelector)))
      .map((el) => el.outerHTML)
      .join("");
  }

  return { paginate, textOf, refit, toFlowHtml };
})();

export { Pager };
