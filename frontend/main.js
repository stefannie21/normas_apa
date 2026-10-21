import { Router } from "./core/router.js";
import { App } from "./editor/app.js";
import { Sidebar } from "./sidebar.js";
import { Icons } from "./ui/icons.js";

import "./views/inicio.js";
import "./views/tesis.js";
import "./views/correcciones.js";
import "./views/reportes.js";
import "./views/ajustes.js";

App.onChange(() => Router.refresh());
Sidebar.init();
// Se arranca en "Correcciones": el documento abierto es el area de trabajo y
// las otras secciones (Inicio, Mis tesis, Reportes) quedan a un clic.
Router.init(App, "correcciones");
Icons.hydrate(document);
