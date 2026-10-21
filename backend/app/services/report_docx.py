"""Genera el informe APA como un documento .docx descargable.

A diferencia de `report.py` (que produce HTML para ver en pantalla), este modulo
construye un Word con: portada-resumen, tarjetas de cumplimiento, desglose por
gravedad y categoria, y la tabla completa de hallazgos con su ubicacion y
sugerencia de correccion.
"""
from __future__ import annotations

import io
from datetime import datetime
from pathlib import Path

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
from docx.shared import Inches, Pt, RGBColor

from backend.app.rules.registry import get_rules

BASE_DIR = Path(__file__).resolve().parents[3]
LOGO_PATH = BASE_DIR / "frontend" / "img" / "cea-logo-full.png"

# Nombre de cada regla en lenguaje claro (lo que ve el estudiante)
RULE_NAMES: dict[str, str] = {r.id: r.name for r in get_rules()}

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

# Los errores se listan primero: es lo primero que el estudiante debe arreglar
SEVERITY_ORDER = {"error": 0, "warning": 1, "info": 2}


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


def _add_logo(doc: Document) -> None:
    """Logo de GROUP CEA en la cabecera del informe.

    Si el archivo no esta disponible el informe se genera igual, solo sin logo.
    """
    try:
        if not LOGO_PATH.exists():
            return
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = p.add_run()
        run.add_picture(str(LOGO_PATH), width=Inches(1.9))
        p.paragraph_format.space_after = Pt(10)
    except Exception:
        # un logo que no carga no puedetumbar la descarga del informe
        pass


def _finding_bullet(doc: Document, f: dict) -> None:
    """Un hallazgo como vineta: que es, donde esta y que hay que hacer.

    En tres lineas para que se lea de un vistazo:
      1. Gravedad | Categoria | Ubicacion (y el codigo de la regla)
      2. El nombre claro de la regla + el detalle exacto
      3. Que hacer (la correccion propuesta)
    """
    sev = str(f.get("severity", "info"))
    rule_id = str(f.get("rule_id", ""))
    category = str(f.get("category", "")).strip()
    location = str(f.get("location", "")).strip()

    # --- linea 1: gravedad, categoria y ubicacion
    p = doc.add_paragraph(style="List Bullet")
    p.paragraph_format.space_after = Pt(0)
    p.paragraph_format.left_indent = Inches(0.32)
    p.paragraph_format.first_line_indent = Inches(-0.16)

    sev_run = p.add_run(SEVERITY_LABEL.get(sev, sev).upper())
    sev_run.bold = True
    sev_run.font.size = Pt(9)
    sev_run.font.color.rgb = SEVERITY_COLOR.get(sev, RGBColor(0x55, 0x55, 0x55))

    sep = p.add_run("   |   ")
    sep.font.size = Pt(9)
    sep.font.color.rgb = RGBColor(0xA0, 0xA0, 0xA0)

    if category:
        cat_run = p.add_run(category)
        cat_run.font.size = Pt(9)
        cat_run.font.color.rgb = RGBColor(0x56, 0x65, 0x73)
        sep2 = p.add_run("   |   ")
        sep2.font.size = Pt(9)
        sep2.font.color.rgb = RGBColor(0xA0, 0xA0, 0xA0)

    if location:
        loc_run = p.add_run(location)
        loc_run.font.size = Pt(9)
        loc_run.bold = True
    if rule_id:
        rid = p.add_run("  (" + rule_id + ")")
        rid.font.size = Pt(8)
        rid.font.color.rgb = RGBColor(0x99, 0x99, 0x99)

    # --- linea 2: la regla en lenguaje claro + el detalle preciso
    det = doc.add_paragraph()
    det.paragraph_format.left_indent = Inches(0.32)
    det.paragraph_format.space_after = Pt(0)
    name = RULE_NAMES.get(rule_id, "")
    if name:
        n_run = det.add_run(name)
        n_run.bold = True
        n_run.font.size = Pt(9.5)
        det.add_run(" — ")
    msg = str(f.get("message", "")).strip()
    m_run = det.add_run(msg)
    m_run.font.size = Pt(9.5)

    # --- linea 3: que hacer
    suggestion = str(f.get("suggestion", "")).strip()
    if suggestion:
        how = doc.add_paragraph()
        how.paragraph_format.left_indent = Inches(0.32)
        how.paragraph_format.space_after = Pt(0)
        lbl = how.add_run("Qué hacer: ")
        lbl.bold = True
        lbl.font.size = Pt(9)
        lbl.font.color.rgb = RGBColor(0x1E, 0x5C, 0x9E)
        s_run = how.add_run(suggestion)
        s_run.font.size = Pt(9)
        s_run.font.color.rgb = RGBColor(0x1E, 0x5C, 0x9E)

    # --- cita del texto donde esta el problema
    excerpt = str(f.get("excerpt", "")).strip()
    if excerpt:
        q = doc.add_paragraph()
        q.paragraph_format.left_indent = Inches(0.32)
        q.paragraph_format.space_after = Pt(6)
        q_run = q.add_run("“" + excerpt[:180] + "”")
        q_run.italic = True
        q_run.font.size = Pt(8.5)
        q_run.font.color.rgb = RGBColor(0x80, 0x80, 0x80)


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
    _add_logo(doc)

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

    # ------------------ Detalle de hallazgos (en vinetas) ------------------
    doc.add_heading("Detalle de hallazgos", level=1)

    if not findings:
        ok = doc.add_paragraph()
        ok_run = ok.add_run(
            "Sin hallazgos. El documento cumple con los criterios verificados."
        )
        ok_run.italic = True
        _footer_note(doc)
        return _save(doc)

    # leyenda rapida: que significa cada gravedad
    legend = doc.add_paragraph()
    legend.paragraph_format.space_after = Pt(10)
    for key, text in (
        ("error", ": hay que corregirlo antes de entregar.  "),
        ("warning", ": conviene revisarlo.  "),
        ("info", ": es un detalle de estilo."),
    ):
        lab = legend.add_run(SEVERITY_LABEL[key])
        lab.bold = True
        lab.font.size = Pt(9)
        lab.font.color.rgb = SEVERITY_COLOR[key]
        txt = legend.add_run(text)
        txt.font.size = Pt(9)
        txt.font.color.rgb = RGBColor(0x56, 0x65, 0x73)

    # los errores primero: es lo primero que hay que arreglar
    ordered = sorted(
        findings,
        key=lambda f: SEVERITY_ORDER.get(str(f.get("severity", "info")), 3),
    )
    for f in ordered:
        _finding_bullet(doc, f)

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
