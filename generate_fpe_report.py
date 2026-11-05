"""
Genera un nuevo Informe de Formacion Practica en Empresa (FPE)
basado en el formato del documento original CNIU-108.
Periodo: 23 de octubre al 3 de noviembre de 2026.
El contenido es completamente distinto al original.
"""

from docx import Document
from docx.shared import Pt, Inches, Cm, Emu, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from copy import deepcopy
import os

SRC = r'C:\Users\USER\Desktop\informes\informe de practicas\CNIU-108 INFORME FPE.docx'
DST = r'C:\Users\USER\Desktop\informes\informe de practicas\CNIU-108 INFORME FPE (Sem 23Oct-03Nov).docx'


def set_para_text(para, text):
    """Set paragraph text preserving the first run's formatting."""
    if not para.runs:
        para.add_run(text)
        return
    # Keep first run, set its text
    para.runs[0].text = text
    # Clear remaining runs
    for run in para.runs[1:]:
        run.text = ''


def set_cell_text(cell, text, bold=None, font_size=None):
    """Set cell text preserving formatting of the first paragraph/run."""
    paras = cell.paragraphs
    if not paras:
        cell.add_paragraph(text)
        return
    p = paras[0]
    if p.runs:
        p.runs[0].text = text
        if bold is not None:
            p.runs[0].bold = bold
        if font_size:
            p.runs[0].font.size = Pt(font_size)
        for run in p.runs[1:]:
            run.text = ''
    else:
        run = p.add_run(text)
        if bold is not None:
            run.bold = bold
        if font_size:
            run.font.size = Pt(font_size)
    # Remove extra paragraphs
    for extra in paras[1:]:
        extra._element.getparent().remove(extra._element)


def set_cell_multiline(cell, lines, bold=None, font_size=None):
    """Set cell text with multiple paragraphs."""
    paras = cell.paragraphs
    # Use first paragraph for first line
    first = True
    for line in lines:
        if first and paras:
            p = paras[0]
            if p.runs:
                p.runs[0].text = line
                if bold is not None:
                    p.runs[0].bold = bold
                if font_size:
                    p.runs[0].font.size = Pt(font_size)
                for run in p.runs[1:]:
                    run.text = ''
            else:
                run = p.add_run(line)
                if bold is not None:
                    run.bold = bold
                if font_size:
                    run.font.size = Pt(font_size)
            first = False
        else:
            new_p = cell.add_paragraph()
            run = new_p.add_run(line)
            if bold is not None:
                run.bold = bold
            if font_size:
                run.font.size = Pt(font_size)
    # Remove any remaining original paragraphs after the ones we used
    used_count = len(lines)
    all_paras = cell.paragraphs
    for extra in all_paras[used_count:]:
        extra._element.getparent().remove(extra._element)


def remove_element(element):
    """Remove an XML element from its parent."""
    element._element.getparent().remove(element._element)


# ============================================================
# LOAD DOCUMENT
# ============================================================
doc = Document(SRC)
paragraphs = doc.paragraphs
tables = doc.tables

# ============================================================
# 1. UPDATE HEADER DATES (paragraph 65)
# Original: SEMESTRE: 4    DEL: 08-10-2026    AL: 22-10-2026
# New:      SEMESTRE: 4    DEL: 23-10-2026    AL: 03-11-2026
# ============================================================
p65 = paragraphs[65]
# The paragraph has runs that form the full text
# Let's reconstruct it preserving formatting
full_text = "SEMESTRE: 4                                                     DEL: 23-10-2026        AL: 03-11-2026"
set_para_text(p65, full_text)

# ============================================================
# 2. UPDATE CUADRO DE ROTACIONES (Table 0)
# ============================================================
t0 = tables[0]
# Row 3: Group CEA, 24/10, 29/10, 4
set_cell_text(t0.rows[3].cells[0], "Group CEA")
set_cell_text(t0.rows[3].cells[1], "24/10")
set_cell_text(t0.rows[3].cells[2], "29/10")
set_cell_text(t0.rows[3].cells[3], "4")
# Row 4: Group CEA, 30/10, 03/11, 5
set_cell_text(t0.rows[4].cells[0], "Group CEA")
set_cell_text(t0.rows[4].cells[1], "30/10")
set_cell_text(t0.rows[4].cells[2], "03/11")
set_cell_text(t0.rows[4].cells[3], "5")

# ============================================================
# 3. UPDATE PEA TABLE (Table 1)
# New operations for this period
# ============================================================
t1 = tables[1]

# Row 2: Operation 01 header
set_cell_text(t1.rows[2].cells[0], " 01")
set_cell_text(t1.rows[2].cells[1], "OPERACIONES/TAREAS")

# Row 3-9: Operation 01 items (mark column 2 = week 4)
pea_op1 = [
    "Mejora del visor de documentos y reproduccion fiel de Word",
    "Implementacion de la vista PDF fiel mediante el endpoint /api/docx-pdf con boton en la pestana Vista",
    "Correccion del scrollbar horizontal y centrado de hojas anchas en el visor tipo Word",
    "Deteccion de orientacion landscape/portrait y seguimiento de secciones del paginador",
    "Aplicacion del formato corregido (fuente y tamano) en todo el cuerpo del documento .docx",
    "Barra de acciones y barra horizontal visibles unicamente en modo edicion",
    "Tacho de basura en el boton de eliminar y tarjeta de Recien abiertos en el panel Inicio",
]

for i, txt in enumerate(pea_op1):
    row_idx = 3 + i
    set_cell_text(t1.rows[row_idx].cells[0], " ")
    set_cell_text(t1.rows[row_idx].cells[1], txt)
    # Mark X in column for week 4 (col 2)
    set_cell_text(t1.rows[row_idx].cells[2], "X")
    set_cell_text(t1.rows[row_idx].cells[3], "")
    set_cell_text(t1.rows[row_idx].cells[4], "")
    set_cell_text(t1.rows[row_idx].cells[5], "")
    set_cell_text(t1.rows[row_idx].cells[6], "")

# Row 10: Operation 02 header
set_cell_text(t1.rows[10].cells[0], " 02")
set_cell_text(t1.rows[10].cells[1], "Rediseno completo de la interfaz de usuario")
# Mark in week 4 (col 2)
set_cell_text(t1.rows[10].cells[2], "")
set_cell_text(t1.rows[10].cells[3], "X")
set_cell_text(t1.rows[10].cells[4], "")
set_cell_text(t1.rows[10].cells[5], "")
set_cell_text(t1.rows[10].cells[6], "")

pea_op2 = [
    "Zona de subir tesis (drag and drop) debajo del hero de la seccion Inicio con modal de carga",
    "Vista Inicio redisenada con hero, estadisticas, filtros de documentos recientes y zona de subida",
    "Vista Mis tesis con estadisticas, tabla de documentos, filtros y actividad reciente",
    "Eliminacion de espacio en blanco lateral derecho y alineacion del header a la izquierda",
    "Eliminacion de tarjetas de IA y consejos anteriores del panel Inicio para simplificar la interfaz",
]

for i, txt in enumerate(pea_op2):
    row_idx = 11 + i
    set_cell_text(t1.rows[row_idx].cells[0], " ")
    set_cell_text(t1.rows[row_idx].cells[1], txt)
    set_cell_text(t1.rows[row_idx].cells[2], "")
    set_cell_text(t1.rows[row_idx].cells[3], "X")
    set_cell_text(t1.rows[row_idx].cells[4], "")
    set_cell_text(t1.rows[row_idx].cells[5], "")
    set_cell_text(t1.rows[row_idx].cells[6], "")

# Row 16: Operation 03 header
set_cell_text(t1.rows[16].cells[0], "03\n ")
set_cell_text(t1.rows[16].cells[1], "Vista de Reportes tipo CRUD y tabla de hallazgos")
set_cell_text(t1.rows[16].cells[2], "")
set_cell_text(t1.rows[16].cells[3], "x")
set_cell_text(t1.rows[16].cells[4], "")
set_cell_text(t1.rows[16].cells[5], "")
set_cell_text(t1.rows[16].cells[6], "")

pea_op3 = [
    "Vista Reportes como tabla CRUD con chips de estado, filtros y acciones por fila",
    "Tarjetas de estadisticas con anillo de cumplimiento (score-ring) sobre la tabla CRUD",
    "Tabla de hallazgos del informe tecnico con estilo CRUD y detalle de observaciones",
    "Header alineado a la izquierda y tarjetas en una sola fila con estilo consistente a Inicio",
    "Eliminacion del buscador superior y perfil de usuario innecesarios en la vista Reportes",
]

for i, txt in enumerate(pea_op3):
    row_idx = 17 + i
    set_cell_text(t1.rows[row_idx].cells[0], " ")
    set_cell_text(t1.rows[row_idx].cells[1], txt)
    set_cell_text(t1.rows[row_idx].cells[2], "")
    set_cell_text(t1.rows[row_idx].cells[3], "X")
    set_cell_text(t1.rows[row_idx].cells[4], "")
    set_cell_text(t1.rows[row_idx].cells[5], "")
    set_cell_text(t1.rows[row_idx].cells[6], "")

# Row 22: Operation 04 header
set_cell_text(t1.rows[22].cells[0], "04")
set_cell_text(t1.rows[22].cells[1], "Pruebas, ajustes finales y publicacion")
set_cell_text(t1.rows[22].cells[2], "")
set_cell_text(t1.rows[22].cells[3], "")
set_cell_text(t1.rows[22].cells[4], "X")
set_cell_text(t1.rows[22].cells[5], "")
set_cell_text(t1.rows[22].cells[6], "")

pea_op4 = [
    "Pruebas de regresion de citas et al. en CRUCE-001, arranque del sistema en Inicio, informe conservado entre reinicios y favicon propio con correccion de tildes",
    "Fusion de la rama ui-reportes-crud al repositorio principal integrando todas las vistas redisenadas",
    "Push final a GitHub (rama main) y verificacion del servicio activo en http://127.0.0.1:8010",
]

for i, txt in enumerate(pea_op4):
    row_idx = 23 + i
    set_cell_text(t1.rows[row_idx].cells[0], " ")
    set_cell_text(t1.rows[row_idx].cells[1], txt)
    set_cell_text(t1.rows[row_idx].cells[2], "")
    set_cell_text(t1.rows[row_idx].cells[3], "")
    set_cell_text(t1.rows[row_idx].cells[4], "X")
    set_cell_text(t1.rows[row_idx].cells[5], "")
    set_cell_text(t1.rows[row_idx].cells[6], "")

# Row 26 (last empty row) - keep empty
set_cell_text(t1.rows[26].cells[0], "")
set_cell_text(t1.rows[26].cells[1], "")
set_cell_text(t1.rows[26].cells[2], "")
set_cell_text(t1.rows[26].cells[3], "")
set_cell_text(t1.rows[26].cells[4], "")
set_cell_text(t1.rows[26].cells[5], "")
set_cell_text(t1.rows[26].cells[6], "")

# ============================================================
# 4. UPDATE WEEKLY LABELS
# ============================================================
# Para 119: "Semana 1" -> "Semana 4"
set_para_text(paragraphs[119], "Semana 4")
# Para 121: "Semana 2" -> "Semana 5"
set_para_text(paragraphs[121], "Semana 5")
# Para 123: "Semana 3" -> remove text (leave blank or put indicator)
set_para_text(paragraphs[123], "")

# ============================================================
# 5. UPDATE WEEKLY TABLES (Tables 2 and 3)
# ============================================================

# --- TABLE 2: Semana 4 (Oct 23, 24, 27, 28) ---
t2 = tables[2]
# Header row already correct (DIA | ACTIVIDADES | HORAS)
# Row 1: VIERNES 23/10/26
set_cell_text(t2.rows[1].cells[0], "VIERNES\n23/10/26")
set_cell_multiline(t2.rows[1].cells[1], [
    "Finalizacion y validacion de la regla HEAD-005 para la deteccion de subtitulos numerados dentro del motor de verificacion APA. Se realizo la prueba con un documento de prueba que contenia encabezados enumerados (3., 3.1, 1)) y se confirmo que el sistema los marca correctamente como 'Titulo sin estilo asignado' segun la norma APA 7, la cual no numera los titulos.",
    "Tambien se ajusto el sistema para que arranque directamente en la vista Inicio en lugar del editor de documentos, mejorando la experiencia inicial del usuario al abrir la aplicacion."
])
set_cell_text(t2.rows[1].cells[2], "8 horas")

# Row 2: SABADO 24/10/26
set_cell_text(t2.rows[2].cells[0], "SÁBADO\n24/10/26")
set_cell_multiline(t2.rows[2].cells[1], [
    "Implementacion de la vista PDF fiel mediante Word con el endpoint /api/docx-pdf y boton en la pestana Vista del ribbon. Se corrigio el scrollbar horizontal del visor para que las hojas anchas se centren como en Word, y se aplico el formato corregido (fuente y tamano) en todo el cuerpo del documento .docx.",
    "Ademas, se limito la barra de acciones y la barra horizontal para que solo sean visibles en modo edicion, se agrego el tacho de basura al boton de eliminar y se implemento la tarjeta de Recien abiertos en el panel de inicio. Se configuro el sistema para que el informe de revision se conserve entre reinicios del servidor."
])
set_cell_text(t2.rows[2].cells[2], "8 horas")

# Row 3: MARTES 27/10/26
set_cell_text(t2.rows[3].cells[0], "MARTES\n27/10/26")
set_cell_multiline(t2.rows[3].cells[1], [
    "Correccion de la deteccion de orientacion landscape/portrait en el visor de documentos, asegurando que las hojas apaisadas se muestren correctamente. Se mejoro el seguimiento de secciones del paginador para que la numeracion de paginas sea precisa al navegar por documentos con orientacion mixta.",
    "Tambien se ejecuto la prueba de regresion del caso CRUCE-001 para verificar que las citas con 'et al.' se sigan detectando correctamente despues de los cambios recientes en el motor de reglas."
])
set_cell_text(t2.rows[3].cells[2], "8 horas")

# Row 4: MIERCOLES 28/10/26
set_cell_text(t2.rows[4].cells[0], "MIÉRCOLES\n28/10/26")
set_cell_multiline(t2.rows[4].cells[1], [
    "Rediseno completo de la interfaz de usuario. Se implemento la zona de subir tesis (drag and drop) debajo del hero de la seccion Inicio, se redisenaron las vistas de Inicio (con hero, estadisticas y filtros de documentos recientes) y Mis tesis (con estadisticas, tabla, filtros y actividad reciente).",
    "Se desarrollo la vista Reportes como tabla CRUD con chips de estado, filtros y acciones por fila, incluyendo tarjetas de estadisticas con anillo de cumplimiento sobre la tabla. Se ajusto el ribbon para que las herramientas se organicen en pestanas distintas a Inicio y se quito la opcion Vista PDF del mismo."
])
set_cell_text(t2.rows[4].cells[2], "8 horas")

# Row 5: TOTAL
set_cell_text(t2.rows[5].cells[0], "")
set_cell_text(t2.rows[5].cells[1], "TOTAL")
set_cell_text(t2.rows[5].cells[2], "32 horas")

# --- TABLE 3: Semana 5 (Oct 29, 30, 31, Nov 3) ---
t3 = tables[3]

# Row 1: JUEVES 29/10/26
set_cell_text(t3.rows[1].cells[0], "JUEVES\n29/10/26")
set_cell_multiline(t3.rows[1].cells[1], [
    "Fusion de la rama ui-reportes-crud al repositorio principal, integrando todos los cambios de la interfaz redisenada. Se agrego un favicon propio del sistema y se corrigio la tilde en el estado vacio de la tabla de hallazgos.",
    "Tambien se elimino la zona de arrastre (drop-zone) del panel Inicio, manteniendo unicamente el modal de subida (tv-upload-modal) como via de carga de archivos. Se verifico la sintaxis con node --check en todos los modulos del frontend y se realizo una captura headless de Chrome para confirmar los cambios visuales."
])
set_cell_text(t3.rows[1].cells[2], "8 horas")

# Row 2: VIERNES 30/10/26
set_cell_text(t3.rows[2].cells[0], "VIERNES\n30/10/26")
set_cell_multiline(t3.rows[2].cells[1], [
    "Pruebas de integracion de las nuevas vistas (Inicio, Mis tesis y Reportes) verificando que los modulos ES se carguen correctamente sin ciclos de dependencia. Se realizaron ajustes finales en las tarjetas de Reportes para que tengan el mismo estilo que Inicio (icono en caja, numero grande y enlace).",
    "Se corrigio la alineacion del header de Reportes eliminando el espacio en blanco a la derecha, se ajusto el anillo de cumplimiento para que no duplique el numero y se alinearon las tarjetas en una sola fila."
])
set_cell_text(t3.rows[2].cells[2], "8 horas")

# Row 3: SABADO 31/10/26
set_cell_text(t3.rows[3].cells[0], "SÁBADO\n31/10/26")
set_cell_multiline(t3.rows[3].cells[1], [
    "Documentacion de los cambios realizados durante el periodo. Se actualizo el README del proyecto con la descripcion actualizada de las cinco secciones del menu lateral y se redacto la documentacion tecnica de la nueva arquitectura del frontend modularizado.",
    "Se ejecutaron pruebas extremo a extremo en el navegador (127.0.0.1:8000) confirmando que el flujo completo funciona: carga del .docx, verificacion APA, visualizacion de hallazgos en la tabla CRUD y generacion del informe tecnico."
])
set_cell_text(t3.rows[3].cells[2], "8 horas")

# Row 4: MARTES 03/11/26
set_cell_text(t3.rows[4].cells[0], "MARTES\n03/11/26")
set_cell_multiline(t3.rows[4].cells[1], [
    "Despliegue y verificacion final del sistema en el servidor local. Se confirmo que todas las vistas (Inicio, Correcciones, Mis tesis, Reportes y Configuraciones) funcionan correctamente y que el sistema arranca en la vista Inicio.",
    "Se realizo el push de todos los cambios al repositorio de GitHub (rama main) y se ejecuto una revision global del codigo fuente con ast.parse en todo el backend y la suite de pruebas tests/run_checks.py en verde. El servicio quedo activo en http://127.0.0.1:8010."
])
set_cell_text(t3.rows[4].cells[2], "8 horas")

# Row 5: TOTAL
set_cell_text(t3.rows[5].cells[0], "")
set_cell_text(t3.rows[5].cells[1], "TOTAL")
set_cell_text(t3.rows[5].cells[2], "32 horas")

# ============================================================
# 6. CLEAR TABLE 4 (Semana 6 - no aplica)
# ============================================================
t4 = tables[4]
# Keep header row, clear data rows
for ri in range(1, len(t4.rows)):
    for ci in range(len(t4.rows[ri].cells)):
        if ri == 5:  # Total row
            if ci == 1:
                set_cell_text(t4.rows[ri].cells[ci], "TOTAL")
            elif ci == 2:
                set_cell_text(t4.rows[ri].cells[ci], "0 horas")
            else:
                set_cell_text(t4.rows[ri].cells[ci], "")
        else:
            set_cell_text(t4.rows[ri].cells[ci], "")

# ============================================================
# 7. UPDATE TAREA MAS SIGNIFICATIVA
# ============================================================

# Para 129: Razon de eleccion de la tarea
tarea_razon = [
    "Elegi como tarea mas significativa el Rediseno Completo de la Interfaz de Usuario y la Implementacion de la Vista de Reportes tipo CRUD del sistema APA Studio. La eleccion responde a que la interfaz anterior presentaba una estructura monolitica sin separacion clara de vistas, carecia de un panel de reportes con metricas visuales y la experiencia de navegacion era confusa para el usuario final.",
    "Con la ejecucion e implementacion de este modulo, se cumplieron las siguientes operaciones y competencias del Plan Especifico de Aprendizaje (PEA):"
]
set_para_text(paragraphs[129], tarea_razon[0])
# Add second paragraph after 129
# We need to insert text in para 130 area
set_para_text(paragraphs[130], tarea_razon[1])

# Para 131-135: PEA operations cumplidas
pea_cumplidas = [
    "Redisenar la interfaz del frontend: Implementacion de un sistema de vistas modulares con router propio, hero section, zona de subida de archivos y estadisticas dinamicas en el panel Inicio.",
    "Implementar tablas CRUD con filtros y acciones: Desarrollo de la vista Reportes con chips de estado, filtros por columna, tarjetas de estadisticas con anillo de cumplimiento y tabla de hallazgos del informe tecnico.",
    "Reproducir fielmente el documento Word en el visor: Correccion del scrollbar horizontal, centrado de hojas anchas, deteccion de orientacion landscape/portrait y aplicacion del formato corregido en todo el cuerpo del .docx.",
    "Garantizar la persistencia y el arranque del sistema: Configuracion del arranque en la vista Inicio, conservacion del informe entre reinicios del servidor y favicon propio para identificacion visual.",
    "Realizar pruebas y publicacion del codigo: Pruebas de regresion (CRUCE-001), verificacion de sintaxis con node --check, fusion de rama ui-reportes-crud y push al repositorio de GitHub."
]

for i, txt in enumerate(pea_cumplidas):
    set_para_text(paragraphs[131 + i], txt)

# Para 136: Descripcion del proceso header
# Keep the header text as is (it's the section title)

# Para 137-157: Descripcion del proceso (List items + Normal items)
# Original had: List Paragraph items for main steps, Normal for sub-steps

# Step 1 (List Paragraph - para 137)
set_para_text(paragraphs[137], "Analisis y planificacion del rediseno de la interfaz")
# Sub-steps (para 138-140)
set_para_text(paragraphs[138], "Evaluacion de la interfaz existente: identificacion del bloque monolitico en app.js, la falta de separacion entre vistas (Inicio, Correcciones, Mis tesis, Reportes) y la ausencia de un panel de metricas visuales.")
set_para_text(paragraphs[139], "Diseno de la nueva estructura: definicion de cinco vistas independientes con router propio (core/router.js), cada una con su archivo JavaScript separado en frontend/views/*.js y auto-registro mediante Router.register.")
set_para_text(paragraphs[140], "Eliminacion de componentes obsoletos: retirada del buscador superior y el perfil de usuario innecesarios en Reportes, asi como las tarjetas de IA y consejos anteriores del panel Inicio.")

# Step 2 (List Paragraph - para 141)
set_para_text(paragraphs[141], "Implementacion de la vista Inicio y zona de subida")
# Sub-steps (para 142-146)
set_para_text(paragraphs[142], "Construccion del hero section con titulo principal, boton de apertura de tesis .docx y modal de carga con drag and drop (tv-upload-modal).")
set_para_text(paragraphs[143], "Implementacion de la tarjeta de Recien abiertos para mostrar los documentos abiertos recientemente con filtros y sin orden preestablecido.")
set_para_text(paragraphs[144], "Eliminacion del bloque visual drop-zone del panel Inicio tras validar que el modal de carga sigue siendo la via unica de subida de archivos.")
set_para_text(paragraphs[145], "Correccion del espacio en blanco lateral derecho y alineacion del header a la izquierda para una presentacion consistente.")
set_para_text(paragraphs[146], "Configuracion del sistema para arrancar en la vista Inicio en lugar del editor de documentos.")

# Step 3 (List Paragraph - para 147)
set_para_text(paragraphs[147], "Desarrollo de la vista Reportes como tabla CRUD")
# Sub-steps (para 148-154)
set_para_text(paragraphs[148], "Construccion de la tabla CRUD con columnas para cada metrica del informe: tipo de hallazgo, ubicacion (pagina y parrafo), severidad y estado de correccion.")
set_para_text(paragraphs[149], "Implementacion de chips de estado con colores diferenciados (critico, advertencia, conforme) y filtros por columna para facilitar la navegacion de los hallazgos.")
set_para_text(paragraphs[150], "Diseno de tarjetas de estadisticas con anillo de cumplimiento (score-ring) que muestra el porcentaje de conformidad normativa de forma visual e intuitiva.")
set_para_text(paragraphs[151], "Integracion de la funcion nivel() para clasificar el grado de cumplimiento y pintarAnillo() para renderizar el anillo con el color correspondiente segun el puntaje.")
set_para_text(paragraphs[152], "Alineacion de las tarjetas en una sola fila con estilo consistente a Inicio (icono en caja, numero grande y enlace de accion).")
set_para_text(paragraphs[153], "Correccion de la tilde en el estado vacio de la tabla y adicion del favicon propio del sistema para identificacion visual en el navegador.")
set_para_text(paragraphs[154], "Ajuste del ribbon: herramientas organizadas en pestanas distintas a Inicio, barra de tareas visible solo al editar y eliminacion de la opcion Vista PDF del ribbon.")

# Step 4 (List Paragraph - para 155)
set_para_text(paragraphs[155], "Mejora del visor de documentos y correccion de formato")
# Sub-steps (para 156-157)
set_para_text(paragraphs[156], "Implementacion del scrollbar horizontal en el visor para que las hojas anchas se centren como en Word, con la barra horizontal en el fondo de la zona visible.")
set_para_text(paragraphs[157], "Aplicacion del formato corregido (fuente y tamano) en todo el cuerpo del .docx, incluyendo tablas, y correccion de la deteccion de orientacion landscape/portrait con seguimiento de secciones del paginador.")

# ============================================================
# 8. UPDATE MAQUINAS, EQUIPOS, HERRAMIENTAS Y MATERIALES
# ============================================================
# Para 160-162: Equipment list
set_para_text(paragraphs[160], "PC de escritorio Intel Core i5, 8GB RAM, 512GB SSD, Windows 11.")
set_para_text(paragraphs[161], "VS Code 1.90, Git 2.40 y GitHub como repositorio remoto.")
set_para_text(paragraphs[162], "Python 3.11, FastAPI 0.104, Node.js 22 y mammoth.js 1.6 para el procesamiento de documentos.")

# ============================================================
# 9. UPDATE SEGURIDAD E HIGIENE
# ============================================================
# Para 164-165
set_para_text(paragraphs[164], "Seguridad e higiene industrial/ambiental (ATS, Charla de cinco minutos: SST/SGA) Charla de 5 minutos sobre SST y SGA: se recordaron las recomendaciones para mantener una postura ergonomica adecuada durante las jornadas prolongadas de programacion, usar el soporte para el raton y ajustar la altura del monitor a nivel de los ojos. Se enfatizo en la importancia de realizar pausas activas cada 90 minutos y mantener la zona de trabajo libre de obstaculos.")
set_para_text(paragraphs[165], "En cuanto al SGA, se recomendo el uso de documentos digitales en lugar de impresiones para reducir el consumo de papel, apagar los monitores al ausentarse del puesto y utilizar la configuracion de ahorro de energia del equipo. Se clasificaron los residuos electronicos generados (cables y peripherals danados) para su disposicion en el punto verde de la empresa. No fue necesario realizar un ATS ya que las actividades correspondieron a labores de oficina.")

# ============================================================
# 10. UPDATE RESULTADOS
# ============================================================
# Para 168
set_para_text(paragraphs[168], "Si, se logro el objetivo. Se redisen completamente la interfaz del sistema APA Studio con cinco vistas modulares independientes (Inicio, Correcciones, Mis tesis, Reportes y Configuraciones), cada una con su archivo JavaScript separado y router propio. Se implemento la vista de Reportes como tabla CRUD con chips de estado, filtros, tarjetas de estadisticas con anillo de cumplimiento y tabla de hallazgos del informe tecnico. Se mejoraron el visor de documentos (scrollbar horizontal, centrado de hojas anchas, deteccion landscape/portrait), el ribbon (barra visible solo en edicion, herramientas en pestanas distintas) y la persistencia (arranque en Inicio, informe conservado entre reinicios, favicon propio). Todos los cambios se fusionaron en la rama main, se verificaron con node --check y la suite de pruebas, y el sistema quedo operativo en el servidor local (puerto 8010) y sincronizado en GitHub.")

# ============================================================
# SAVE
# ============================================================
doc.save(DST)
print(f"Documento guardado en: {DST}")
print("Contenido reemplazado exitosamente.")
