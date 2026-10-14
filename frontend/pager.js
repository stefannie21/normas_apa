/* Paginacion estilo Word: divide el flujo continuo en hojas apiladas respetando
   la geometria de cada seccion del documento (vertical u horizontal, tamaño y margenes).
   - Divide parrafos por lineas al final de cada hoja.
   - Titulos, tablas e imagenes NO se separan (se mueven a la siguiente hoja).
   - Respeta saltos de pagina manuales (div.page-break). */
(function () {
  "use strict";

  const DEFAULT_SECTION = {
    width_in: 8.5,
    height_in: 11,
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
      landscape: !!s.landscape,
    };
  }

  function getMeasurer(root) {
    if (!measurer || !measurer.isConnected) {
      measurer = document.createElement("div");
      measurer.style.cssText =
        "position:absolute;left:-12000px;top:0;visibility:hidden;pointer-events:none;z-index:-1;";
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
    let h = clone.offsetHeight;
    const cs = getComputedStyle(clone);
    h += parseFloat(cs.marginTop || 0) + parseFloat(cs.marginBottom || 0);
    m.removeChild(clone);
    return h;
  }

  function wordsOf(el) {
    return (el.textContent || "").trim().split(/\s+/).filter(Boolean);
  }

  // Escala una imagen para que quepa dentro del area util de la hoja (como Word).
  function scaleImage(img, g) {
    const natW = img.naturalWidth || img.width || 0;
    const natH = img.naturalHeight || img.height || 0;
    if (!natW || !natH) return false;
    const before = img.style.width + "x" + img.style.height;
    let w = natW;
    let h = natH;
    if (w > g.contentW) {
      w = g.contentW;
      h = (natH * g.contentW) / natW;
    }
    if (h > g.contentH) {
      h = g.contentH;
      w = (natW * g.contentH) / natH;
    }
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

  function textKey(el) {
    return (el.textContent || "")
      .toLowerCase()
      .replace(/[^a-z0-9\u00e0-\u00ff]+/g, " ")
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
    const probe = el.cloneNode(false);
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
    sheet.style.width = g.width + "px";
    sheet.style.minHeight = g.height + "px";
    sheet.style.paddingTop = g.padTop + "px";
    sheet.style.paddingBottom = g.padBottom + "px";
    sheet.style.paddingLeft = g.padLeft + "px";
    sheet.style.paddingRight = g.padRight + "px";
    // no se marca contentEditable: #page es el unico host de edicion, asi el
    // historial de deshacer (Ctrl+Z) del navegador cubre todo el documento
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
    let sectionIndex = 0;
    let g = geoms[0];
    currentGeomRef = g;

    const nextSheet = () => {
      sheet = makeSheet(root, g, sectionIndex);
      used = 0;
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
        if (sheet && (sheet.children.length > 1 || used > MIN_BREAK_PX)) nextSheet();
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

      let h = measureNode(unit, g.contentW);
      if (h > g.contentH && imagesOf(unit).length) {
        for (let i = 0; i < 8 && h > g.contentH; i++) {
          shrinkImages(unit, (g.contentH / h) * 0.97);
          h = measureNode(unit, g.contentW);
        }
      }
      if (used + h <= g.contentH) {
        sheet.appendChild(unit);
        used += h;
        return;
      }
      // No cabe en la hoja actual.
      const spaceLeft = g.contentH - used;
      if (used > MIN_BREAK_PX && isSplittable(unit) && spaceLeft > 8) {
        const k = maxWordsThatFit(unit, spaceLeft, g.contentW);
        if (k > 0) {
          const cut = splitParagraph(unit, k);
          if (cut) {
            sheet.appendChild(cut.head);
            nextSheet();
            placeUnit(cut.tail);
            return;
          }
        }
      }
      // Hoja actual casi vacia o unidad no divisible: pasar a hoja nueva.
      nextSheet();
      h = measureNode(unit, g.contentW);
      if (h > g.contentH && isSplittable(unit)) {
        const k = maxWordsThatFit(unit, g.contentH, g.contentW);
        if (k > 0) {
          const cut = splitParagraph(unit, k);
          if (cut) {
            sheet.appendChild(cut.head);
            nextSheet();
            placeUnit(cut.tail);
            return;
          }
        }
      }
      sheet.appendChild(unit);
      used = h;
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
function toFlowHtml(root) {
    return collectUnits(root)
      .map((el) => el.outerHTML)
      .join("");
  }

  window.Pager = { paginate, textOf, refit, toFlowHtml };
})();