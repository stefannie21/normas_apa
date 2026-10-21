"""Reglas de verificacion de tablas (APA 7, seccion Tablas).

Se apoyan en TableInfo, que el parser extrae del XML de cada <w:tbl>.
"""
from __future__ import annotations

from backend.app.rules.base import Category, Finding, Rule, Severity
from backend.app.services.docx_parser import ParsedDocument


class TableCaptionRule(Rule):
    """Toda tabla debe llevar un rotulo 'Tabla N' y un titulo."""

    def __init__(self) -> None:
        super().__init__(
            id="TABLE-001",
            name="Rotulo y titulo de tabla",
            category=Category.TABLAS,
            description=(
                "Cada tabla debe tener, en la linea anterior, un rotulo en negrita "
                "'Tabla N' y un titulo descriptivo en cursiva."
            ),
            default_severity=Severity.WARNING,
        )

    def check(self, document: ParsedDocument) -> list[Finding]:
        findings: list[Finding] = []
        for t in document.tables:
            if not t.has_caption_number:
                findings.append(
                    self.finding(
                        f"Tabla {t.index}: falta el rotulo 'Tabla {t.index}' en la linea anterior.",
                        paragraph_index=t.caption_paragraph_index,
                        location=f"Tabla {t.index}",
                        excerpt=t.caption_text[:120],
                        suggestion=f"Agregar el rotulo 'Tabla {t.index}' en negrita sobre la tabla.",
                    )
                )
            elif not t.title_italic:
                findings.append(
                    self.finding(
                        f"Tabla {t.index}: el titulo de la tabla debe ir en cursiva.",
                        paragraph_index=t.caption_paragraph_index,
                        location=f"Tabla {t.index}",
                        excerpt=t.caption_text[:120],
                        suggestion="Poner el titulo de la tabla en cursiva.",
                    )
                )
        return findings


class TableHeaderRule(Rule):
    """La primera fila de la tabla debe ser encabezado (en negrita)."""

    def __init__(self) -> None:
        super().__init__(
            id="TABLE-002",
            name="Encabezado de columnas",
            category=Category.TABLAS,
            description="Toda tabla debe tener encabezados de columna en negrita en la primera fila.",
            default_severity=Severity.WARNING,
        )

    def check(self, document: ParsedDocument) -> list[Finding]:
        findings: list[Finding] = []
        for t in document.tables:
            if t.rows > 0 and not t.has_header_row:
                findings.append(
                    self.finding(
                        f"Tabla {t.index}: la primera fila debe ser el encabezado (en negrita).",
                        paragraph_index=t.caption_paragraph_index,
                        location=f"Tabla {t.index}",
                        suggestion="Poner en negrita los encabezados de columna de la primera fila.",
                    )
                )
        return findings


class TableBordersRule(Rule):
    """Solo bordes horizontales; prohibidos los verticales."""

    def __init__(self) -> None:
        super().__init__(
            id="TABLE-003",
            name="Bordes de tabla",
            category=Category.TABLAS,
            description=(
                "Las tablas solo llevan bordes horizontales (superior, inferior, "
                "debajo del encabezado). Prohibidos los bordes verticales y las "
                "cuadriculas por celda."
            ),
            default_severity=Severity.WARNING,
        )

    def check(self, document: ParsedDocument) -> list[Finding]:
        findings: list[Finding] = []
        for t in document.tables:
            if t.has_vertical_borders:
                findings.append(
                    self.finding(
                        f"Tabla {t.index}: tiene bordes verticales; APA solo permite bordes horizontales.",
                        paragraph_index=t.caption_paragraph_index,
                        location=f"Tabla {t.index}",
                        suggestion="Quitar los bordes verticales y las cuadriculas de celda.",
                    )
                )
        return findings


class TableMentionRule(Rule):
    """La tabla debe mencionarse en el texto por su numero."""

    def __init__(self) -> None:
        super().__init__(
            id="TABLE-004",
            name="Mencion de la tabla en el texto",
            category=Category.TABLAS,
            description=(
                "Toda tabla debe mencionarse en el cuerpo del texto por su numero "
                "('Tabla 1'), nunca por su posicion en la pagina."
            ),
            default_severity=Severity.WARNING,
        )

    def check(self, document: ParsedDocument) -> list[Finding]:
        findings: list[Finding] = []
        for t in document.tables:
            if not t.mentioned_in_text:
                findings.append(
                    self.finding(
                        f"Tabla {t.index}: no se menciona en el texto por su numero.",
                        paragraph_index=t.caption_paragraph_index,
                        location=f"Tabla {t.index}",
                        suggestion=f"Mencionar la tabla en el texto como 'Tabla {t.index}'.",
                    )
                )
        return findings


class TableFontRule(Rule):
    """Fuente de las celdas consistente con el cuerpo."""

    def __init__(self) -> None:
        super().__init__(
            id="TABLE-005",
            name="Fuente de las celdas",
            category=Category.TABLAS,
            description=(
                "El texto de las celdas debe usar el mismo tipo y tamano de fuente "
                "que el cuerpo del documento."
            ),
            default_severity=Severity.INFO,
        )

    def check(self, document: ParsedDocument) -> list[Finding]:
        findings: list[Finding] = []
        for t in document.tables:
            if t.rows == 0:
                continue
            if not t.cell_font_consistent:
                detail = ""
                if t.cell_font_name and document.default_font and t.cell_font_name != document.default_font:
                    detail = f" (fuente {t.cell_font_name} vs {document.default_font})"
                elif t.cell_font_size_pt and document.default_font_size_pt and t.cell_font_size_pt != document.default_font_size_pt:
                    detail = f" (tamano {t.cell_font_size_pt} pt vs {document.default_font_size_pt} pt)"
                findings.append(
                    self.finding(
                        f"Tabla {t.index}: la fuente de las celdas no coincide con el cuerpo{detail}.",
                        paragraph_index=t.caption_paragraph_index,
                        location=f"Tabla {t.index}",
                        suggestion="Usar en las celdas el mismo tipo y tamano de fuente que el texto principal.",
                    )
                )
        return findings


RULES = [
    TableCaptionRule(),
    TableHeaderRule(),
    TableBordersRule(),
    TableMentionRule(),
    TableFontRule(),
]
