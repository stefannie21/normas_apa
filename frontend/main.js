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
Router.init(App);
Icons.hydrate(document);
