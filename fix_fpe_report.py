"""
Corrige el documento FPE:
1. Reescribe el PEA con operaciones orientadas al documento (PEA IV Semestre)
2. Amplia las caracteristicas de equipos informaticos
"""

from docx import Document
from docx.shared import Pt

SRC = r'C:\Users\USER\Desktop\informes\informe de practicas\CNIU-108 INFORME FPE (Sem 23Oct-03Nov).docx'


def set_para_text(para, text):
    if not para.runs:
        para.add_run(text)
        return
    para.runs[0].text = text
    for run in para.runs[1:]:
        run.text = ''


def set_cell_text(cell, text):
    paras = cell.paragraphs
    if not paras:
        cell.add_paragraph(text)
        return
    p = paras[0]
    if p.runs:
        p.runs[0].text = text
        for run in p.runs[1:]:
            run.text = ''
    else:
        p.add_run(text)
    for extra in paras[1:]:
        extra._element.getparent().remove(extra._element)


def set_cell_multiline(cell, lines):
    paras = cell.paragraphs
    first = True
    for line in lines:
        if first and paras:
            p = paras[0]
            if p.runs:
                p.runs[0].text = line
                for run in p.runs[1:]:
                    run.text = ''
            else:
                p.add_run(line)
            first = False
        else:
            new_p = cell.add_paragraph()
            new_p.add_run(line)
    used = len(lines)
    all_paras = cell.paragraphs
    for extra in all_paras[used:]:
        extra._element.getparent().remove(extra._element)


doc = Document(SRC)
paragraphs = doc.paragraphs
t1 = doc.tables[1]

# ============================================================
# 1. REESCRIBIR PEA - Operaciones orientadas al DOCUMENTO
# ============================================================

# --- Operacion 01: Levantar y procesar la informacion del documento ---
set_cell_text(t1.rows[2].cells[0], " 01")
set_cell_text(t1.rows[2].cells[1], "OPERACIONES/TAREAS")

op1_items = [
    "Levantar y procesar la informacion del documento: mejora del visor para reproducir fielmente el .docx como Word",
    "Implementacion de la vista PDF fiel del documento mediante el endpoint /api/docx-pdf con boton en la pestana Vista",
    "Correccion del scrollbar horizontal y centrado de hojas anchas para visualizar correctamente el documento en pantalla",
    "Deteccion de orientacion landscape/portrait del documento y seguimiento de secciones del paginador por pagina",
    "Lectura e interpretacion del documento: separacion en nodos navegables (parrafos, titulos, citas, tablas, figuras y referencias)",
    "Tarjeta de Recien abiertos en el panel Inicio para acceder rapidamente a documentos procesados anteriormente",
    "Aplicacion del formato corregido (fuente y tamano) en todo el cuerpo del documento .docx incluyendo tablas",
]

for i, txt in enumerate(op1_items):
    ri = 3 + i
    set_cell_text(t1.rows[ri].cells[0], " ")
    set_cell_text(t1.rows[ri].cells[1], txt)
    set_cell_text(t1.rows[ri].cells[2], "X")
    for ci in [3, 4, 5, 6]:
        set_cell_text(t1.rows[ri].cells[ci], "")

# --- Operacion 02: Aplicar normativas academicas y de formato ---
set_cell_text(t1.rows[10].cells[0], " 02")
set_cell_text(t1.rows[10].cells[1], "Aplicar normativas academicas y de formato al documento")
set_cell_text(t1.rows[10].cells[2], "")
set_cell_text(t1.rows[10].cells[3], "X")
for ci in [4, 5, 6]:
    set_cell_text(t1.rows[10].cells[ci], "")

op2_items = [
    "Validacion de la regla HEAD-005: deteccion de subtitulos numerados (3., 3.1, 1)) que la norma APA 7 no admite en titulos",
    "Aplicacion de correcciones de formato (fuente, interlineado, sangria y alineacion) en el cuerpo completo del documento",
    "Correccion del formato dentro de tablas del documento para que hereden la tipografia y tamano correctos",
    "Excepciones de portada (HEAD-004/FORMAT-003): la primera pagina no se valida como titulo sin estilo asignado",
    "Prueba de regresion del cruce citas-referencias (caso CRUCE-001) con deteccion de 'et al.' para tres o mas autores",
]

for i, txt in enumerate(op2_items):
    ri = 11 + i
    set_cell_text(t1.rows[ri].cells[0], " ")
    set_cell_text(t1.rows[ri].cells[1], txt)
    set_cell_text(t1.rows[ri].cells[2], "")
    set_cell_text(t1.rows[ri].cells[3], "X")
    for ci in [4, 5, 6]:
        set_cell_text(t1.rows[ri].cells[ci], "")

# --- Operacion 03: Ejecutar correcciones y edicion de documentos ---
set_cell_text(t1.rows[16].cells[0], "03\n ")
set_cell_text(t1.rows[16].cells[1], "Ejecutar correcciones y edicion del documento")
set_cell_text(t1.rows[16].cells[2], "")
set_cell_text(t1.rows[16].cells[3], "x")
for ci in [4, 5, 6]:
    set_cell_text(t1.rows[16].cells[ci], "")

op3_items = [
    "Interfaz de edicion del documento: barra de acciones y barra horizontal visibles unicamente en modo edicion",
    "Ribbon con herramientas organizadas en pestanas (Inicio, Insertar, Revisar APA y Vista) separadas del panel Inicio",
    "Zona de subir el documento (.docx) mediante drag and drop con modal de carga y previsualizacion tipo Word",
    "Boton de eliminar con tacho de basura para descartar el documento cargado y sin acciones rapidas innecesarias",
    "Eliminacion de la zona de arrastre del panel Inicio manteniendo el modal como via unica de carga del documento",
]

for i, txt in enumerate(op3_items):
    ri = 17 + i
    set_cell_text(t1.rows[ri].cells[0], " ")
    set_cell_text(t1.rows[ri].cells[1], txt)
    set_cell_text(t1.rows[ri].cells[2], "")
    set_cell_text(t1.rows[ri].cells[3], "X")
    for ci in [4, 5, 6]:
        set_cell_text(t1.rows[ri].cells[ci], "")

# --- Operacion 04: Emitir el informe tecnico de resultados ---
set_cell_text(t1.rows[22].cells[0], "04")
set_cell_text(t1.rows[22].cells[1], "Emitir el informe tecnico de resultados del documento")
set_cell_text(t1.rows[22].cells[2], "")
set_cell_text(t1.rows[22].cells[3], "")
set_cell_text(t1.rows[22].cells[4], "X")
for ci in [5, 6]:
    set_cell_text(t1.rows[22].cells[ci], "")

op4_items = [
    "Vista de Reportes como tabla CRUD para visualizar los hallazgos del informe con chips de estado, filtros por columna y tarjetas de estadisticas con anillo de cumplimiento (score-ring)",
    "Tabla de hallazgos del informe tecnico con detalle de observaciones, ubicacion (pagina y parrafo), severidad y estado de correccion del documento",
    "Generacion del dictamen tecnico conservado entre reinicios del servidor, favicon propio del sistema y push final al repositorio de GitHub",
]

for i, txt in enumerate(op4_items):
    ri = 23 + i
    set_cell_text(t1.rows[ri].cells[0], " ")
    set_cell_text(t1.rows[ri].cells[1], txt)
    set_cell_text(t1.rows[ri].cells[2], "")
    set_cell_text(t1.rows[ri].cells[3], "")
    set_cell_text(t1.rows[ri].cells[4], "X")
    for ci in [5, 6]:
        set_cell_text(t1.rows[ri].cells[ci], "")

# Row 26 empty
for ci in range(7):
    set_cell_text(t1.rows[26].cells[ci], "")

# ============================================================
# 2. ACTUALIZAR TAREA SIGNIFICATIVA - PEA cumplido (paras 131-135)
# ============================================================
set_para_text(paragraphs[131], "Levantar y procesar la informacion del documento: mejora del visor para reproducir fielmente el .docx como Word, con deteccion de orientacion landscape/portrait, scrollbar horizontal y separacion en nodos navegables.")
set_para_text(paragraphs[132], "Aplicar normativas academicas y de formato: validacion de la regla HEAD-005 para subtitulos numerados, aplicacion del formato corregido en todo el cuerpo del documento y prueba de regresion del cruce citas-referencias.")
set_para_text(paragraphs[133], "Ejecutar correcciones y edicion del documento: interfaz de edicion con ribbon organizado en pestanas, barra de acciones visible solo en modo edicion y zona de carga del .docx mediante drag and drop.")
set_para_text(paragraphs[134], "Emitir el informe tecnico de resultados: vista de Reportes como tabla CRUD con chips de estado, tarjetas de estadisticas con anillo de cumplimiento y tabla de hallazgos con detalle de observaciones.")
set_para_text(paragraphs[135], "Garantizar la persistencia y verificacion: el informe se conserva entre reinicios del servidor, el sistema arranca en la vista Inicio y todos los cambios se publicaron en GitHub tras pasar la suite de pruebas.")

# ============================================================
# 3. AMPLIAR CARACTERISTICAS DE EQUIPOS INFORMATICOS
# ============================================================
# Para 159: header (keep as is)
# Para 160-162: detailed equipment

set_para_text(paragraphs[160], "Computadora de escritorio: procesador Intel Core i5-10400 (6 nucleos, 12 hilos, frecuencia base 2.9 GHz, turbo hasta 4.3 GHz), memoria RAM 8GB DDR4 a 2666 MHz, almacenamiento SSD de 512GB NVMe M.2, sistema operativo Windows 11 Pro 64 bits.")

set_para_text(paragraphs[161], "Monitor LED ASUS 24 pulgadas (modelo VA24EHE), resolucion Full HD 1920x1080 px, tasa de refresco 75 Hz, conexion HDMI; teclado logico USB y mouse optico USB. Conexion a red por cable Ethernet 1000 Mbps y WiFi 802.11ac.")

set_para_text(paragraphs[162], "Software: VS Code 1.90 (editor de codigo), Git 2.40 (control de versiones), Python 3.11 con FastAPI 0.104 (backend), Node.js 22 con mammoth.js 1.6 (frontend y renderizado de .docx), Google Chrome (navegador para pruebas), GitHub como repositorio remoto.")

# Add extra paragraph for more equipment if para 163 exists
if len(paragraphs) > 163:
    set_para_text(paragraphs[163], "Servidor local: el sistema APA Studio se ejecuta en el puerto 8010 mediante uvicorn (ASGI) sobre el equipo descrito, sin requerir hardware adicional.")

# ============================================================
# SAVE
# ============================================================
doc.save(SRC)
print("Documento corregido exitosamente.")
print("- PEA reescrito con operaciones orientadas al documento")
print("- Equipos informaticos con caracteristicas detalladas")
