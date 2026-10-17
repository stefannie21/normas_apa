/* Iconos SVG en linea (sin dependencias externas). */
(function () {
  "use strict";
  const ICONS = {
    // menú lateral
    cap: '<path d="M2 9l10-5 10 5-10 5z"/><path d="M6 11.5V16c0 1.7 2.7 3 6 3s6-1.3 6-3v-4.5"/>',
    home: '<path d="M3 11l9-7 9 7"/><path d="M5 10v9h14v-9"/><path d="M10 19v-5h4v5"/>',
    files: '<path d="M8 3h9l4 4v14H8z"/><path d="M17 3v4h4"/><path d="M4 7v14h11"/>',
    wand: '<path d="M4 20l4-1 10-10-3-3L5 16z"/><path d="M14 6l3 3"/><path d="M4 5h4"/><path d="M4 9h3"/>',
    chart: '<path d="M4 20V10"/><path d="M10 20V4"/><path d="M16 20v-7"/><path d="M22 20H2"/>',
    gear: '<circle cx="12" cy="12" r="3"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3M4.9 4.9l2.1 2.1M17 17l2.1 2.1M19.1 4.9L17 7M7 17l-2.1 2.1"/>',
    chevron: '<path d="M14 6l-6 6 6 6"/>',
    menu: '<path d="M4 7h16"/><path d="M4 12h16"/><path d="M4 17h16"/>',
    download: '<path d="M12 4v10"/><path d="M8 11l4 4 4-4"/><path d="M5 19h14"/>',
    save: '<path d="M5 4h11l3 3v13H5z"/><path d="M15 4v4h4"/><path d="M8 20v-6h8v6"/>',
    folder: '<path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>',
    search: '<circle cx="11" cy="11" r="6"/><line x1="16" y1="16" x2="21" y2="21"/>',
spark: '<path d="M12 2 L13.6 8.2 L20 9.8 L13.6 11.4 L12 18 L10.4 11.4 L4 9.8 L10.4 8.2 Z"/><path d="M18.5 15.5 L19.3 18.2 L22 19 L19.3 19.8 L18.5 22.5 L17.7 19.8 L15 19 L17.7 18.2 Z"/>',
    docs: '<path d="M7 3h7l5 5v13H7z"/><path d="M14 3v5h5"/>',
    clipboard: '<rect x="6" y="4" width="12" height="17" rx="2"/><path d="M9 4V3h6v1"/><path d="M9 11h6M9 15h4"/>',
    undo: '<path d="M9 7 4 12l5 5"/><path d="M4 12h9a6 6 0 0 1 0 12"/>',
    redo: '<path d="M15 7l5 5-5 5"/><path d="M20 12h-9a6 6 0 0 0 0 12"/>',
    paste: '<rect x="6" y="4" width="12" height="16" rx="2"/><path d="M9 4V3h6v1"/><path d="M9 11h6M9 15h4"/>',
    bold: '<path d="M7 4h6a4 4 0 0 1 0 8H7z"/><path d="M7 12h7a4 4 0 0 1 0 8H7z"/>',
    italic: '<line x1="10" y1="4" x2="14" y2="4"/><line x1="10" y1="20" x2="14" y2="20"/><line x1="14" y1="4" x2="10" y2="20"/>',
    underline: '<path d="M7 4v7a5 5 0 0 0 10 0V4"/><line x1="6" y1="20" x2="18" y2="20"/>',
    color: '<path d="M5 17 12 5l7 12z"/><line x1="4" y1="21" x2="20" y2="21"/>',
    highlight: '<path d="M4 20h16"/><path d="M6 16 15 4l3 3-9 9z"/><path d="M6 16l-1 4 4-1"/>',
    bulletList: '<circle cx="5" cy="7" r="1.3"/><circle cx="5" cy="12" r="1.3"/><circle cx="5" cy="17" r="1.3"/><line x1="9" y1="7" x2="20" y2="7"/><line x1="9" y1="12" x2="20" y2="12"/><line x1="9" y1="17" x2="20" y2="17"/>',
    numberedList: '<path d="M4 6h1v4M4 10h2"/><path d="M4 14h2l-2 3h2"/><line x1="10" y1="7" x2="20" y2="7"/><line x1="10" y1="12" x2="20" y2="12"/><line x1="10" y1="17" x2="20" y2="17"/>',
    indentInc: '<line x1="10" y1="6" x2="20" y2="6"/><line x1="10" y1="12" x2="20" y2="12"/><line x1="10" y1="18" x2="20" y2="18"/><path d="M4 9l3 3-3 3z"/>',
    indentDec: '<line x1="10" y1="6" x2="20" y2="6"/><line x1="10" y1="12" x2="20" y2="12"/><line x1="10" y1="18" x2="20" y2="18"/><path d="M7 9l-3 3 3 3z"/>',
    alignLeft: '<line x1="4" y1="6" x2="20" y2="6"/><line x1="4" y1="10" x2="13" y2="10"/><line x1="4" y1="14" x2="20" y2="14"/><line x1="4" y1="18" x2="13" y2="18"/>',
    alignCenter: '<line x1="4" y1="6" x2="20" y2="6"/><line x1="7" y1="10" x2="17" y2="10"/><line x1="4" y1="14" x2="20" y2="14"/><line x1="7" y1="18" x2="17" y2="18"/>',
    alignRight: '<line x1="4" y1="6" x2="20" y2="6"/><line x1="11" y1="10" x2="20" y2="10"/><line x1="4" y1="14" x2="20" y2="14"/><line x1="11" y1="18" x2="20" y2="18"/>',
    alignJustify: '<line x1="4" y1="6" x2="20" y2="6"/><line x1="4" y1="10" x2="20" y2="10"/><line x1="4" y1="14" x2="20" y2="14"/><line x1="4" y1="18" x2="20" y2="18"/>',
    lineSpacing: '<line x1="4" y1="6" x2="16" y2="6"/><line x1="4" y1="12" x2="16" y2="12"/><line x1="4" y1="18" x2="16" y2="18"/><path d="M19 5v14M17 7l2-2 2 2M17 17l2 2 2-2"/>',
    pageBreak: '<path d="M7 3h7l5 5v6H7z"/><path d="M4 17h16"/><path d="M12 19v3M12 22l-2-2M12 22l2-2"/>',
    table: '<rect x="4" y="5" width="16" height="14" rx="1.5"/><line x1="4" y1="10" x2="20" y2="10"/><line x1="4" y1="14.5" x2="20" y2="14.5"/><line x1="10" y1="5" x2="10" y2="19"/><line x1="15" y1="5" x2="15" y2="19"/>',
    image: '<rect x="4" y="5" width="16" height="14" rx="2"/><circle cx="9" cy="10" r="1.6"/><path d="M5 17l4-4 3 3 3-3 4 4"/>',
    link: '<path d="M9 14a4 4 0 0 0 6 0l2-2a4 4 0 0 0-6-6l-1 1"/><path d="M15 10a4 4 0 0 0-6 0l-2 2a4 4 0 0 0 6 6l1-1"/>',
    eye: '<path d="M2 12s4-7 10-7 10 7 10 7-4 7-10 7-10-7-10-7z"/><circle cx="12" cy="12" r="3"/>',
    panel: '<rect x="3" y="4" width="18" height="16" rx="2"/><line x1="15" y1="4" x2="15" y2="20"/>',
    check: '<path d="M5 12l4 4 10-10"/>',
  fix: '<path d="M4 20l4-1 10-10-3-3L5 16z"/><path d="M14 6l3 3"/><path d="M4 6h5"/><path d="M4 10h4"/>',
    ruler: '<rect x="3" y="8" width="18" height="8" rx="1"/><line x1="7" y1="8" x2="7" y2="12"/><line x1="11" y1="8" x2="11" y2="13"/><line x1="15" y1="8" x2="15" y2="12"/><line x1="19" y1="8" x2="19" y2="13"/>',
    pilcrow: '<path d="M13 4v16"/><path d="M9 4h8"/><path d="M9 4a4 4 0 0 0 0 8h4"/>',
    paint: '<path d="M5 9a4 4 0 0 1 4-4h6a4 4 0 0 1 4 4v1H5z"/><path d="M12 10v6"/><rect x="10" y="16" width="4" height="5" rx="1"/>',
  };

  function svg(name) {
    const markup = ICONS[name];
    if (!markup) return "";
    // Los iconos se guardan como fragmentos (paths). Se envuelven aqui para
    // que el navegador los interprete como SVGinline.
    return (
      '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" ' +
      'stroke="currentColor" stroke-width="1.8" stroke-linecap="round" ' +
      'stroke-linejoin="round">' +
      markup +
      "</svg>"
    );
  }

  function hydrate(rootEl) {
    const scope = rootEl || document;
    scope.querySelectorAll("[data-icon]").forEach((el) => {
      const name = el.getAttribute("data-icon");
      if (el.dataset.iconDone === name) return;
      el.innerHTML = svg(name);
      el.dataset.iconDone = name;
      el.style.display = "inline-flex";
      el.style.alignItems = "center";
    });
  }

  window.Icons = { svg, hydrate };
  window.hydrateIcons = hydrate;

  document.addEventListener("DOMContentLoaded", () => hydrate(document));
})();


