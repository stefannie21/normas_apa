# Normas APA — Sistema de revisión de tesis

Sistema web para una empresa de asesoramiento de tesis: se abre un documento
(tesis o proyecto de tesis en formato `.docx`), se edita en un visor tipo Word y
se verifica su cumplimiento con las **normas APA (7.ª edición)**.

## Interfaz

Menú lateral con cinco secciones.

- **Inicio** es un panel de situación: la tesis abierta, su nivel de
  cumplimiento, los errores y avisos del último análisis, cómo funciona el
  proceso y el estado de la revisión con IA.
- **Correcciones** es el editor: la cinta de opciones (Inicio, Insertar, Revisar
  APA y Vista), el documento paginado y la barra de estado.
- **Mis tesis**, **Reportes** y **Configuraciones** están preparadas pero **sin
  contenido**: todavía no se ha decidido qué va en cada una.

El menú se pliega con el botón de su base y se recupera con el botón de la barra
de título.

## Índice automático

El índice solo se genera si el documento tiene **un salto de página** o un
**título tipo "Índice"/"Contenido"**. Si no hay ninguno, el programa no inventa
una portada de índice donde el autor no la puso; inserta el índice después del
primer salto de página cuando existe.

## Qué hace

- **Verifica** el documento contra 30 reglas programadas (formato de página,
  tipografía, interlineado, sangría, títulos, citas en texto y lista de
  referencias) y devuelve un informe con errores, avisos y observaciones.
- **Señala** cada problema dentro del propio texto, con colores por gravedad, y
  un globito con la regla, el mensaje y la recomendación de la norma.
- **Corrige** automáticamente lo que es mecánico y reversible (interlineado,
  espacios, sangrías, márgenes, `et al.`, `&`, orden de referencias, cursivas),
  con vista previa, selección y deshacer.
- **No toca nunca** el contenido, los autores ni los años: eso se resuelve a
  mano, y por eso aparece señalado en lugar de corregido.
- **Exporta el documento corregido** a `.docx`, aplicando las correcciones
  directamente sobre el archivo original con `python-docx`.
- **Descarga el informe en Word** (`.docx`) con el resumen de cumplimiento, el
  desglose por categoría y la tabla completa de hallazgos.
- Revisión opcional por IA (Gemini) como segunda opinión, solo de lectura, con
  cascada de modelos y reintentos si el proveedor está saturado.
- Guarda la sesión en el navegador (IndexedDB) para no perder el trabajo, con
  aviso al cerrar si hay cambios sin guardar.
- Historial de cambios con deshacer/rehacer.

> Aviso: este informe es una ayuda automática. No sustituye la revisión de un
> asesor humano.

## Requisitos

- Python 3.10 o superior
- Navegador moderno (Chrome, Edge o Firefox)

## Ejecución

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --port 8000
```

Abrir <http://127.0.0.1:8000>. La documentación de la API queda en
<http://127.0.0.1:8000/docs>.

Si el puerto 8000 ya está ocupado por otro servicio de la máquina, cambiarlo con
`--port 8010` y abrir esa dirección.

## Revisión por IA (opcional)

El motor de reglas funciona sin configuración. Para añadir la revisión por IA:

1. Copiar `.env.example` a `.env`.
2. Definir `GEMINI_API_KEY` (y opcionalmente `AI_MODEL`, `AI_PROVIDER`).
3. Poner `AI_ENABLED=true`.

Si no hay clave, esa parte se omite silenciosamente.

> `.env` está en `.gitignore` y **no debe subirse nunca** al repositorio.

## Pruebas

```powershell
.\.venv\Scripts\python.exe tests\run_checks.py
```

Verifica formato, citas/referencias y el cálculo de cumplimiento. Los
documentos de prueba se regeneran con los scripts `tests/make_*.py`.

## Estructura

```
backend/app/
  main.py                Punto de entrada FastAPI
  config.py              Configuración / variables de entorno
  api/routes.py          Endpoints HTTP
  services/
    docx_parser.py       Lectura y normalización del .docx
    analyzer.py          Orquesta reglas + IA
    report.py            Informe JSON/HTML
    bibliography.py      Extracción de citas y referencias
    ai_reviewer.py       Revisión por LLM (opcional)
    docx_writer.py       Aplica correcciones y devuelve un .docx nuevo
    report_docx.py       Genera el informe APA como .docx descargable
  rules/
    base.py              Tipos base (Finding, Rule, Severity)
    registry.py          Registro de reglas activas
    formatting.py        Formato de página y texto
    headings.py          Títulos y niveles
    citations.py         Citas en el texto
    references.py        Lista de referencias
    cite_format.py       Formato interno de las citas
    ref_format.py        Formato de las referencias
    matching.py          Cruce cita <-> referencia
frontend/
  index.html             Interfaz
  styles.css
  app.js                 Lógica de la app (carga, edición, informe, correcciones)
  pager.js               Paginación tipo Word
  ribbon.js              Ribbon (Inicio, Insertar, Revisar APA, Vista)
  sidebar.js             Menú lateral y vistas
  commands.js            Comandos de edición y estilos
  history.js             Historial de cambios (deshacer/rehacer)
  fixer.js               Correcciones automáticas
  marker.js              Señalamiento de errores en el texto
  storage.js             Guardado local (IndexedDB)
  icons.js               Iconos
  vendor/                mammoth.browser.min.js (docx -> HTML, local)
tests/                   Pruebas y generadores de documentos de muestra
inf/                     Documentación de trabajo del proyecto
```

## Endpoints principales

| Método | Ruta | Qué hace |
|---|---|---|
| `GET` | `/health` | Estado del servicio y de la IA |
| `GET` | `/rules` | Catálogo de reglas activas |
| `POST` | `/api/analyze` | Analiza un `.docx` y devuelve el informe |
| `POST` | `/api/docx-meta` | Geometría y formato de las secciones |
| `POST` | `/api/report/docx` | Informe APA como `.docx` descargable |
| `POST` | `/api/export` | `.docx` corregido con los IDs de reglas aplicados |
| `POST` | `/api/ai/classify` | Segunda opinión por IA (solo lectura) |

## Limitación conocida

El verificador analiza el `.docx` **original** que se abrió, no el estado
editado en pantalla. Por eso el porcentaje de cumplimiento no baja al aplicar
correcciones en el editor: las marcas sí se actualizan, pero la puntuación
sigue reflejando el archivo de partida.

Para obtener una puntuación actualizada hay que **exportar el documento
corregido** (`/api/export`) y volver a abrir ese `.docx` nuevo en la
aplicación.