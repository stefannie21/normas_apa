/* Ribbon estilo Word: barra de herramientas por pestañas.
     Las acciones se delegan en Commands (edicion) y en los hooks que registra app.js. */
import { Commands } from "./commands.js";
import { History } from "./history.js";
import { Icons } from "../ui/icons.js";

const Ribbon = (function () {
  "use strict";

  const hooks = {};

  // ------------------------------------------------------------- configuracion
  const FONT_SIZES = [8, 9, 10, 11, 12, 14, 16, 18, 24, 28, 36, 48];

  const RIBBON = [
    {
      id: "inicio",
      label: "Inicio",
      groups: [
{
          label: "Portapapeles",
          controls: [
            { type: "action", cmd: "paste", icon: "paste", label: "Pegar", big: true },
            { type: "action", cmd: "undo", icon: "undo", label: "Deshacer" },
            { type: "action", cmd: "redo", icon: "redo", label: "Rehacer" },
          ],
        },
        {
          label: "Fuente",
          controls: [
            { type: "select", cmd: "fontName", options: ["Times New Roman", "Calibri", "Arial", "Georgia", "Lucida Sans Unicode", "Computer Modern"], default: "Times New Roman" },
            { type: "select", cmd: "fontSize", options: FONT_SIZES, default: 12, numeric: true },
            // Las letras son las del atajo en espanol: N negrita, C cursiva, S
            // subrayado. Antes se dibujaba encima el icono con la letra inglesa
            // (B, I, U), que es la de Word en ingles y despista al usuario.
            // Van en un grupo propio porque el grupo "Fuente" es mas ancho que
            // su hueco y, sin agruparlos, flex los reparte entre dos filas.
            {
              type: "group",
              controls: [
                { type: "action", cmd: "bold", letter: "N", label: "Negrita", toggle: true },
                { type: "action", cmd: "italic", letter: "C", label: "Cursiva", toggle: true },
                { type: "action", cmd: "underline", letter: "S", label: "Subrayado", toggle: true },
              ],
            },
            { type: "color", prop: "foreColor", label: "Color de texto", icon: "color" },
            { type: "color", prop: "hiliteColor", label: "Resaltar", icon: "highlight" },
          ],
        },
        {
          label: "Párrafo",
          controls: [
            { type: "action", cmd: "justifyLeft", icon: "alignLeft", label: "Izquierda", toggle: true },
            { type: "action", cmd: "justifyCenter", icon: "alignCenter", label: "Centrar", toggle: true },
            { type: "action", cmd: "justifyRight", icon: "alignRight", label: "Derecha", toggle: true },
            { type: "action", cmd: "justifyFull", icon: "alignJustify", label: "Justificar", toggle: true },
            { type: "action", cmd: "outdent", icon: "indentDec", label: "Reducir sangría" },
            { type: "action", cmd: "indent", icon: "indentInc", label: "Aumentar sangría" },
            { type: "select", cmd: "lineHeight", options: ["1", "1.15", "1.5", "2", "2.5", "3"], default: "2", label: "Interlineado" },
          ],
        },
        {
          label: "Estilos",
          controls: [
            { type: "select", action: "style", options: ["Normal", "Párrafo de lista", "Título 1", "Título 2", "Título 3"], default: "Normal" },
            { type: "action", cmd: "removeFormat", icon: "pilcrow", label: "Quitar formato" },
          ],
        },
      ],
    },
    {
      id: "insertar",
      label: "Insertar",
      groups: [
        {
          label: "Tablas e imagenes",
          controls: [
            { type: "action", action: "table", icon: "table", label: "Tabla", big: true },
            { type: "action", action: "image", icon: "image", label: "Imagen", big: true },
            { type: "action", action: "link", icon: "link", label: "Enlace", big: true },
          ],
        },
        {
          label: "Listas",
          controls: [
            { type: "action", cmd: "insertUnorderedList", icon: "bulletList", label: "Viñetas", toggle: true },
            { type: "action", cmd: "insertOrderedList", icon: "numberedList", label: "Numerada", toggle: true },
          ],
        },
      ],
    },
    {
      id: "revisar",
      label: "Revisar APA",
      groups: [
        {
          label: "Revisión",
          controls: [
{ type: "action", action: "analyze", icon: "check", label: "Verificar normas APA", big: true, primary: true },
            { type: "action", action: "ai-review", icon: "spark", label: "Revisión con IA", big: true },
            { type: "action", action: "ai-revoke", icon: "shield", label: "Quitar consentimiento IA" },
            { type: "action", action: "fix-doc", icon: "fix", label: "Corregir documento", big: true },
            { type: "action", action: "toggle-pane", icon: "panel", label: "Ver informe" },
            { type: "action", action: "clear-marks", icon: "paint", label: "Quitar marcas" },
          ],
        },
{
          label: "Páginas",
          controls: [
            { type: "action", action: "page-break", icon: "pageBreak", label: "Salto de página" },
            { type: "action", action: "repaginate", icon: "ruler", label: "Reorganizar páginas", big: true },
          ],
        },
        {
          label: "Estilo APA",
          controls: [
            { type: "action", action: "apa-defaults", icon: "docs", label: "Formato base", hint: "Aplicar formato base" },
          ],
        },
      ],
    },
    {
      id: "vista",
      label: "Vista",
      groups: [
        {
          label: "Vistas",
          controls: [
            { type: "action", action: "reading", icon: "eye", label: "Modo lectura", big: true },
          ],
        },
        {
          label: "Mostrar",
          controls: [
            { type: "action", action: "toggle-pane", icon: "panel", label: "Ver informe" },
            { type: "action", action: "orientacion", icon: "pageBreak", label: "Orientación de páginas" },
            { type: "action", action: "toggle-ruler", icon: "ruler", label: "Regla" },
          ],
        },
      ],
    },
  ];

  // ------------------------------------------------------------------ helpers
  function svg(name, size) {
      const markup = Icons.svg(name);
    if (!markup) return "";
    return markup.replace("<svg", `<svg width="${size}" height="${size}"`);
  }

  function el(tag, cls, html) {
    const node = document.createElement(tag);
    if (cls) node.className = cls;
    if (html != null) node.innerHTML = html;
    return node;
  }

  let callbacks = {};
  let tabsEl = null;
  let panelsEl = null;
  let activeTab = RIBBON[0].id;
  let zoomValue = 100;

  // -------------------------------------------------------------------- render
  function render(tabs, panels, cbs) {
    tabsEl = tabs;
    panelsEl = panels;
    callbacks = cbs || {};

    tabsEl.innerHTML = "";
    RIBBON.forEach((tab) => {
      const b = el("button", "ribbon-tab" + (tab.id === activeTab ? " active" : ""), tab.label);
      b.addEventListener("click", () => {
        activeTab = tab.id;
        tabsEl.querySelectorAll(".ribbon-tab").forEach((x, i) =>
          x.classList.toggle("active", RIBBON[i].id === activeTab)
        );
        renderGroups(tab);
      });
      tabsEl.appendChild(b);
    });
    renderGroups(RIBBON[0]);
  }

  function renderGroups(tab) {
    panelsEl.innerHTML = "";
    const panel = el("div", "ribbon-panel active" + (tab.id !== "inicio" ? " ribbon-side" : ""));
    tab.groups.forEach((g) => {
      const group = el("div", "ribbon-group");
      const controls = el("div", "ribbon-group-controls");
      g.controls.forEach((c) => controls.appendChild(renderControl(c)));
      group.appendChild(controls);
      group.appendChild(el("div", "ribbon-group-label", g.label));
      panel.appendChild(group);
    });
    panelsEl.appendChild(panel);
    refreshStates();
    // al cambiar de pestaña se recrean los botones: hay que volver a reflejar
    // si queda algo que deshacer o rehacer
      if (History.refresh) History.refresh();
  }

  function renderControl(c) {
    if (c.type === "select") return renderSelect(c);
    if (c.type === "color") return renderColor(c);
    if (c.type === "group") return renderGroup(c);
    return renderAction(c);
  }

  // Fila que no se parte: mantiene juntos los controles que deben caer en la
  // misma linea (las tres letras de fuente, por ejemplo). El grupo "Fuente" no
  // cabe entero en su ancho maximo, asi que sin esto flex envuelve y la N se
  // queda sola en la fila de arriba, separada de la C y la S.
  function renderGroup(c) {
    const row = el("div", "rrow");
    (c.controls || []).forEach((child) => row.appendChild(renderControl(child)));
    return row;
  }

function renderSelect(c) {
    const wrap = el("div", "rselect-wrap");
    const sel = document.createElement("select");
    sel.className = "rselect";
    // permite que Commands.refresh() sepa que desplegable hay que atualizar
    // con lo que tenga el texto seleccionado
    sel.dataset.cmd = c.cmd || c.action || "";
    // valor con el que se dibuja por defecto: es al que vuelve la cinta cuando
    // no hay nada seleccionado
    if (c.default !== undefined) sel.dataset.default = String(c.default);
    if (c.label) sel.title = c.label;
    const opts = c.options || [];
    // las opciones deben existir ANTES de fijar el valor: si no, el navegador
    // reinicia selectedIndex a 0 y el desplegable miente (p. ej. interlineado 1)
    opts.forEach((o) => {
      const opt = document.createElement("option");
      opt.value = String(o);
      opt.textContent = String(o);
      sel.appendChild(opt);
    });
    if (c.default !== undefined && opts.some((o) => String(o) === String(c.default))) {
      sel.value = String(c.default);
    }
    sel.addEventListener("change", () => {
      if (c.action === "style") {
        applyStyle(sel.value);
      } else if (c.cmd === "fontName") {
        Commands.applyFontFamily(sel.value);
      } else if (c.cmd === "fontSize") {
        Commands.applyFontSize(Number(sel.value));
      } else if (c.cmd === "lineHeight") {
        Commands.applyToBlocks("lineHeight", sel.value);
      } else if (c.cmd) {
        Commands.exec(c.cmd);
      }
    });
    wrap.appendChild(sel);
    return wrap;
  }

  const STYLE_MAP = {
    Normal: ["p", ""],
    "Párrafo de lista": ["li", ""],
    "Título 1": ["h1", "1.5em"],
    "Título 2": ["h2", "1.3em"],
    "Título 3": ["h3", "1.12em"],
  };

  function applyStyle(name) {
    const p = document.getElementById("page");
    if (!p) return;
    const [tag, size] = STYLE_MAP[name] || ["p", ""];
    // nunca se toman las hojas como bloques: solo parrafos y titulos reales
    const blocks = Commands.selectedBlocks();
    const targets = blocks.length ? blocks : Commands.contentBlocks();
    if (!targets.length) return;
    targets.forEach((b) => {
      const replacement = document.createElement(tag);
      replacement.innerHTML = b.innerHTML;
      if (size) replacement.style.fontSize = size;
      b.replaceWith(replacement);
    });
    // convertir p <-> h1/h2/h3 invalida el indice generado: se rehace
    if (tag === "h1" || tag === "h2" || tag === "h3" || tag === "p") rebuildIndex();
  }

    function rebuildIndex() {
      if (typeof hooks.onStyleChange === "function") hooks.onStyleChange();
    }

  function renderColor(c) {
    const wrap = el("div", "rcolor");
    wrap.title = c.label || "";
    const icon = el("span", "rcolor-icn", svg(c.icon || "color", 18));
    const input = document.createElement("input");
    input.type = "color";
    input.value = "#1b1f24";
    input.addEventListener("input", () => Commands.applyColor(c.prop, input.value));
    const bar = el("span", "rcolor-bar");
    wrap.appendChild(icon);
    wrap.appendChild(input);
    wrap.appendChild(bar);
    return wrap;
  }

  function renderAction(c) {
    const btn = document.createElement("button");
    btn.className = "rbtn";
    if (c.big) btn.classList.add("big");
    if (c.primary) btn.classList.add("primary");
    btn.title = c.hint || c.label || "";

    const parts = [];
    if (c.letter) {
      // La letra sustituye al icono: es el atajo en espanol y ocupa el boton
      // entero, como los botones de Negrita / Cursiva / Subrayado.
      parts.push(`<span class="ltr">${c.letter}</span>`);
    } else if (c.icon) {
      parts.push(`<span class="icn">${svg(c.icon, c.big ? 22 : 18)}</span>`);
    }
    if (c.label && !c.letter) parts.push(`<span>${c.label}</span>`);
    btn.innerHTML = parts.join("");
    if (c.letter) btn.classList.add("letter");

    if (c.cmd) {
      btn.dataset.cmd = c.cmd;
      if (c.toggle) btn.dataset.toggle = "1";
      btn.addEventListener("click", () => Commands.exec(c.cmd));
    } else if (c.action) {
      btn.dataset.action = c.action;
      btn.addEventListener("click", () => {
        const fn = callbacks[c.action];
        if (typeof fn === "function") fn();
      });
    }
    return btn;
  }

    function refreshStates() {
      Commands.refresh();
    }

  function setZoom(value) {
    zoomValue = value;
    const p = document.getElementById("page");
    if (p) p.style.transform = "scale(" + value / 100 + ")";
    const label = document.getElementById("zoom-label");
    if (label) label.textContent = value + "%";
  }

  function setHooks(h) {
    Object.assign(hooks, h || {});
  }

  return {
    render,
    setZoom,
    refreshStates,
    setHooks,
    RIBBON,
    get zoom() {
      return zoomValue;
    },
  };
})();

export { Ribbon };
