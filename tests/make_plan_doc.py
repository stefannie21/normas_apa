"""Genera inf/Plan_IA_y_Criterios_APA.docx con el documento de planificación:
revisión del bosquejo, contraste con la guía APA 7, brechas, arquitectura por
capas, ubicación de la IA y plan por fases."""
from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Inches, Pt, RGBColor

OUT = r"inf\Plan_IA_y_Criterios_APA.docx"
AZUL = RGBColor(0x18, 0x5A, 0xBD)
GRIS = RGBColor(0x44, 0x4C, 0x56)

doc = Document()

# --- formato general ---
for section in doc.sections:
    section.top_margin = section.bottom_margin = Inches(1)
    section.left_margin = section.right_margin = Inches(1)

normal = doc.styles["Normal"]
normal.font.name = "Times New Roman"
normal.font.size = Pt(12)
normal.paragraph_format.line_spacing = 2.0
normal.paragraph_format.space_after = Pt(0)


def h1(text):
    p = doc.add_heading(text, level=1)
    for r in p.runs:
        r.font.color.rgb = AZUL
        r.font.name = "Times New Roman"
    return p


def h2(text):
    p = doc.add_heading(text, level=2)
    for r in p.runs:
        r.font.color.rgb = AZUL
        r.font.name = "Times New Roman"
    return p


def par(text, bold=False, italic=False, size=12, align=None, space_after=0):
    p = doc.add_paragraph()
    r = p.add_run(text)
    r.bold = bold
    r.italic = italic
    r.font.size = Pt(size)
    r.font.name = "Times New Roman"
    if align is not None:
        p.alignment = align
    p.paragraph_format.space_after = Pt(space_after)
    return p


def bullet(text, bold_prefix=None):
    p = doc.add_paragraph(style="List Bullet")
    if bold_prefix:
        r = p.add_run(bold_prefix)
        r.bold = True
        r.font.size = Pt(12)
        r.font.name = "Times New Roman"
    r = p.add_run(text)
    r.font.size = Pt(12)
    r.font.name = "Times New Roman"
    p.paragraph_format.line_spacing = 1.5
    p.paragraph_format.space_after = Pt(2)
    return p


def table(headers, rows, widths=None):
    t = doc.add_table(rows=1, cols=len(headers))
    t.style = "Light Grid Accent 1"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    for i, text in enumerate(headers):
        cell = t.rows[0].cells[i]
        cell.text = ""
        r = cell.paragraphs[0].add_run(text)
        r.bold = True
        r.font.size = Pt(10)
        r.font.name = "Times New Roman"
        cell.paragraphs[0].paragraph_format.line_spacing = 1.0
    for row in rows:
        cells = t.add_row().cells
        for i, value in enumerate(row):
            cells[i].text = ""
            p = cells[i].paragraphs[0]
            r = p.add_run(str(value))
            r.font.size = Pt(10)
            r.font.name = "Times New Roman"
            p.paragraph_format.line_spacing = 1.0
            p.paragraph_format.space_after = Pt(2)
    if widths:
        for row in t.rows:
            for i, w in enumerate(widths):
                row.cells[i].width = Inches(w)
    doc.add_paragraph().paragraph_format.space_after = Pt(6)
    return t


# ======================= PORTADA =======================
par(
    "PLAN DE AMPLIACIÓN DEL SISTEMA DE VERIFICACIÓN APA",
    bold=True,
    size=16,
    align=WD_ALIGN_PARAGRAPH.CENTER,
)
par(
    "Verificación y corrección asistida de tesis en .docx",
    italic=True,
    size=12,
    align=WD_ALIGN_PARAGRAPH.CENTER,
)
par(
    "Revisión del documento «Revisión de documentos de Asesoría» y de la "
    "«Guía Normas APA 7.ª edición»",
    size=11,
    align=WD_ALIGN_PARAGRAPH.CENTER,
)
doc.add_paragraph()
table(
    ["Campo", "Detalle"],
    [
        ("Sistema", "APA Studio — verificador de documentos .docx"),
        ("Base de código", "FastAPI + python-docx + motor de reglas + vista tipo Word"),
        ("Fuentes analizadas", "inf/bosquejo.docx · inf/Guia-Normas-APA-7ma-edicion (1).pdf"),
        ("Alcance de este documento", "Planificación. No incluye implementación."),
    ],
    widths=[1.5, 5.0],
)

doc.add_page_break()

# ======================= 1. OBJETIVO =======================
h1("1. Objetivo")
par(
    "Definir cómo debe evolucionar el sistema para cubrir el alcance operativo "
    "descrito en el documento de asesoría, que va más allá de validar el formato "
    "APA: incluye gestoría del encargo, cumplimiento de la normativa de cada "
    "universidad, control de versiones y seguimiento de las observaciones del asesor."
)

# ======================= 2. HALLAZGOS =======================
h1("2. Revisión del documento «bosquejo»")
par(
    "El documento de 105 párrafos estructura el servicio en dos bloques muy "
    "distintos, con lógicas diferentes.",
)

h2("2.1 Bloque normativo — criterios APA")
par("Detalla los controles que hoy exige la revisión formal y bibliográfica:")
bullet("Papel Carta, márgenes de 2.54 cm en los cuatro lados.")
bullet("Seis fuentes permitidas, con excepciones para figuras, código y notas al pie.")
bullet("Texto alineado a la izquierda, interlineado doble y sangría de 0.5\" (1.27 cm).")
bullet("Sangría francesa de 1.27 cm en la lista de referencias.")
bullet("Número de página en la esquina superior derecha, numeración desde la portada.")
bullet("Cinco niveles de jerarquía de títulos con formato propio.")
bullet("Sistema autor-fecha: cita narrativa y cita parentética.")
bullet("Regla de autores: hasta dos se citan siempre; tres o más usan «et al.» desde la primera mención.")
bullet("Autor corporativo: nombre completo y sigla entre corchetes en la primera cita.")
bullet("Citas textuales con página obligatoria; bloque de 40 palabras o más sin comillas y con sangría.")
bullet("Referencias en página nueva, título en negrita y centrado, orden alfabético.")
bullet("Autores invertidos; hasta 20 autores se listan, más de 20 se listan 19 y el último.")

h2("2.2 Bloque de gestión — proceso de asesoría")
par("No es APA: es la operación de la asesoría, y es lo que el sistema no cubre.")
bullet("Organizar archivos por versión, universidad, programa y nivel académico.")
bullet("Exigir al cliente la guía metodológica o reglamento de tesis vigente.")
bullet("Validar la estructura y el formato contra la plantilla de la facultad, no solo contra APA.")
bullet("Revisar fondo y forma: coherencia interna, redacción académica y ortotipografía.")
bullet("Control de versiones: comparar la versión previa con la actual.")
bullet("Auditar las observaciones del asesor: anotaciones marginales, comentarios y fichas.")
bullet("Extraer acuerdos de las reuniones grabadas y cruzarlos con lo escrito.")

h2("2.3 Contraste con la «Guía Normas APA 7.ª edición» (57 páginas)")
par(
    "La guía, elaborada a partir de normas-apa.org, confirma la Almost的全部 criterios "
    "del bloque normativo. Se verificaron dos puntos sensibles:"
)
bullet(
    "Los 20 autores y la regla de 19 + puntos suspensivos + último autor son el cambio "
    "de la 7.ª edición respecto de la 6.ª. El bosquejo lo recoge correctamente (pág. 47 de la guía)."
)
bullet(
    "La redacción del bosquejo pide «Cada Palabra Iniciando en Mayúscula» también en el "
    "nivel 3. La guía pide ese estilo en los niveles 1 y 2; el nivel 3 añade cursiva, no "
    "mayúsculas adicionales. No es un conflicto, pero conviene separarlo en el validador."
)
par(
    "Conclusión: el bosquejo es un documento de requisitos fiable y utilizable como "
    "especificación. Sirve como checklist contra el que medir el sistema.",
    bold=True,
)

doc.add_page_break()

# ======================= 3. BRECHAS =======================
h1("3. Brecha actual frente a los requisitos")

h2("3.1 Lo que el sistema ya verifica (20 reglas)")
table(
    ["Bloque", "Reglas actuales"],
    [
        ("Formato", "Márgenes, tipografías, tamaños, interlineado doble, alineación, sangría, espaciado"),
        ("Títulos", "Jerarquía, formato por nivel, títulos sin estilo de Word"),
        ("Citas", "Autor y año, «&» frente a «and», «et al.», página en cita textual"),
        ("Referencias", "Presencia, año, sangría francesa, orden alfabético, DOI como URL"),
    ],
    widths=[1.4, 5.1],
)

h2("3.2 Lo que falta, por valor")
table(
    ["Requisito del bosquejo", "Por qué importa", "Prioridad"],
    [
        (
            "Cruce cita ↔ referencia, en ambos sentidos",
            "Requisito explícito: toda cita debe tener referencia y ninguna referencia debe sobrar. Hoy no se verifica ninguna de las dos direcciones.",
            "Alta",
        ),
        (
            "Referencias por tipo de fuente",
            "Cursiva en libro, tesis o informe; en artículo solo el contenedor. Hoy no se distingue el tipo.",
            "Alta",
        ),
        (
            "«et al.» desde la primera mención con tres o más autores",
            "Hoy solo se verifica el punto final, no el umbral de autores.",
            "Alta",
        ),
        (
            "Cita en bloque de 40 palabras o más",
            "Sin comillas, sin cursiva, sangría de 1.27 cm, punto antes del paréntesis. No existe la regla.",
            "Media",
        ),
        (
            "Punto final según el tipo de cita",
            "Después del paréntesis en citas cortas; antes en cita en bloque.",
            "Media",
        ),
        (
            "Autor corporativo con sigla entre corchetes",
            "Primera cita con nombre completo, siguientes solo con la sigla.",
            "Media",
        ),
        (
            "Hasta 20 autores y regla de más de 20",
            "Incluye la lista invertida de nombres.",
            "Media",
        ),
        (
            "Numeración desde la portada",
            "Página 1 en la portada y角 superior derecha en todas.",
            "Baja",
        ),
        (
            "Plantilla institucional de la universidad",
            "Es lo primero que pide el asesor y obliga a solicitar un segundo archivo al cliente.",
            "Alta",
        ),
        (
            "Control de versiones",
            "Comparar con la versión anterior para ver qué observaciones se subsanaron.",
            "Media",
        ),
        (
            "Clasificación del encargo",
            "Universidad, programa y nivel. Hoy no existen datos del cliente.",
            "Media",
        ),
    ],
    widths=[1.9, 3.6, 0.9],
)

# ======================= 4. ARQUITECTURA =======================
doc.add_page_break()
h1("4. Arquitectura propuesta")
par(
    "Seis capas. Las dos primeras no requieren inteligencia artificial y son las que "
    "convierten el producto de verificador de APA en sistema de asesoría."
)
par(
    "Cliente/Encargo → Perfil de norma → Extracción → Reglas → IA acotada → Aplicación + Bitácora",
    bold=True,
    align=WD_ALIGN_PARAGRAPH.CENTER,
)

h2("4.1 Capa 0 — Ficha del encargo (nueva)")
par(
    "Universidad, programa, nivel académico, guía institucional y versión del documento. "
    "Es el requisito del apartado 2.2 que exige al cliente su reglamento de tesis. "
    "Implica el cambio arquitectónico más relevante: el sistema actual no guarda estado."
)

h2("4.2 Capa 1 — Perfil de norma (nueva)")
par(
    "Dos perfiles: APA estricto o plantilla institucional. La guía de la universidad se "
    "sube como archivo y sus reglas se extraen al perfil (márgenes, fuentes, secciones "
    "exigidas y estructura). Es lo que hace útil el sistema para un asesor real."
)

h2("4.3 Capa 2 — Extracción estructurada")
par(
    "El parser ya lee el XML del documento, de modo que la extensión es natural: se "
    "extraen dos listas tipadas, citas y referencias, con autor, año, título, contenedor, "
    "volumen, páginas, DOI, cursivas, página estimada y párrafo. Sin esta capa las "
    "reglas nuevas no pueden funcionar."
)

h2("4.4 Capa 3 — Motor de reglas")
par(
    "Las reglas nuevas se suman a las veinte actuales sin cambiar la arquitectura: son "
    "archivos nuevos que implementan la misma interfaz de comprobación."
)

h2("4.5 Capa 4 — IA acotada")
par(
    "Tres encargos: clasificar el tipo de fuente y detectar elementos faltantes, proponer "
    "la referencia canónica cuando el patrón no se reconoce, y evaluar coherencia "
    "semántica y redacción. Toda salida lleva confianza; por debajo del umbral es sugerencia, "
    "nunca aplicación automática."
)

h2("4.6 Capa 5 — Aplicación y bitácora")
par(
    "Correcciones quirúrgicas sobre el .docx original, solo de tipo mecánico, con registro "
    "de antes y después. Ese registro es el insumo del control de versiones."
)

# ======================= 5. IA =======================
doc.add_page_break()
h1("5. Dónde incluir la IA")

h2("5.1 Principio")
par(
    "El motor de reglas es el juez y la IA es el analista. La IA no escribe en el documento. "
    "Si la IA edita el .docx, aparecerán referencias inventadas, y eso es plagio no "
    "intencionado: el peor fallo posible en este producto.",
    bold=True,
)

h2("5.2 Reparto de responsabilidades")
table(
    ["Tarea", "Motor", "Motivo"],
    [
        ("Formato, márgenes, jerarquía, sangrías", "Regla", "Verificable y reproducible"),
        (
            "¿Cita tiene referencia? ¿Referencia sin citar?",
            "IA",
            "Exige comparar nombres con variantes: «García» y «Garcia», «et al.» frente a la lista completa",
        ),
        ("¿Qué tipo de fuente es?", "IA", "El patrón es ambiguo entre idiomas y convenciones"),
        ("¿Cumple el formato APA de ese tipo?", "Regla", "Determinista una vez que el tipo está tipado"),
        ("Redacción y ortotipografía", "IA, sin auto Corrección", "Requisito de fondo y forma"),
        ("Orden, cursivas, sangría francesa, «&»", "Regla más aplicación", "Mecánico y reversible"),
        ("Inventar o completar una referencia", "Prohibido", "Riesgo académico directo"),
    ],
    widths=[2.1, 1.6, 2.8],
)

h2("5.3 Restricción de contexto")
par(
    "La IA recibe únicamente el JSON de citas y referencias, nunca la tesis completa. "
    "Reduce coste, reduce alucinación y hace auditable cada decisión."
)

h2("5.4 Lo que la IA no debe hacer nunca")
bullet("Escribir o reescribir contenido del documento sin confirmación humana.")
bullet("Participar en el conteo de páginas ni en el formato; ahí son más fiables el navegador y la librería.")
bullet("Sugerir una referencia que no exista ya en el documento.")

# ======================= 6. FASES =======================
doc.add_page_break()
h1("6. Plan por fases")
table(
    ["Fase", "Contenido", "Riesgo", "Valor"],
    [
        ("1", "Extracción estructurada y reglas de citas y referencias, incluido el cruce", "Nulo", "Alto"),
        ("2", "Ficha del encargo y perfil de plantilla institucional", "Bajo", "Alto"),
        ("3", "IA para cruce y clasificación de fuentes", "Bajo", "Medio-alto"),
        ("4", "Correcciones automáticas seguras y exportación del .docx corregido", "Medio", "Alto"),
        ("5", "Control de versiones y auditoría de observaciones del asesor", "Bajo", "Medio"),
    ],
    widths=[0.6, 3.6, 0.9, 1.1],
)
par(
    "Las fases 1 y 2 no requieren IA ni clave de API. Son la base sobre la cual la IA deja "
    "de inventar.",
    bold=True,
)

# ======================= 7. PUNTOS DE INTEGRACIÓN =======================
h1("7. Puntos donde el código actual facilita el trabajo")
bullet("La interfaz de reglas ya está definida; las nuevas son archivos nuevos, no un rediseño.", bold_prefix="Motor de reglas. ")
bullet("Los hallazgos ya transportan datos estructurados y el modal de títulos sin estilo demuestra cómo agruparlos.", bold_prefix="Datos estructurados. ")
bullet("El backend ya lee el XML del documento, con el mismo criterio se extraen las reglas del reglamento institucional.", bold_prefix="Lectura directa del XML. ")
bullet("El generador de informe es el lugar natural para la bitácora de correcciones.", bold_prefix="Informe. ")
bullet("La vista web ya muestra páginas con la geometría real de cada sección del documento.", bold_prefix="Visualización. ")

# ======================= 8. RECOMENDACIÓN =======================
h1("8. Recomendación")
par(
    "Empezar por la fase 1. Es la que cierra el requisito que el propio documento de "
    "asesoría marca como obligatorio: que toda cita tenga su referencia y que ninguna "
    "referencia quede sin citar. No necesita IA, no tiene riesgo y es la que más valor "
    "aporta por unidad de esfuerzo."
)
par(
    "La segunda decisión es de producto, no técnica: si conviene atacar primero la fase 1 "
    "(más valor técnico inmediato) o la fase 2 (más cambio en el producto, porque el asesor "
    "necesita validar contra la norma de su universidad, no solo contra APA)."
)

doc.save(OUT)
print("OK:", OUT)