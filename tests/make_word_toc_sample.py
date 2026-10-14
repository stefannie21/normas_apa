"""Genera tests/sample_word_toc.docx que replica un indice de Word real:
campo TOC con entradas hipervinculadas (_Toc bookmarks), numeradas y con pagina al final."""
from docx import Document
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
from docx.shared import Pt

doc = Document()

# --- Titulo del indice ---
doc.add_heading("Índice", level=1)

entries = [
    ("1", "PROBLEMA DE INVESTIGACIÓN", 1, 1),
    ("2", "OBJETIVO GENERAL Y ESPECÍFICOS", 2, 1),
    ("2.1", "Objetivo general", 2, 2),
    ("2.2", "Objetivos específicos", 2, 2),
    ("3", "JUSTIFICACIÓN", 3, 1),
    ("4", "MARCO TEÓRICO", 4, 1),
    ("4.1", "Dependencia al teléfono móvil", 4, 2),
    ("4.1.1", "Dimensiones de la dependencia al teléfono móvil", 4, 3),
]

# --- Campo TOC real: begin / instrText / separate ... resultado ... end ---
p = doc.add_paragraph()
r = p.add_run()
fld = OxmlElement("w:fldChar"); fld.set(qn("w:fldCharType"), "begin"); r._r.append(fld)
r = p.add_run()
instr = OxmlElement("w:instrText"); instr.set(qn("xml:space"), "preserve")
instr.text = ' TOC \\o "1-3" \\h \\z \\u '
r._r.append(instr)
r = p.add_run()
fld = OxmlElement("w:fldChar"); fld.set(qn("w:fldCharType"), "separate"); r._r.append(fld)

for num, title, page, level in entries:
    ep = doc.add_paragraph()
    if num == "1":
        r = ep.add_run()
        fc = OxmlElement("w:fldChar"); fc.set(qn("w:fldCharType"), "begin"); r._r.append(fc)
        r = ep.add_run()
        it = OxmlElement("w:instrText"); it.set(qn("xml:space"), "preserve")
        it.text = f' PAGEREF _Toc{level}{page} \\h '
        r._r.append(it)
        r = ep.add_run()
        fc = OxmlElement("w:fldChar"); fc.set(qn("w:fldCharType"), "separate"); r._r.append(fc)
    # texto de la entrada: numero + titulo + tab + pagina (todo hipervinculado)
    link = OxmlElement("w:hyperlink")
    link.set(qn("w:anchor"), f"_Toc{level}{page}")
    rr = OxmlElement("w:r")
    t = OxmlElement("w:t"); t.text = num + ". " + title
    rr.append(t)
    link.append(rr)
    rr2 = OxmlElement("w:r")
    tab = OxmlElement("w:tab"); rr2.append(tab)
    t2 = OxmlElement("w:t"); t2.text = str(page)
    rr2.append(t2)
    link.append(rr2)
    ep._p.append(link)
    if num == "4.1.1":
        rr3 = OxmlElement("w:r")
        fc = OxmlElement("w:fldChar"); fc.set(qn("w:fldCharType"), "end"); rr3.append(fc)
        ep._p.append(rr3)

doc.add_page_break()

# --- Contenido real ---
doc.add_heading("PROBLEMA DE INVESTIGACIÓN", level=1)
doc.add_paragraph("Descripcion del problema de investigacion.")
doc.add_heading("OBJETIVO GENERAL Y ESPECÍFICOS", level=1)
doc.add_heading("Objetivo general", level=2)
doc.add_paragraph("Objetivo general del trabajo.")
doc.add_heading("Objetivos específicos", level=2)
doc.add_paragraph("Objetivos especificos.")
doc.add_heading("JUSTIFICACIÓN", level=1)
doc.add_paragraph("Justificacion del estudio.")
doc.add_heading("MARCO TEÓRICO", level=1)
doc.add_paragraph("Marco teorico.")
doc.add_heading("Dependencia al teléfono móvil", level=2)
doc.add_paragraph("Dependencia al movil.")
doc.add_heading("Dimensiones de la dependencia al teléfono móvil", level=3)
doc.add_paragraph("Dimensiones.")

doc.save("tests/sample_word_toc.docx")
print("ok")