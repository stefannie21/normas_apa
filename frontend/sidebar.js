/* Menú lateral: solo plegado y despliegue. Las secciones viven en views/ y las
   maneja core/router.js. */
import { Dom } from "./core/dom.js";
import { Icons } from "./ui/icons.js";

const { $ } = Dom;

function toggleMenu() {
  // si esta oculto se muestra, y al reves: el valor actual decide el destino
  setMenu(document.querySelector(".app").classList.contains("sb-hidden"));
}

function setMenu(show) {
  const appEl = document.querySelector(".app");
  if (!appEl) return;
  appEl.classList.toggle("sb-hidden", !show);
  try {
    localStorage.setItem("apa.menu.hidden", show ? "0" : "1");
  } catch (e) {
    /* modo privado */
  }
  const label = show ? "Ocultar menú" : "Mostrar menú";
  const btn = $("sb-collapse");
  if (btn) {
    const t = btn.querySelector("strong");
    if (t) t.textContent = label;
    const s2 = btn.querySelector("small");
    if (s2) s2.textContent = show ? "Amplía el área de edición" : "Volver a mostrar el menú";
    btn.querySelector("[data-icon]")?.setAttribute("data-icon", show ? "chevron" : "menu");
    Icons.hydrate(btn);
  }
  const showBtn = $("sb-show");
  if (showBtn) showBtn.title = show ? "Menú visible" : "Mostrar el menú";
}

function init() {
  const card = $("sb-collapse");
  if (card) card.addEventListener("click", toggleMenu);

  const showBtn = $("sb-show");
  if (showBtn) showBtn.addEventListener("click", () => setMenu(true));

  try {
    if (localStorage.getItem("apa.menu.hidden") === "1") setMenu(false);
  } catch (e) {
    /* sin persistencia */
  }
}

export const Sidebar = { init, setMenu };
