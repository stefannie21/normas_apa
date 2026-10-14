"""Genera tests/sample_landscape.docx: seccion 1 vertical (cuerpo de la tesis) y
seccion 2 horizontal (apendice con tabla ancha), tal como en Word."""
from docx import Document
from docx.enum.section import WD_ORIENT, WD_SECTION
from docx.shared import Inches, Pt

doc = Document()

# --- Seccion 1: vertical ---
doc.add_heading("Introduccion", level=1)
doc.add_paragraph(
    "Contenido de la seccion vertical. Este parrafo tiene suficientes lineas para "
    "ocupar varias hojas del documento y comprobar que la paginacion vertical "
    "sigue funcionando igual que antes."
)
doc.add_paragraph(
    "Segundo parrafo de la seccion vertical con texto adicional para generar "
    "contenido suficiente y validar el cambio de seccion mas adelante."
)

# --- Seccion 2: horizontal (nueva pagina, orientacion apaisada) ---
sec = doc.add_section(WD_SECTION.NEW_PAGE)
sec.orientation = WD_ORIENT.LANDSCAPE
sec.page_width, sec.page_height = Inches(11), Inches(8.5)
sec.left_margin = Inches(1)
sec.right_margin = Inches(1)
sec.top_margin = Inches(1)
sec.bottom_margin = Inches(1)

doc.add_heading("Apendice: tabla ancha", level=1)
doc.add_paragraph("Esta seccion esta en horizontal; la tabla usa todo el ancho disponible.")

table = doc.add_table(rows=1, cols=6)
table.style = "Table Grid"
hdr = table.rows[0].cells
for i, t in enumerate(["Variable", "Tipo", "Unidad", "Min", "Max", "Fuente"]):
    hdr[i].text = t
for row in [
    ("Ansiedad", "Escala", "1-5", "1.0", "5.0", "Escala de Beck"),
    ("Estres", "Escala", "1-5", "1.0", "5.0", "PSS-10"),
    ("Sueño", "Horas", "h", "4.0", "9.0", "Actigrafia"),
    ("Mobile", "Horas/dia", "h", "1.0", "9.0", "Encuesta"),
]:
    cells = table.add_row().cells
    for i, v in enumerate(row):
        cells[i].text = v

doc.save("tests/sample_landscape.docx")
print("ok")