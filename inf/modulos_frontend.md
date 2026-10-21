# Módulos del frontend

Cómo está organizada la interfaz, qué responsabilidad tiene cada archivo y qué
reglas hay que respetar para que el código no vuelva a convertirse en un bloque
difícil de mantener.

Estado: la **opción A** (vistas separadas, router propio) y la **opción B**
(módulos ES nativos, carpetas `core/`, `ui/`, `editor/`, `views/`) ya están
aplicadas. El detalle del plan B se conserva en la sección 10.

---

## 1. Principios

1. **Una responsabilidad por archivo.** Si un archivo dibuja y además navega y
   además guarda datos, son dos o tres módulos.
2. **Dependencias en un solo sentido.** `core` no sabe qué es una vista; una
   vista no sabe qué es el editor; el editor no sabe que existe el menú.
3. **El estado vive en un solo sitio.** Hoy es el editor (`app.js`). Las vistas
   lo leen a través de la fachada, nunca tocando variables internas.
4. **Nada de HTML duplicado.** El menú lo genera el registro de vistas: una
   sección nueva aparece en el menú sin editar `index.html`.
5. **Sin empaquetador.** El navegador carga los archivos tal cual. En la opción
   B se usan módulos ES nativos; no hay `node_modules` ni compilación.

---

## 2. Estructura actual

```
frontend/
  index.html            cáscara: menú vacío, cinta, editor, panel de informe
  main.js               punto de entrada: importa todo y arranca
  core/
    dom.js              utilidades de DOM ($, esc, icon, hydrate, fecha)
    router.js           registro de vistas, go(), refresh(), menú
  ui/
    icons.js            iconos SVG en línea
  views/
    inicio.js           panel de situación
    tesis.js            Mis Tesis (pendiente de datos)
    correcciones.js     vista shell del editor
    reportes.js         Reportes (pendiente)
    ajustes.js          Configuraciones (pendiente)
  editor/
    app.js              editor: carga, edición, análisis, informe, correcciones
    pager.js            paginación tipo Word
    ribbon.js           cinta de opciones
    commands.js         comandos de edición y estilos
    history.js          deshacer / rehacer
    fixer.js            correcciones automáticas
    marker.js           señalamiento de errores en el texto
    storage.js          guardado local (IndexedDB)
  sidebar.js            solo plegar / desplegar el menú
```

---

## 3. Mapa de dependencias

```
                    main.js  (une todo)
                   /   |   \
                  /    |    \
             views/  core/  editor/
                \      |      /
                 \     |     /
                  Dom ─┴─ Router
```

Regla de oro:

```
core   ->  no importa nada de views ni de editor
views  ->  puede importar core; usa el editor solo por la fachada (api)
editor ->  puede importar core (Dom); nunca importa views ni router
main   ->  importa views, core y editor; es el único que los conecta
```

Si aparece un `import` que va en contra de estas flechas, el diseño está mal.

---

## 4. Qué va en cada módulo

### 4.1 `core/dom.js` — utilidades de DOM

| | |
|---|---|
| **Responsabilidad** | Funciones puras de DOM y texto. |
| **Depende de** | Nada. |
| **Expone** | `$`, `$$`, `esc`, `icon`, `hydrate`, `fecha`. |
| **No debe** | Consultar la API, guardar estado, conocer vistas concretas. |

Contenido actual: `$`, `esc`, `icon`, `hydrate`, `fecha`.

Candidatos a entrar aquí más adelante: `delegate(root, selector, event, fn)`,
`on(root, event, fn)`.

### 4.2 `core/router.js` — navegación

| | |
|---|---|
| **Responsabilidad** | Guardar el registro de vistas, cambiar de sección, avisar del refresco y construir el menú. |
| **Depende de** | `dom.js`. |
| **Expone** | `register`, `init`, `go`, `refresh`, `current`, `has`. |
| **No debe** | Dibujar contenido de una sección, hablar con la API, conocer el editor. |

Decide tres cosas:

1. qué vista está activa y qué elemento del menú se resalta;
2. si se muestra el contenedor de vistas **o** el editor (`shell: true`);
3. el título del documento (`Inicio · APA Studio`).

No decide *qué* contiene una sección: eso es de `views/`.

### 4.3 `core/http.js` — acceso a la API *(propuesto en la opción B)*

| | |
|---|---|
| **Responsabilidad** | Todas las llamadas a `/api/*`, en un solo sitio. |
| **Depende de** | `fetch`. |
| **Expone** | `health()`, `rules()`, `analyze(...)`, `docxMeta(...)`, `reportDocx(...)`, `exportDocx(...)`, `aiClassify(...)`. |
| **No debe** | Tocar el DOM ni saber qué vista lo llama. |

Hoy las llamadas están repartidas entre `app.js` y `views/inicio.js`
(`fetch("/api/rules")`, `fetch("/api/health")`). Centralizarlas permite manejar
timeouts y errores de una sola forma. No es obligatorio para la opción B; sí es
recomendable.

### 4.4 `views/*.js` — las secciones

Todas cumplen el mismo contrato (sección 5). Lo que cambia es su contenido:

**`views/inicio.js`** — panel de situación.
- Lee `api.state()`: nombre, páginas, palabras, score, recuento de hallazgos.
- Pide `/api/health` para el estado de la IA y `/api/rules` para el número de reglas.
- Acciones: abrir archivo, ir al editor, ver informe.
- **No debe** analizar el documento ni modificar el editor.

**`views/tesis.js`** — lista de tesis guardadas.
- Hoy solo dibuja el estado vacío porque `SessionStore` guarda **un único**
  documento bajo la clave `"current"`.
- Para que tenga contenido real hace falta, antes, un repositorio de documentos
  (ver 4.8). No se deben inventar tesis de ejemplo.

**`views/correcciones.js`** — vista *shell*.
- No dibuja nada. Solo declara `shell: true` para que el router enseñe la cinta,
  el área de trabajo y la barra de estado.
- **No debe** contener lógica del editor.

**`views/reportes.js`** — informe.
- Destino natural: resumen del último análisis, histórico de scores, descarga
  del informe en Word. Hoy: estado vacío.

**`views/ajustes.js`** — configuración.
- Destino natural: mostrar proveedor y modelo de IA (`/api/health`), umbral de
  confianza, y preferencias de la interfaz (menú plegado, zoom).
- **No debe** editar el `.env` ni exponer claves.

### 4.5 `sidebar.js` — el menú

| | |
|---|---|
| **Responsabilidad** | Plegar y desplegar la barra lateral; recordar la preferencia. |
| **Depende de** | `core/dom.js`. |
| **Expone** | `init`, `setMenu`. |
| **No debe** | Navegar entre secciones ni dibujar contenido. |

Si el menú necesita un elemento nuevo (un separador, un pie con versión), se
añade al HTML que genera `router.js`, no aquí.

### 4.6 `editor/app.js` — el documento

| | |
|---|---|
| **Responsabilidad** | Ciclo de vida del `.docx`: abrir, convertir, editar, paginar, analizar, marcar, corregir, exportar y restaurar la sesión. |
| **Depende de** | `Pager`, `Marker`, `Fixer`, `History`, `Commands`, `Ribbon`, `SessionStore`, `Icons`. |
| **Expone (fachada)** | `state()`, `pickFile()`, `openReport()`, `rebuildIndex()`, `onChange(fn)`. |
| **No debe** | Conocer el router ni las vistas. |

Es el módulo más grande (≈1.400 líneas). La opción B **no** lo divide; solo lo
declara como módulo ES y le quita la llamada a `Router.init`. Dividirlo por
dentro (documento, análisis, informe, exportación) es un trabajo aparte.

El editor no llama al router: cuando cambia su estado, avisa a quien se haya
suscrito con `App.onChange(fn)`. Es `main.js` el que suscribe
`() => Router.refresh()`, y así el editor deja de depender de la navegación.

### 4.7 `editor/pager.js`, `ribbon.js`, `marker.js`, `fixer.js`, `commands.js`, `history.js`, `storage.js`

| Módulo | Responsabilidad | No debe |
|---|---|---|
| `pager.js` | Repartir el HTML en hojas y calcular páginas. | Editar el contenido. |
| `ribbon.js` | Dibujar la cinta y reflejar el estado de los botones. | Aplicar formato por sí mismo: usa `Commands`. |
| `marker.js` | Señalar hallazgos en el texto y el globito. | Corregir nada. |
| `fixer.js` | Correcciones mecánicas y reversibles, con vista previa. | Tocar autores, años ni contenido. |
| `commands.js` | Comandos de edición (`exec`, fuentes, sangrías…). | Decidir cuándo se ejecutan. |
| `history.js` | Pila de deshacer / rehacer. | Guardar en disco. |
| `storage.js` | Persistir la sesión en IndexedDB. | Decidir qué documento es “el actual”. |

`storage.js` es el que hay que ampliar para `views/tesis.js`:

```
hoy:   clave "current"            -> un documento
meta:  clave "index"              -> [{id, nombre, fecha, score}]
doc:   clave "doc:<id>"           -> contenido del documento
```

### 4.8 `ui/icons.js` — iconos

| | |
|---|---|
| **Responsabilidad** | Devolver el SVG de un nombre y reemplazar `[data-icon]`. |
| **Depende de** | Nada. |
| **Expone** | `Icons.svg(nombre)`, `Icons.hydrate(root)`. |
| **No debe** | Conocer secciones ni estado. |

Vive en `frontend/ui/icons.js` porque lo usan el menú, las vistas y el editor.

### 4.9 `main.js` — el cableado *(propuesto en la opción B)*

| | |
|---|---|
| **Responsabilidad** | Importar todo y conectar las piezas al arrancar. |
| **Depende de** | `core`, `views`, `editor`. |
| **Expone** | Nada: es el punto de entrada. |
| **No debe** | Tener lógica de negocio ni dibujar. |

Hace exactamente esto:

```js
import { Router } from "./core/router.js";
import * as Sidebar from "./sidebar.js";
import "./views/inicio.js";
import "./views/tesis.js";
import "./views/correcciones.js";
import "./views/reportes.js";
import "./views/ajustes.js";
import { App } from "./editor/app.js";

Sidebar.init();
Router.init(App, "inicio");
```

---

## 5. El contrato de una vista

```js
const vista = {
  title: "Reportes",        // obligatorio: menú y título de pestaña
  icon: "chart",            // obligatorio: nombre de icono
  order: 40,                // obligatorio: posición en el menú
  shell: false,             // opcional: no se dibuja, solo se activa
  setup(api) {},            // opcional: recibe la fachada una vez
  render(api) -> string,    // HTML de la sección
  mount(el, api) {},        // enlazar eventos sobre el HTML recién creado
  refresh(api) {},          // opcional: el estado cambió; redibujar
  unmount() {},             // opcional: limpiar temporizadores, etc.
  activate(api) {},         // solo si shell: true
};
```

Reglas:

- `render` es **puro**: no escribe en el documento ni pide datos sin necesidad.
- `mount` es el único lugar donde se añaden `addEventListener`; al redibujar,
  el HTML se reemplaza y los eventos viejos desaparecen con él.
- `refresh` no debe perder la posición del scroll (ver `views/inicio.js`).
- Una vista **no** guarda referencias a nodos fuera de su contenedor.

---

## 6. El contrato del editor

Las vistas no importan `app.js`: reciben una fachada con cuatro funciones.

| Función | Para qué |
|---|---|
| `state()` | `{name, pages, words, dirty, savedAt, score, counts, ruleCount}` |
| `pickFile()` | Abrir el selector de `.docx` |
| `openReport()` | Mostrar el panel del informe |
| `rebuildIndex()` | Rehacer el índice si cambió la estructura |

Aviso de cambios: hoy `app.js` llama directamente a `Router.refresh()`, lo que
invierte la dependencia (el editor no debería saber que existe el router). En la
opción B se sustituye por una suscripción:

```js
// editor/app.js
let onChange = () => {};
export const App = { /* ... */ onChange(cb) { onChange = cb; } };
function avisar() { onChange(); }

// main.js
App.onChange(() => Router.refresh());
```

---

## 7. CSS por módulo

Los selectores **no cambian**; solo se reparten. Así no hay regresiones.

| Archivo | Contenido |
|---|---|
| `styles/base.css` | Variables, tipografía, botones, scrollbars, utilidades |
| `styles/layout.css` | `.app`, `.sidebar`, `.sb-*`, `.titlebar`, `.statusbar` |
| `styles/editor.css` | `.workspace`, `.canvas`, `.page`, `.sheet`, `.ribbon`, `.report-pane` |
| `styles/views.css` | `.view`, `.view-head`, `.vempty`, `.vbtn` |
| `styles/dashboard.css` | `.dash`, `.hero`, `.stats`, `.stat`, `.card`, `.pasos` |

Prefijo por sección para que no se pisen estilos nuevos:
`inicio` → `.dash-*`, `tesis` → `.tesis-*`, `reportes` → `.rep-*`,
`ajustes` → `.cfg-*`.

---

## 8. Cómo añadir una sección (paso a paso)

1. Crear `frontend/views/miseccion.js`.
2. Registrar la vista:

```js
import { esc, icon } from "../core/dom.js";

export default {
  title: "Mi sección",
  icon: "docs",
  order: 60,
  render(api) {
    return `<div class="view-head"><h1>${icon("docs")}Mi sección</h1></div>
            <div class="vempty">Nada todavía.</div>`;
  },
  mount(el, api) {},
};
```

3. Añadir el `<script>` en `index.html` (opción A) o el `import` en `main.js`
   (opción B).
4. Recargar: aparece en el menú en la posición `order`. No hay que tocar el HTML
   del menú.

Para una sección que necesite datos, `mount` pide los datos y `render` los
dibuja; no se guardan datos en el módulo salvo caché explícita (como
`ruleCount` en `inicio.js`).

---

## 9. Nombres y estilo

- Archivos en minúsculas y sin espacios: `inicio.js`, `reportes.js`.
- Un módulo expone **una** cosa: `Dom`, `Router`, `App`, o un objeto de vista.
- Exportaciones nombradas; `export default` solo para la vista de un archivo de
  `views/`.
- Español para lo visible (textos, títulos) y para los nombres de dominio
  (`hallazgos`, `tesis`); inglés solo en APIs del navegador.
- Sin comentarios que repitan lo que dice el código; sí para decisiones raras
  (por qué se ignora un caso, por qué se conserva el scroll).

---

## 10. La opción B: módulos ES nativos

**Aplicada.** Objetivo: `import` / `export` en lugar de `window.X`, sin
empaquetador. Se hizo de una vez (B1–B4), verificando al final con las tres
pruebas E2E.

### Qué cambia

| Antes (A) | Después (B) |
|---|---|
| `window.Dom = {...}` | `export const Dom = {...}` |
| `<script src="...">` por archivo | `import` desde `main.js` |
| `window.App` | `export const App` |
| `Router.init(window.App)` dentro de `app.js` | `Router.init(App)` en `main.js` |
| `index.html` carga 17 scripts | carga `main.js` como `type="module"` |

### Mapa de imports

```
main.js
 ├── core/router.js ── core/dom.js
 ├── sidebar.js ────── core/dom.js
 ├── views/* ───────── core/dom.js
 └── editor/app.js ─── editor/{pager,ribbon,marker,fixer,history,commands,storage}.js
                       ui/icons.js
```

### Pasos, con verificación después de cada uno

**B1. `main.js` y los módulos de `core` y `views`.**
- Convertir `dom.js`, `router.js` y las cinco vistas a `import`/`export`.
- Crear `main.js`; `index.html` conserva los scripts del editor y añade
  `<script type="module" src="/static/main.js"></script>` al final.
- Quitar de `app.js` la llamada a `Router.init`; `main.js` la hace.
- Verificar: las cinco secciones, el menú y el editor siguen funcionando.

**B2. El editor, archivo por archivo.**
- Convertir `pager`, `icons` (a `ui/`), `history`, `commands`, `marker`,
  `fixer`, `ribbon`, `storage`, `app`.
- Mientras quede algún consumidor sin convertir, el módulo conserva además
  `window.X = X` como puente temporal.
- Verificar después de cada archivo: abrir tesis, analizar, corregir, deshacer,
  exportar.

**B3. Retirar los puentes.**
- Borrar todos los `window.X = ...` y comprobar que no queda ninguna referencia
  global. `grep` de `window.` debe devolver solo lo imprescindible.

**B4. Mover el editor a `editor/`.**
- Mover los archivos y ajustar imports. `index.html` ya solo carga `main.js`.
- Verificar: misma batería completa.

### Criterio de aceptación de B

- `index.html` carga un único script.
- `grep window.` en `frontend/` no devuelve asignaciones de módulos.
- Las 5 secciones navegan, el editor abre/analiza/corrige/exporta y el menú se
  pliega, sin errores en consola.
- La prueba E2E del editor y la de módulos pasan sin cambios.

### Lo que B **no** hace

- No divide `app.js` por dentro (eso es otra fase).
- No cambia la lógica de las reglas ni de la IA.
- No toca el backend.
- No introduce dependencias ni herramientas de compilación.

---

## 11. Checklist antes de dar un módulo por terminado

- [ ] Tiene una sola responsabilidad y un nombre que la describe.
- [ ] Sus `import` respetan el mapa de la sección 3.
- [ ] No lee ni escribe variables globales ajenas.
- [ ] Si es una vista: cumple el contrato y se registra sola.
- [ ] Si dibuja: `render` no provoca efectos secundarios.
- [ ] Si escucha eventos: los enlaza en `mount`, no en `render`.
- [ ] No deja `console.log` ni código muerto.
- [ ] Pasa la prueba de módulos y la del editor sin errores de consola.
