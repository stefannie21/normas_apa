# Normas APA — Sistema de revisión de tesis

Sistema web para una empresa de asesoramiento de tesis: se abre un documento
(tesis o proyecto de tesis en formato `.docx`), se edita en un visor tipo Word y
se verifica su cumplimiento con las **normas APA (7.ª edición)**.

## Qué hace

- **Verifica** el documento contra 29 reglas programadas (formato de página,
  tipografía, interlineado, sangría, títulos, citas en texto y lista de
  referencias) y devuelve un informe con errores, avisos y observaciones.
- **Señala** cada problema dentro del propio texto, con colores por gravedad, y
  un globito con la regla, el mensaje y la recomendación de la norma.
- **Corrige** automáticamente lo que es mecánico y reversible (interlineado,
  espacios, sangrías, márgenes, `et al.`, `&`, orden de referencias, cursivas),
  con vista previa, selección y deshacer.
- **No toca nunca** el contenido, los autores ni los años: eso se resuelve a
  mano, y por eso aparece señalado en lugar de corregido.
- Revisión opcional por IA (Gemini) como segunda opinión, solo de lectura.
- Guarda la sesión en el navegador (IndexedDB) para no perder el trabajo.

> Aviso: este informe es una ayuda automática. No sustituye la revisión de un
> asesor humano.

## Requisitos

- Python 3.10 o superior
- Navegador moderno (Chrome, Edge o Firefox)

## Ejecución

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --reload
```

Abrir <http://127.0.0.1:8000>. La documentación de la API queda en
<http://127.0.0.1:8000/docs>.

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
  commands.js            Comandos de edición y estilos
  fixer.js               Correcciones automáticas
  marker.js              Señalamiento de errores en el texto
  storage.js             Guardado local (IndexedDB)
  icons.js               Iconos
  vendor/                mammoth.browser.min.js (docx -> HTML, local)
tests/                   Pruebas y generadores de documentos de muestra
inf/                     Documentación de trabajo del proyecto
```

## Limitación conocida

El verificador analiza el `.docx` **original** que se abrió, no el estado
editado en pantalla. Por eso el porcentaje de cumplimiento no baja al aplicar
correcciones: las correcciones se aplican al documento del editor y las marcas
se actualizan, pero la puntuación requiere volver a verificar el archivo.