/* Utilidades de DOM compartidas por el menu y las vistas. */
import { Icons } from "../ui/icons.js";

function $(id) {
  return document.getElementById(id);
}

function esc(s) {
  const d = document.createElement("div");
  d.textContent = s == null ? "" : String(s);
  return d.innerHTML;
}

function icon(name) {
  return `<span data-icon="${name}"></span>`;
}

function hydrate(root) {
  Icons.hydrate(root);
}

function fecha(iso) {
  try {
    return new Date(iso).toLocaleString("es", {
      day: "2-digit",
      month: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch (e) {
    return "";
  }
}

export const Dom = { $, esc, icon, hydrate, fecha };
export { $, esc, icon, hydrate, fecha };
