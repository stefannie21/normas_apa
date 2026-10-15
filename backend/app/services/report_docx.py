"""Genera el informe APA como un documento .docx descargable.

A diferencia de `report.py` (que produce HTML para ver en pantalla), este modulo
construye un Word con: portada-resumen, tarjetas de cumplimiento, desglose por
gravedad y categoria, y la tabla completa de hallazgos con su ubicacion y
sugerencia de correccion.
"""
from __future__ import annotations

import io
from datetime import datetime

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
from docx.shared import Inches, Pt, RGBColor

SEVERITY_LABEL = {
    "error": "Error",
    "warning": "Advertencia",
    "info": "Observación",
}

SEVERITY_COLOR = {
    "error": RGBColor(0xC0, 0x39, 0x2B),  # rojo
    "warning": RGBColor(0xD6, 0x89, 0x10),  # ámbar
    "info": RGBColor(0x24, 0x71, 0xA3),  # azul
}

SEVERITY_FILL = {
    "error": "F9D7D3",
    "warning": "FCEBD4",
    "info": "D9E8F5",
}


def _shade(cell, hex_fill: str) -> None:
    """Aplica color de fondo a una celda de tabla."""
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), hex_fill)
    tc_pr.append(shd)


def _set_repeat_header(row) -> None:
    """Marca una fila como encabezado que se repite en cada pagina."""
    tr_pr = row._tr.get_or_add_trPr()
    tbl_header = OxmlElement("w:tblHeader")
    tbl_header.set(qn("w:val"), "true")
    tr_pr.append(tbl_header)


def _friendly_date(iso: str) -> str:
    try:
        dt = datetime.fromisoformat(iso)
        return dt.strftime("%d/%m/%Y a las %H:%M")
    except (ValueError, TypeError):
        return iso


def build_report_docx(report: dict) -> bytes:
    """Construye el informe APA en formato .docx a partir del payload del informe.

    Recibe el mismo diccionario que produce `report.build_report()` y devuelve
    los bytes del archivo .docx.
    """
    doc = Document()

    # Configuracion base del documento
    for section in doc.sections:
        section.top_margin = Inches(1)
        section.bottom_margin = Inches(1)
        section.left_margin = Inches(1)
        section.right_margin = Inches(1)

    normal = doc.styles["Normal"]
    normal.font.name = "Calibri"
    normal.font.size = Pt(11)
    normal.paragraph_format.space_after = Pt(6)

    summary = report.get("summary", {}) or {}
    by_sev = summary.get("by_severity", {}) or {}
    by_cat = summary.get("by_category", {}) or {}
    findings = report.get("findings", []) or []
    filename = report.get("filename", "documento")
    generated_at = report.get("generated_at", "")
    score = summary.get("compliance_score", 0)

    # ------------------ Encabezado ------------------
    title = doc.add_heading("Informe de cumplimiento de normas APA", level=0)
    title.alignment = WD_ALIGN_PARAGRAPH.LEFT

    meta = doc.add_paragraph()
    run = meta.add_run("Documento evaluado: ")
    run.bold = True
    meta.add_run(str(filename))
    meta.add_run("\n")
    run2 = meta.add_run("Generado: ")
    run2.bold = True
    meta.add_run(_friendly_date(generated_at))
    meta.add_run("\n")
    run3 = meta.add_run("Normativa de referencia: ")
    run3.bold = True
    meta.add_run("APA 7.ª edición")

    doc.add_paragraph()

    # ------------------ Tarjetas resumen ------------------
    doc.add_heading("Resumen", level=1)
    score_p = doc.add_paragraph()
    score_run = score_p.add_run(f"{score}%")
    score_run.bold = True
    score_run.font.size = Pt(28)
    score_run.font.color.rgb = RGBColor(0x1E, 0x84, 0x49)
    score_label = score_p.add_run("  nivel de cumplimiento")
    score_label.font.size = Pt(12)
    score_label.font.color.rgb = RGBColor(0x56, 0x65, 0x73)

    # Tabla resumen de conteos
    resumen_rows = [
        ("Hallazgos totales", str(summary.get("total_findings", len(findings)))),
        ("Errores", str(by_sev.get("error", 0))),
        ("Advertencias", str(by_sev.get("warning", 0))),
        ("Observaciones", str(by_sev.get("info", 0))),
    ]
    tbl = doc.add_table(rows=0, cols=2)
    tbl.style = "Light Grid Accent 1"
    tbl.alignment = WD_TABLE_ALIGNMENT.LEFT
    for label, value in resumen_rows:
        cells = tbl.add_row().cells
        cells[0].text = label
        cells[0].paragraphs[0].runs[0].bold = True
        cells[1].text = value
        cells[1].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER

    doc.add_paragraph()

    # ------------------ Desglose por categoria ------------------
    if by_cat:
        doc.add_heading("Hallazgos por categoría", level=1)
        cat_tbl = doc.add_table(rows=1, cols=2)
        cat_tbl.style = "Light Grid Accent 1"
        hdr = cat_tbl.rows[0].cells
        hdr[0].text = "Categoría"
        hdr[1].text = "Cantidad"
        for cell in hdr:
            cell.paragraphs[0].runs[0].bold = True
        _set_repeat_header(cat_tbl.rows[0])
        for cat, count in sorted(by_cat.items(), key=lambda x: (-x[1], x[0])):
            cells = cat_tbl.add_row().cells
            cells[0].text = str(cat)
            cells[1].text = str(count)
            cells[1].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
        doc.add_paragraph()

    # ------------------ Tabla de hallazgos ------------------
    doc.add_heading("Detalle de hallazgos", level=1)

    if not findings:
        ok = doc.add_paragraph()
        ok_run = ok.add_run(
            "Sin hallazgos. El documento cumple con los criterios verificados."
        )
        ok_run.italic = True
        _footer_note(doc)
        return _save(doc)

    detail_tbl = doc.add_table(rows=1, cols=5)
    detail_tbl.style = "Table Grid"
    detail_tbl.autofit = True
    headers = ["Gravedad", "Categoría", "Regla", "Ubicación", "Detalle"]
    widths = [Inches(1.1), Inches(1.4), Inches(0.9), Inches(1.5), Inches(3.1)]
    for i, text in enumerate(headers):
        cell = detail_tbl.rows[0].cells[i]
        cell.text = ""
        para = cell.paragraphs[0]
        run = para.add_run(text)
        run.bold = True
        run.font.size = Pt(10)
        _shade(cell, "D9D9D9")
    _set_repeat_header(detail_tbl.rows[0])

    for f in findings:
        sev = str(f.get("severity", "info"))
        cells = detail_tbl.add_row().cells

        # Gravedad con color de fondo y texto
        sev_cell = cells[0]
        sev_cell.text = ""
        sev_para = sev_cell.paragraphs[0]
        sev_run = sev_para.add_run(SEVERITY_LABEL.get(sev, sev))
        sev_run.bold = True
        sev_run.font.size = Pt(9)
        sev_run.font.color.rgb = SEVERITY_COLOR.get(sev, RGBColor(0x55, 0x55, 0x55))
        _shade(sev_cell, SEVERITY_FILL.get(sev, "F2F2F2"))

        # Categoria
        cells[1].text = ""
        c1 = cells[1].paragraphs[0].add_run(str(f.get("category", "")))
        c1.font.size = Pt(9)

        # Regla
        cells[2].text = ""
        c2 = cells[2].paragraphs[0].add_run(str(f.get("rule_id", "")))
        c2.font.size = Pt(9)

        # Ubicacion
        cells[3].text = ""
        c3 = cells[3].paragraphs[0].add_run(str(f.get("location", "")))
        c3.font.size = Pt(9)

        # Detalle (mensaje + sugerencia + extracto)
        detail_cell = cells[4]
        detail_cell.text = ""
        d_para = detail_cell.paragraphs[0]
        d_run = d_para.add_run(str(f.get("message", "")))
        d_run.font.size = Pt(9)
        if f.get("suggestion"):
            sug = detail_cell.add_paragraph()
            sug_run = sug.add_run("Sugerencia: " + str(f["suggestion"]))
            sug_run.italic = True
            sug_run.font.size = Pt(8.5)
            sug_run.font.color.rgb = RGBColor(0x56, 0x65, 0x73)
        if f.get("excerpt"):
            exc = detail_cell.add_paragraph()
            exc_run = exc.add_run("«" + str(f["excerpt"])[:180] + "»")
            exc_run.font.size = Pt(8.5)
            exc_run.font.color.rgb = RGBColor(0x80, 0x80, 0x80)

    # Ajustar ancho de columnas
    for row in detail_tbl.rows:
        for i, cell in enumerate(row.cells):
            cell.width = widths[i]

    ai_review = report.get("ai_review")
    if ai_review and ai_review.get("notes"):
        doc.add_paragraph()
        doc.add_heading("Notas de la revisión con IA", level=1)
        for note in ai_review["notes"]:
            doc.add_paragraph(str(note), style="List Bullet")

    _footer_note(doc)
    return _save(doc)


def _footer_note(doc: Document) -> None:
    doc.add_paragraph()
    note = doc.add_paragraph()
    run = note.add_run(
        "Informe automático de apoyo. No sustituye la revisión de un asesor humano."
    )
    run.italic = True
    run.font.size = Pt(9)
    run.font.color.rgb = RGBColor(0x70, 0x70, 0x70)


def _save(doc: Document) -> bytes:
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()
