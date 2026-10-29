"""Aplica correcciones de formato directamente sobre el .docx original.

Recibe el bytes del .docx y la lista de reglas corregidas, y modifica el
documento con python-docx para devolver un .docx nuevo con las correcciones
aplicadas de forma permanente.
"""
from __future__ import annotations

import io

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Inches, Pt
from docx.text.paragraph import Paragraph

W_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"

# Reglas que sabemos aplicar de forma permanente en el .docx
RULE_FORMATTERS = {
    "FORMAT-004": "interlineado",
    "FORMAT-007": "espacios",
    "FORMAT-006": "sangria",
    "FORMAT-005": "alineacion",
    "FORMAT-001": "margenes",
    "FORMAT-002": "fuente",
    "FORMAT-003": "tamano",
    "CIT-003": "et_al",
    "CIT-002": "ampersand",
    "REF-002": "sangria_francesa",
    "HEAD-002": "titulos_formato",
}


def _iter_body_paragraphs(doc):
    """Parrafos del cuerpo en orden, incluidas las celdas de tablas.

    `doc.paragraphs` solo recorre los parrafos de nivel superior: el texto de
    una tabla (por ejemplo la matriz de consistencia) se saltaba al aplicar
    correcciones, asi que la edicion quedaria sin formato en esas celdas.
    """
    for child in doc.element.body.iterchildren():
        if child.tag == W_NS + "p":
            yield Paragraph(child, doc)
        elif child.tag == W_NS + "tbl":
            for p in child.iter(W_NS + "p"):
                yield Paragraph(p, doc)


def apply_corrections(docx_bytes: bytes, rule_ids: list[str]) -> bytes:
    """Aplica las correcciones al .docx y devuelve los bytes del archivo resultante."""
    doc = Document(io.BytesIO(docx_bytes))

    actions = set()
    for rid in rule_ids:
        action = RULE_FORMATTERS.get(rid)
        if action:
            actions.add(action)

    if not actions:
        return docx_bytes

    # Formato por parrafo (incluye las celdas de tablas, en orden de documento)
    for p in _iter_body_paragraphs(doc):
        _apply_paragraph_rules(p, actions)

    # Margenes por seccion
    if "margenes" in actions:
        for section in doc.sections:
            section.top_margin = Inches(1.0)
            section.bottom_margin = Inches(1.0)
            section.left_margin = Inches(1.0)
            section.right_margin = Inches(1.0)

    # Fuente y tamano por defecto del documento
    if "fuente" in actions or "tamano" in actions:
        _apply_font_defaults(doc, actions)

    # Titulos: negrita y alineacion por nivel
    if "titulos_formato" in actions:
        _apply_heading_format(doc)

    # Guardar y devolver bytes
    out = io.BytesIO()
    doc.save(out)
    out.seek(0)
    return out.read()


def _apply_paragraph_rules(p, actions: set[str]):
    pf = p.paragraph_format

    if "interlineado" in actions:
        pf.line_spacing = 2.0

    if "espacios" in actions:
        pf.space_before = Pt(0)
        pf.space_after = Pt(0)

    if "sangria" in actions:
        # Sangria de primera linea: 0.5 in (1.27 cm)
        # Solo en parrafos de cuerpo, no en encabezados ni referencias
        if not p.style or "Heading" not in (p.style.name or ""):
            if not _is_reference_paragraph(p):
                pf.first_line_indent = Inches(0.5)

    if "alineacion" in actions:
        if p.alignment == WD_ALIGN_PARAGRAPH.JUSTIFY:
            p.alignment = WD_ALIGN_PARAGRAPH.LEFT

    if "sangria_francesa" in actions:
        if _is_reference_paragraph(p):
            pf.left_indent = Inches(0.5)
            pf.first_line_indent = Inches(-0.5)

    if "et_al" in actions:
        for run in p.runs:
            if run.text:
                import re
                run.text = re.sub(r'\bet\s?al\b(?!\.)', 'et al.', run.text, flags=re.IGNORECASE)

    if "ampersand" in actions:
        for run in p.runs:
            if run.text:
                import re
                # Dentro de parentesis: "and"/"y" -> "&"
                run.text = re.sub(
                    r'\(([^()]*?)\s+\b(?:and|y)\s+([^()]*?)\)',
                    r'(\1 & \2)',
                    run.text
                )


def _is_reference_paragraph(p) -> bool:
    """Detecta si un parrafo pertenece a la lista de referencias."""
    text = (p.text or "").strip().lower()
    if text.startswith("referencias") or text.startswith("references"):
        return False  # es el titulo, no una referencia
    # Heuristica: tiene un autor y un ano entre parentesis
    import re
    if re.search(r'\(\d{4}\)', p.text or ""):
        return True
    if re.search(r'https?://', p.text or ""):
        return True
    return False


def _apply_font_defaults(doc, actions: set[str]):
    """Aplica fuente y tamano consistente en todo el documento."""
    font_name = None
    font_size = None

    if "fuente" in actions:
        font_name = "Times New Roman"
    if "tamano" in actions:
        font_size = Pt(12)

    for p in _iter_body_paragraphs(doc):
        for run in p.runs:
            if font_name and not _is_heading(p):
                if not run.font.name or run.font.name not in {
                    "Times New Roman", "Calibri", "Arial", "Georgia",
                    "Lucida Sans Unicode", "Computer Modern",
                }:
                    run.font.name = font_name
            if font_size and not _is_heading(p):
                # `run.font.size` puede ser None (heredado del estilo): en ese
                # caso hay que asignarlo igual, si no el tamano nunca cambia.
                if run.font.size is None or run.font.size.pt not in {10.0, 11.0, 12.0}:
                    run.font.size = font_size

    # El estilo Normal hereda a los parrafos sin formato explicito: sin esto
    # un documento con fuente/tamano "heredados" no se corrige del todo.
    if font_name or font_size:
        normal = doc.styles["Normal"]
        if font_name:
            normal.font.name = font_name
        if font_size:
            normal.font.size = font_size


def _is_heading(p) -> bool:
    if not p.style:
        return False
    name = (p.style.name or "").lower()
    return "heading" in name or "titulo" in name or "title" in name


def _apply_heading_format(doc):
    """Aplica formato APA a los encabezados: nivel 1 centrado+negrita, etc."""
    for p in _iter_body_paragraphs(doc):
        if not p.style:
            continue
        name = (p.style.name or "").lower()
        if "heading 1" in name or "titulo 1" in name:
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            for run in p.runs:
                run.bold = True
                run.italic = False
        elif "heading 2" in name or "titulo 2" in name:
            p.alignment = WD_ALIGN_PARAGRAPH.LEFT
            for run in p.runs:
                run.bold = True
                run.italic = False
        elif "heading 3" in name or "titulo 3" in name:
            p.alignment = WD_ALIGN_PARAGRAPH.LEFT
            for run in p.runs:
                run.bold = True
                run.italic = True
