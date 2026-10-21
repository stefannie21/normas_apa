/* Correcciones automaticas SOLO de tipo mecanico y reversible.

Regla del proyecto: la IA no escribe en el documento y aqui tampoco se
corrige nada semantico (anios, autores, contenido). Solo formato ypunctuation
  que se pueden aplicar con certeza y deshacer.
  */
const Fixer = (function () {
  "use strict";

  const IN = 96; // px por pulgada

  // ------------------------------------------------------------- utilidades
  function root() {
    return document.getElementById("page");
  }

  /* ---------- Ambito ----------
     `ctx.el` acota la correccion al bloque donde se pulso "Corregir esto".
     Sin el (corrector del panel, o documento entero) el ambito es #page. */
  function scopeOf(ctx) {
    return (ctx && ctx.el) || root();
  }

  // Titulos validos de la lista de referencias. Se replica la normalizacion
  // del backend (_find_references_start) para que el corrector marque la
  // MISMA lista que el verificador: minusculas, sin el numero inicial
  // ("6. REFERENCIAS"), sin signos y sin las palabras "apa"/"bibliografica".
  const REFS_TITLES = new Set([
    "referencias",
    "referencias bibliograficas",
    "referencias bibliográficas",
    "bibliografia",
    "bibliografía",
    "references",
    "lista de referencias",
  ]);

  function isRefsTitle(text) {
    let t = String(text || "")
      .trim()
      .toLowerCase()
      .replace(/\s+/g, " ");
    t = t.replace(/^[\d]+[.)]\s*/, "");
    t = t.replace(/^[ .:\-–—]+/, "").replace(/[ .:\-–—]+$/, "");
    t = t.replace(/\b(apa|bibliografica|bibliograficas|bibliografico)\b/g, " ");
    t = t.replace(/\s+/g, " ").trim();
    return REFS_TITLES.has(t);
  }

  // nodos que coinciden con el selector DENTRO del ambito (incluido el mismo)
  function scopeNodes(ctx, selector) {
    const base = scopeOf(ctx);
    const p = root();
    if (!p || !base) return [];
    if (base === p) return Array.from(p.querySelectorAll(selector));
    const out = [];
    if (base.matches && base.matches(selector)) out.push(base);
    Array.from(base.querySelectorAll(selector)).forEach((el) => out.push(el));
    return out;
  }

  function allBlocks(ctx) {
    const p = root();
    if (!p) return [];
    return scopeNodes(ctx, "p,h1,h2,h3,h4,h5,h6,li,blockquote").filter(
      (el) => !el.classList.contains("sheet-num") && !el.closest(".doc-toc")
    );
  }

  function isHeading(el) {
    return /^H[1-6]$/.test(el.tagName);
  }

  function isReference(el) {
    const p = root();
    if (!p) return false;
    const nodes = Array.from(p.querySelectorAll("h1,h2,h3,p,li"));
    // Se toma el ULTIMO titulo que coincide, como hace el backend: en una
    // tesis la palabra "referencias" puede aparecer antes (indice, capitulo
    // de introduction...) y con el primero todo el cuerpo del documento
    // contaba como lista de referencias.
    let cut = -1;
    nodes.forEach((node, i) => {
      if (isRefsTitle(node.textContent)) cut = i;
    });
    if (cut < 0) return false;
    return nodes.indexOf(el) > cut;
  }

  function normName(t) {
    return (t || "")
      .toLowerCase()
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "")
      .replace(/[^a-z0-9]+/g, " ")
      .trim();
  }

  // Todas las escrituras pasan por aqui: en modo simulacion se cuentan pero
  // NO se modifica el documento (la vista previa jamas debe alterar el texto).
  let DRY = false;
  function writeStyle(el, prop, value) {
    if (!DRY) el.style[prop] = value;
    return true;
  }
  function writeText(node, text) {
    if (!DRY) node.data = text;
    return true;
  }
  function writeHTML(el, html) {
    if (!DRY) el.innerHTML = html;
    return true;
  }

  function surnameOf(text) {
    let t = (text || "").trim().replace(/^\d+(\.\d+)*[.)]?\s*/, "");
    t = t.split(/\s*[,&;]/)[0];
    t = t.split(/\s+(?:et\s+al|y|and)\s+/i)[0];
    const words = t.trim().split(/\s+/);
    return normName(words[0] || "");
  }

// Envuelve un texto en <em> conservando el resto del formato del elemento.
  function italicize(el, needle) {
    if (!needle) return false;
    const walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
    const nodes = [];
    while (walker.nextNode()) nodes.push(walker.currentNode);
    for (const node of nodes) {
      const i = node.data.indexOf(needle);
      if (i < 0) continue;
      if (DRY) return true;
      const before = node.data.slice(0, i);
      const after = node.data.slice(i + needle.length);
      const em = document.createElement("em");
      em.textContent = needle;
      const frag = document.createDocumentFragment();
      if (before) frag.appendChild(document.createTextNode(before));
      frag.appendChild(em);
      if (after) frag.appendChild(document.createTextNode(after));
      node.parentNode.replaceChild(frag, node);
      return true;
    }
    return false;
  }

  function refType(text) {
    const t = normName(text);
    if (/\b(tesis|thesis|disertacion)\b/.test(t)) return "tesis";
    if (/doi\.org|https?:\/\//.test(t)) return "web";
    if (/\(\d+(,\s*\d+)?\)/.test(t) || /\d+\s*[-–]\s*\d+\s*$/.test(t)) return "articulo";
    if (/\b(editorial|ediciones|press|springer|publishing|s\.a\.|s\.l\.)\b/.test(t)) return "libro";
    if (/\b(capitulo|chapter)\b/.test(t)) return "capitulo";
    return "libro";
  }

  function splitTitleContainer(text) {
    const body = text.replace(/^[^(]*\([^)]*\)\.?\s*/, "");
    const m = body.match(/^(.+?[a-z0-9)\]])\.\s+(.{4,})$/i);
    if (!m) return { title: body.split(".")[0], container: "" };
    return { title: m[1].trim(), container: m[2].trim() };
  }

  // ------------------------------------------------------------ correcciones
  const CORRECTIONS = [
    {
      id: "interlineado",
      label: "Interlineado doble",
      detail: "Fija el interlineado en 2.0 en todo el texto.",
      rules: ["FORMAT-004"],
      apply(ctx) {
        let n = 0;
        allBlocks(ctx).forEach((el) => {
          if (el.style.lineHeight !== "2") {
            writeStyle(el, "lineHeight", "2");
            n++;
          }
        });
        return n;
      },
    },
    {
      id: "espacios",
      label: "Quitar espacio entre párrafos",
      detail: "Deja 0 pt de espacio antes y después de cada párrafo.",
      rules: ["FORMAT-007"],
      apply(ctx) {
        let n = 0;
        allBlocks(ctx).forEach((el) => {
          if (el.style.marginTop !== "0" || el.style.marginBottom !== "0") {
            writeStyle(el, "marginTop", "0");
            writeStyle(el, "marginBottom", "0");
            n++;
          }
        });
        return n;
      },
    },
    {
      id: "sangria",
      label: "Sangría de primera línea (1.27 cm)",
      detail: "Aplica sangría de 0.5 pulgadas a los párrafos del cuerpo.",
      rules: ["FORMAT-006"],
      apply(ctx) {
        let n = 0;
        allBlocks(ctx).forEach((el) => {
          if (el.tagName !== "P" || isHeading(el)) return;
          if (isReference(el)) return;
          if ((el.textContent || "").trim().length < 80) return;
          if (el.style.textIndent !== "0.5in") {
            writeStyle(el, "textIndent", "0.5in");
            n++;
          }
        });
        return n;
      },
    },
    {
      id: "alineacion",
      label: "Alinear a la izquierda",
      detail: "Quita la justificación y alinea a la izquierda (regla APA).",
      rules: ["FORMAT-005"],
      apply(ctx) {
        let n = 0;
        allBlocks(ctx).forEach((el) => {
          if (el.style.textAlign === "justify") {
            writeStyle(el, "textAlign", "left");
            n++;
          }
        });
        return n;
      },
    },
    {
      id: "margenes",
      label: "Márgenes de 2.54 cm",
      detail: "Ajusta los márgenes de cada hoja a 1 pulgada.",
      rules: ["FORMAT-001"],
      // los margenes son de la HOJA, no del parrafo: se corrige la hoja que
      // contiene la marca y el boton avisa de que el alcance es el documento
      scope: "doc",
      apply(ctx) {
        let n = 0;
        const sections = (ctx && ctx.sections) || [];
        const base = scopeOf(ctx);
        const propia = base && base.closest ? base.closest(".sheet") : null;
        const hojas = propia ? [propia] : Array.from(root().querySelectorAll(".sheet"));
        hojas.forEach((sheet, i) => {
          const s = sections[Number(sheet.dataset.section || i)] || {};
          const pad = [s.top_in, s.right_in, s.bottom_in, s.left_in].every(
            (v) => v == null || Math.abs(v - 1) < 0.1
          );
          if (pad) return;
          writeStyle(sheet, "paddingTop", "1in");
          writeStyle(sheet, "paddingRight", "1in");
          writeStyle(sheet, "paddingBottom", "1in");
          writeStyle(sheet, "paddingLeft", "1in");
          if (!DRY) sheet.style.setProperty("--content-h", 9 * IN + "px");
          n++;
        });
        return n;
      },
    },
    {
      id: "et-al",
      label: "Corregir 'et al.'",
      detail: "Añade el punto final en las citas con 'et al'.",
      rules: ["CIT-003"],
      apply(ctx) {
        let n = 0;
        scopeNodes(ctx, "p,li").forEach((el) => {
          const walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
          const nodes = [];
          while (walker.nextNode()) nodes.push(walker.currentNode);
          nodes.forEach((node) => {
            const fixed = node.data.replace(/\bet\s?al\b(?!\.)/gi, "et al.");
            if (fixed !== node.data) {
              writeText(node, fixed);
              n++;
            }
          });
        });
        return n;
      },
    },
    {
      id: "ampersand",
      label: "Usar '&' dentro de las citas",
      detail: "Sustituye 'and' o 'y' por '&' dentro de los paréntesis de cita.",
      rules: ["CIT-002"],
      apply(ctx) {
        let n = 0;
        scopeNodes(ctx, "p,li").forEach((el) => {
          const walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
          const nodes = [];
          while (walker.nextNode()) nodes.push(walker.currentNode);
          nodes.forEach((node) => {
            const fixed = node.data.replace(
              /\(([^()]*?)\s+\b(?:and|y)\s+([^()]*?)\)/g,
              (m, a, b) => "(" + a + " & " + b + ")"
            );
            if (fixed !== node.data) {
              writeText(node, fixed);
              n++;
            }
          });
        });
        return n;
      },
    },
    {
      id: "refs-sangria",
      label: "Sangría francesa en las referencias",
      detail: "Aplica la sangría francesa de 1.27 cm a cada referencia.",
      rules: ["REF-002"],
      apply(ctx) {
        let n = 0;
        allBlocks(ctx).forEach((el) => {
          if (!isReference(el) || isHeading(el)) return;
          if (el.style.textIndent === "-0.5in" && el.style.marginLeft === "0.5in") return;
          writeStyle(el, "marginLeft", "0.5in");
          writeStyle(el, "textIndent", "-0.5in");
          n++;
        });
        return n;
      },
    },
    {
      id: "refs-orden",
      label: "Ordenar las referencias alfabéticamente",
      detail: "Reordena la lista de referencias por el primer apellido.",
      rules: ["REF-003"],
      // reordenar la lista entera no tiene sentido "por parrafo"
      scope: "doc",
      apply() {
        const p = root();
        if (!p) return 0;
        let titleEl = null;
        p.querySelectorAll("h1,h2,h3").forEach((el) => {
          if (isRefsTitle(el.textContent)) titleEl = el;
        });
        // si el titulo esta escrito como parrafo en negrita y no como
        // encabezado, se busca igual (pero solo si no hay ninguno)
        if (!titleEl) {
          p.querySelectorAll("p").forEach((el) => {
            if (isRefsTitle(el.textContent)) titleEl = el;
          });
        }
        if (!titleEl) return 0;
        const host = titleEl.parentNode;
        const refs = [];
        let node = titleEl.nextElementSibling;
        while (node && !/^H[1-6]$/.test(node.tagName)) {
          if (node.tagName === "P" && (node.textContent || "").trim()) refs.push(node);
          node = node.nextElementSibling;
        }
        if (refs.length < 2) return 0;
        const sorted = refs
          .slice()
          .sort((a, b) => surnameOf(a.textContent).localeCompare(surnameOf(b.textContent)));
        if (sorted.every((el, i) => el === refs[i])) return 0;
        // se reinsertan en su MISMO contenedor para no sacar los parrafos de la hoja
        const anchor = refs[refs.length - 1].nextSibling;
        sorted.forEach((el) => {
          if (!DRY) host.insertBefore(el, anchor);
        });
        return refs.length;
      },
    },
    {
      id: "refs-cursivas",
      label: "Cursivas en las referencias",
      detail: "Cursiva el título (libros/tesis) o el contenedor (artículos).",
      rules: ["REF-006"],
      apply(ctx) {
        let n = 0;
        allBlocks(ctx).forEach((el) => {
          if (!isReference(el) || isHeading(el)) return;
          if (el.querySelector("em, i")) return; // ya tiene cursiva
          const text = el.textContent || "";
          const type = refType(text);
          const { title, container } = splitTitleContainer(text);
          if (!title) return;
          if (type === "articulo" || type === "capitulo") {
            const name = container.split(",")[0].trim();
            if (name && italicize(el, name)) n++;
          } else if (italicize(el, title)) n++;
        });
        return n;
      },
    },
    {
      id: "titulos-formato",
      label: "Formato de los títulos por nivel",
      detail: "Nivel 1 centrado y negrita; niveles 2 y 3 a la izquierda y en negrita (nivel 3 en cursiva).",
      rules: ["HEAD-002"],
      apply(ctx) {
        let n = 0;
        scopeNodes(ctx, "h1,h2,h3").forEach((el) => {
          const level = Number(el.tagName[1]);
          writeStyle(el, "fontWeight", "700");
          if (level === 1) writeStyle(el, "textAlign", "center");
          else writeStyle(el, "textAlign", "left");
          if (level === 3) writeStyle(el, "fontStyle", "italic");
          else writeStyle(el, "fontStyle", "normal");
          n++;
        });
        return n;
      },
    },
  ];

  function available(findings) {
    const rules = new Set((findings || []).map((f) => f.rule_id));
    return CORRECTIONS.filter((c) => c.rules.some((r) => rules.has(r)));
  }

// Cuenta en seco cuantos elementos tocaria cada correccion. No modifica nada.
  function preview(items, ctx) {
    const out = [];
    DRY = true;
    try {
      items.forEach((c) => {
        let count = 0;
        try {
          count = c.apply(ctx || {}) || 0;
        } catch (e) {
          count = 0;
        }
        out.push({ id: c.id, label: c.label, detail: c.detail, count });
      });
    } finally {
      DRY = false;
    }
    return out;
  }

  function applySelected(items, ctx) {
    let total = 0;
    const done = [];
    DRY = false;
    items.forEach((c) => {
      let n = 0;
      try {
        n = c.apply(ctx || {}) || 0;
      } catch (e) {
        n = 0;
      }
      if (n > 0) {
        done.push({ id: c.id, label: c.label, count: n, rules: c.rules.slice() });
        total += n;
      }
    });
    return { total, done };
  }

    return { CORRECTIONS, available, preview, applySelected };
  })();

export { Fixer };

