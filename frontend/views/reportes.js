/* Vista Reportes. */
import { Router } from "../core/router.js";
import { Dom } from "../core/dom.js";

const { icon } = Dom;

Router.register("reportes", {
  title: "Reportes",
  icon: "chart",
  order: 40,
  render() {
    return `<div class="view-head"><h1>${icon("chart")}Reportes</h1></div>
      <div class="vempty">Esta sección todavía no tiene contenido.</div>`;
  },
});
