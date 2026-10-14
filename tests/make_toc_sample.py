"""Genera un .docx con campo TOC (indice) real y varios títulos para probar la conversion."""
from __future__ import annotations

from pathlib import Path

from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

TOC_STYLES = {1: "TOC 1", 2: "TOC 2", 3: "TOC 3"}


def _make_toc_entry(text: str, level: int = 1, page: int = 1):
    """Crea una entrada de indice (parrafo con estilo TOC n, enlace interno)."""
    p = OxmlElement("w:p")
    ppr = OxmlElement("w:pPr")
    pstyle = OxmlElement("w:pStyle")
    pstyle.set(qn("w:val"), TOC_STYLES[level])
    ppr.append(pstyle)
    p.append(ppr)

    # hiperenlace interno a bookmark #_Toc0001
    hl = OxmlElement("w:hyperlink")
    hl.set(qn("w:anchor"), "_Toc0001")

    r = OxmlElement("w:r")
    rpr = OxmlElement("w:rPr")
    rstyle = OxmlElement("w:rStyle")
    rstyle.set(qn("w:val"), "Hyperlink")
    rpr.append(rstyle)
    r.append(rpr)
    t = OxmlElement("w:t")
    t.text = text
    r.append(t)
    hl.append(r)

    p.append(hl)

    # numeros de pagina con tabulacion
    rp = OxmlElement("w:r")
    tp = OxmlElement("w:t")
    tp.text = "\t" + str(page)
    rp.append(tp)
    p.append(rp)
    return p


def build_sample_with_toc() -> bytes:
    doc = Document()

    doc.add_heading("Indice", level=1)

    # Campo fldSimple TOC con entradas cacheadas.
    fld = OxmlElement("w:fldSimple")
    fld.set(qn("w:instr"), ' TOC \\o "1-3" \\h \\z \\u ')
    fld.append(_make_toc_entry("Introduccion", 1, 1))
    fld.append(_make_toc_entry("Marco teorico", 1, 2))
    fld.append(_make_toc_entry("Metodologia", 2, 5))

    # Insertar campo: coger el primer elemento del cuerpo e insertar antes.
    body_el = doc.element.body
    body_el.insert(2, fld)

    # Contenido.
    doc.add_heading("Introduccion", level=1)
    doc.add_paragraph(
        "Texto de ejemplo con varias paginas de contenido para comprobar la "
        "paginacion y la visibilidad de multiples hojas en el editor."
    )
    doc.add_heading("Marco teorico", level=1)
    for _ in range(12):
        doc.add_paragraph(
            "La investigacion academica exige rigor metodologico, revision de "
            "literatura y una correcta citacion de las fuentes utilizadas en el "
            "desarrollo del proyecto (Garcia, 2020)."
        )
    doc.add_heading("Metodologia", level=2)
    doc.add_paragraph("Parrafo metodologico de la investigacion.")

    import io

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


if __name__ == "__main__":
    Path(__file__).with_name("sample_toc.docx").write_bytes(build_sample_with_toc())
    print("ok")