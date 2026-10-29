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
// Se arranca en "Inicio": el panel de situación es la primera pantalla y el
// documento abierto queda a un clic en "Correcciones".
Router.init(App, "inicio");
Icons.hydrate(document);
