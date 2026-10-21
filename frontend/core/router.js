/* Registro y navegación entre vistas.

Cada sección se declara sola con Router.register(nombre, vista). La vista puede
ser una pantalla que se dibuja (render/mount) o una "shell" que solo activa algo
que ya está montado en la página, como el editor.

Contrato de una vista:
  title   -> nombre visible en el menú y en el título de la pestaña
  icon    -> icono del menú
  order   -> posición en el menú
  shell   -> true si no se dibuja, solo se activa
  render(api)  -> devuelve HTML
  mount(el, api)  -> enlaza eventos
  refresh(api)    -> opcional; el estado de la app cambió
  unmount()       -> opcional; se sale de la vista
  activate(api)   -> solo en vistas shell
*/
import { Dom } from "./dom.js";

const views = {};
let api = null;
let inner = null;
let nav = null;
let view = null;
let current = null;

function register(name, spec) {
  views[name] = spec;
}

function syncNav(name) {
  if (!nav) return;
  nav.querySelectorAll(".sb-item").forEach((b) => {
    b.classList.toggle("active", b.dataset.view === name);
  });
}

function setShell(show) {
  const ribbon = document.getElementById("ribbon");
  const ws = document.querySelector(".workspace");
  const bar = document.querySelector(".statusbar");
  if (ribbon) ribbon.hidden = !show;
  if (ws) ws.hidden = !show;
  if (bar) bar.hidden = !show;
}

function go(name) {
  const spec = views[name];
  if (!spec) return;

  const prev = views[current];
  if (prev && typeof prev.unmount === "function") prev.unmount();

  current = name;
  syncNav(name);
  document.title = (spec.title ? spec.title + " · " : "") + "APA Studio";

  if (spec.shell) {
    if (view) view.hidden = true;
    setShell(true);
    if (typeof spec.activate === "function") spec.activate(api);
    return;
  }

  if (view) view.hidden = false;
  setShell(false);
  if (!inner) return;
  inner.innerHTML = spec.render ? spec.render(api) : "";
  Dom.hydrate(inner);
  if (typeof spec.mount === "function") spec.mount(inner, api);
}

function refresh() {
  const spec = views[current];
  if (spec && typeof spec.refresh === "function") spec.refresh(api);
}

function buildNav() {
  if (!nav) return;
  const list = Object.keys(views)
    .filter((k) => !views[k].hideInMenu)
    .sort((a, b) => (views[a].order || 0) - (views[b].order || 0));

  nav.innerHTML = list
    .map((name) => {
      const v = views[name];
      return `<button class="sb-item" data-view="${name}" title="${Dom.esc(v.title)}">
        <span class="sb-icn" data-icon="${v.icon || "docs"}"></span><span class="sb-label">${Dom.esc(v.title)}</span>
      </button>`;
    })
    .join("");
  Dom.hydrate(nav);
}

function init(app, start) {
  api = app;
  inner = document.getElementById("view-inner");
  nav = document.getElementById("sb-nav");
  view = document.getElementById("view");

  Object.keys(views).forEach((k) => {
    if (typeof views[k].setup === "function") views[k].setup(api);
  });

  buildNav();
  if (nav) {
    nav.addEventListener("click", (e) => {
      const b = e.target.closest(".sb-item");
      if (b) go(b.dataset.view);
    });
  }
  go(start || "inicio");
}

export const Router = {
  register,
  init,
  go,
  refresh,
  current: () => current,
  has: (name) => !!views[name],
};
