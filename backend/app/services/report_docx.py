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


# Color de los titulos (el mismo azul del informe de comentarios del asesor)
TITULO_COLOR = RGBColor(0x1B, 0x36, 0x5D)


def _etiqueta(doc: Document, texto: str, sangria: float = 0.32) -> object:
    """Parrafo de vineta con la etiqueta en negrita y el texto detras."""
    p = doc.add_paragraph(style="List Bullet")
    p.paragraph_format.space_after = Pt(2)
    p.paragraph_format.left_indent = Inches(sangria)
    p.paragraph_format.first_line_indent = Inches(-0.16)
    lab = p.add_run(texto)
    lab.bold = True
    lab.font.size = Pt(10.5)
    return p


def _observacion(doc: Document, f: dict) -> None:
    """Una observacion con las tres lineas del informe de comentarios:
    que se observo, donde esta y que hay que hacer."""
    sev = str(f.get("severity", "info"))
    rule_id = str(f.get("rule_id", ""))
    location = str(f.get("location", "")).strip()
    message = str(f.get("message", "")).strip()
    suggestion = str(f.get("suggestion", "")).strip()
    excerpt = str(f.get("excerpt", "")).strip()
    name = RULE_NAMES.get(rule_id, "")

    # --- Observacion
    p = _etiqueta(doc, "Observación")
    sev_run = p.add_run(" (" + SEVERITY_LABEL.get(sev, sev) + ")")
    sev_run.bold = True
    sev_run.font.size = Pt(9.5)
    sev_run.font.color.rgb = SEVERITY_COLOR.get(sev, RGBColor(0x55, 0x55, 0x55))
    p.add_run(": ")
    if name:
        n_run = p.add_run(name + ". ")
        n_run.bold = True
        n_run.font.size = Pt(10.5)
    m_run = p.add_run(message)
    m_run.font.size = Pt(10.5)
    if excerpt:
        e_run = p.add_run(' "' + excerpt[:220] + '"')
        e_run.italic = True
        e_run.font.size = Pt(9.5)
        e_run.font.color.rgb = RGBColor(0x80, 0x80, 0x80)

    # --- Ubicacion
    u = _etiqueta(doc, "Ubicación en el Documento: ")
    donde = location or "Sin ubicación precisa"
    u_run = u.add_run(donde)
    u_run.font.size = Pt(10.5)
    if rule_id:
        r = u.add_run("  (" + rule_id + ")")
        r.font.size = Pt(8.5)
        r.font.color.rgb = RGBColor(0x99, 0x99, 0x99)

    # --- Accion de correccion
    a = _etiqueta(doc, "Acción de Corrección Indicada: ")
    if suggestion:
        s_run = a.add_run(suggestion)
        s_run.font.size = Pt(10.5)
    else:
        s_run = a.add_run("Revisar este punto manualmente: no se puede corregir de forma automática.")
        s_run.font.size = Pt(10.5)
        s_run.italic = True
        s_run.font.color.rgb = RGBColor(0x56, 0x65, 0x73)


def _seccion_heading(doc: Document, titulo: str, cuenta: dict) -> None:
    """Encabezado de la seccion del documento, con el resumen de avisos."""
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(12)
    p.paragraph_format.space_after = Pt(4)
    p.paragraph_format.keep_with_next = True
    run = p.add_run(titulo)
    run.bold = True
    run.font.size = Pt(10.5)
    run.font.color.rgb = TITULO_COLOR
    partes = []
    if cuenta.get("error"):
        partes.append(f"{cuenta['error']} error{'es' if cuenta['error'] > 1 else ''}")
    if cuenta.get("warning"):
        partes.append(f"{cuenta['warning']} aviso{'s' if cuenta['warning'] > 1 else ''}")
    if cuenta.get("info"):
        partes.append(f"{cuenta['info']} observaci{'ones' if cuenta['info'] > 1 else 'on'}")
    if partes:
        det = p.add_run("  (" + ", ".join(partes) + ")")
        det.font.size = Pt(9)
        det.font.color.rgb = RGBColor(0x80, 0x80, 0x80)


def build_report_docx(report: dict) -> bytes:
    """Construye el informe APA en formato .docx a partir del payload del informe.

    Recibe el mismo diccionario que produce `report.build_report()` y devuelve
    los bytes del archivo .docx.
    """
    doc = Document()

    # Configuración base del documento (márgenes más amplios para presentación formal)
    for section in doc.sections:
        section.top_margin = Inches(1.25)
        section.bottom_margin = Inches(1.25)
        section.left_margin = Inches(1.25)
        section.right_margin = Inches(1.25)

    # Estilo "Normal" con fuente Times New Roman, tamaño 12 pt y espaciado adecuado
    normal = doc.styles["Normal"]
    normal.font.name = "Times New Roman"
    normal.font.size = Pt(12)
    normal.paragraph_format.space_after = Pt(6)

    # Encabezado y pie de página: número de página centrado
    section = doc.sections[0]
    # Pie de página con número de página
    footer = section.footer
    # Asegurarse de que exista un párrafo
    if not footer.paragraphs:
        footer.add_paragraph()
    foot_par = footer.paragraphs[0]
    foot_par.alignment = WD_ALIGN_PARAGRAPH.CENTER
    # Campo de numero de pagina. Ojo: w:fldSimple es un elemento del parrafo,
    # no de un run; si se mete dentro de <w:r> Word no lo muestra. Se agrega un
    # run con un valor inicial para que el numero se vea antes de actualizar.
    fld = OxmlElement('w:fldSimple')
    fld.set(qn('w:instr'), 'PAGE')
    run = OxmlElement('w:r')
    txt = OxmlElement('w:t')
    txt.text = '1'
    run.append(txt)
    fld.append(run)
    foot_par._p.append(fld)

    summary = report.get("summary", {}) or {}
    by_sev = summary.get("by_severity", {}) or {}
    by_cat = summary.get("by_category", {}) or {}
    findings = report.get("findings", []) or []
    filename = report.get("filename", "documento")
    generated_at = report.get("generated_at", "")
    score = summary.get("compliance_score", 0)

    # ------------------ Encabezado ------------------
    _add_logo(doc)

    title = doc.add_paragraph()
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    t_run = title.add_run("INFORME DE COMENTARIOS Y OBSERVACIONES DEL DOCUMENTO")
    t_run.bold = True
    t_run.font.size = Pt(14)
    t_run.font.color.rgb = TITULO_COLOR

    meta = doc.add_paragraph()
    meta.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = meta.add_run("Documento: ")
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

    # ------------------ Comentarios por seccion ------------------
    doc.add_heading("Comentarios y observaciones por sección", level=1)

    if not findings:
        ok = doc.add_paragraph()
        ok_run = ok.add_run(
            "Sin hallazgos. El documento cumple con los criterios verificados."
        )
        ok_run.italic = True
        _footer_note(doc)
        return _save(doc)

    # Los errores primero: es lo primero que hay que corregir.
    priority = {"error": 0, "warning": 1, "info": 2}
    ordered = sorted(
        findings,
        key=lambda f: (
            priority.get(str(f.get("severity", "info")), 3),
            f.get("paragraph_index") if f.get("paragraph_index") is not None else 10**9,
        ),
    )

    # agrupar por seccion del documento
    grupos: dict[str, list[dict]] = {}
    for f in ordered:
        sec = str((f.get("extra") or {}).get("section") or "").strip()
        grupos.setdefault(sec, []).append(f)

    # los avisos que no son de un parrafo concreto van primero, bajo su propio
    # encabezado: son de todo el documento (margenes, tipografia, orden...)
    grupos_orden: list[tuple[str, list[dict]]] = []
    generales = grupos.pop("", None)
    if generales:
        grupos_orden.append(("Aspectos generales del documento", generales))
    for sec, lista in grupos.items():
        grupos_orden.append((sec, lista))

    # las secciones se ordenan como aparecen en el documento, no alfabeticamente:
    # el asesor recorre la tesis de principio a fin
    def _posicion(lista: list[dict]) -> int:
        return min(
            (f.get("paragraph_index") for f in lista if f.get("paragraph_index") is not None),
            default=10**9,
        )

    grupos_orden.sort(key=lambda par: _posicion(par[1]))

    for sec, lista in grupos_orden:
        # dentro de la seccion, primero los errores y luego el orden del texto
        lista = sorted(
            lista,
            key=lambda f: (
                priority.get(str(f.get("severity", "info")), 3),
                f.get("paragraph_index") if f.get("paragraph_index") is not None else 10**9,
            ),
        )
        cuenta = {"error": 0, "warning": 0, "info": 0}
        for f in lista:
            cuenta[str(f.get("severity", "info"))] = cuenta.get(str(f.get("severity", "info")), 0) + 1
        _seccion_heading(doc, sec, cuenta)
        for f in lista:
            _observacion(doc, f)

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
