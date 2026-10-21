/* Vista Editar documento (clave interna: "correcciones").

No dibuja nada: es la vista "shell" que muestra el editor, que ya está montado
en la página. El router se encarga de enseñar la cinta, el área de trabajo y la
barra de estado.
  */
import { Router } from "../core/router.js";

(function () {
    "use strict";

    Router.register("correcciones", {
      title: "Editar documento",
      icon: "wand",
      order: 30,
      shell: true,
    });
  })();
