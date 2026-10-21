/* Vista Configuraciones. */
import { Router } from "../core/router.js";
import { Dom } from "../core/dom.js";

const { icon } = Dom;

Router.register("ajustes", {
  title: "Configuraciones",
  icon: "gear",
  order: 50,
  render() {
    return `<div class="view-head"><h1>${icon("gear")}Configuraciones</h1></div>
      <div class="vempty">Esta sección todavía no tiene contenido.</div>`;
  },
});
