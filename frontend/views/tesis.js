/* Vista Mis Tesis.

Pendiente: listar las tesis guardadas. Hoy SessionStore guarda un único
documento bajo la clave "current"; para listar varios hay que darle a cada uno
su propia clave y un registro de metadatos.
*/
import { Router } from "../core/router.js";
import { Dom } from "../core/dom.js";

const { icon } = Dom;

Router.register("tesis", {
  title: "Mis Tesis",
  icon: "files",
  order: 20,
  render() {
    return `<div class="view-head"><h1>${icon("files")}Mis Tesis</h1></div>
      <div class="vempty">Esta sección todavía no tiene contenido.</div>`;
  },
});
