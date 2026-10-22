from __future__ import annotations

from backend.app.rules.base import Category, Finding, Rule, Severity
from backend.app.services.docx_parser import ParsedDocument

# APA 7: 2.54 cm (1 in) en todos los margenes.
MARGIN_IN = 1.0
MARGIN_TOLERANCE_IN = 0.1

ACCEPTED_FONTS = {
    "times new roman",
    "calibri",
    "arial",
    "georgia",
    "lucida sans unicode",
    "computer modern",
}

ACCEPTED_SIZES = {10.0, 11.0, 12.0}

INDENT_IN = 0.5
INDENT_TOLERANCE_IN = 0.1

LINE_SPACING_TARGET = 2.0
LINE_SPACING_TOLERANCE = 0.15


def _approx(value, target, tol) -> bool:
    return value is not None and abs(value - target) <= tol


class MarginRule(Rule):
    def __init__(self) -> None:
        super().__init__(
            id="FORMAT-001",
            name="Márgenes de 2.54 cm (1 in)",
            category=Category.FORMATO,
            description="Todos los márgenes de la página deben ser de 1 pulgada (2.54 cm).",
            default_severity=Severity.ERROR,
        )

    def check(self, document: ParsedDocument) -> list[Finding]:
        findings: list[Finding] = []
        for section in document.sections:
            wrong = []
            for label, value in (
                ("superior", section.top_margin_in),
                ("inferior", section.bottom_margin_in),
                ("izquierdo", section.left_margin_in),
                ("derecho", section.right_margin_in),
            ):
                if value is None or not _approx(value, MARGIN_IN, MARGIN_TOLERANCE_IN):
                    shown = f"{value:.2f} in" if value is not None else "no definido"
                    wrong.append(f"{label}={shown}")
            if wrong:
                findings.append(
                    self.finding(
                        f"La sección {section.index + 1} no tiene márgenes APA (1 in). "
                        f"Valores detectados: {', '.join(wrong)}.",
                        location=f"Sección {section.index + 1}",
                        suggestion="Configurar 2.54 cm (1 in) en los cuatro márgenes.",
                    )
                )
        return findings


class FontFamilyRule(Rule):
    def __init__(self) -> None:
        super().__init__(
            id="FORMAT-002",
            name="Tipografía permitida",
            category=Category.FORMATO,
            description="Usar una fuente aceptada por APA (p. ej. Times New Roman 12, Calibri 11, Arial 11).",
        )

    def check(self, document: ParsedDocument) -> list[Finding]:
        seen: dict[str, object] = {}
        for p in document.body_paragraphs:
            for name in p.fonts:
                key = name.strip().lower()
                if key and key not in ACCEPTED_FONTS and key not in seen:
                    seen[key] = p
        return [
            self.finding(
                f"Fuente no recomendada por APA: '{name}'.",
                paragraph_index=p.index,
                location=f"Párrafo {p.index + 1}",
                excerpt=p.excerpt(),
                suggestion="Usar Times New Roman 12, Calibri 11, Arial 11, Georgia 11, Lucida Sans Unicode 10 o Computer Modern 10.",
            )
            for name, p in seen.items()
        ]


class FontSizeRule(Rule):
    def __init__(self) -> None:
        super().__init__(
            id="FORMAT-003",
            name="Tamaño de fuente consistente",
            category=Category.FORMATO,
            description="El cuerpo del texto debe usar un tamaño de fuente APA consistente.",
        )

    def check(self, document: ParsedDocument) -> list[Finding]:
        findings: list[Finding] = []
        out_of_range: set[float] = set()
        first_bad: object | None = None
        for p in document.body_paragraphs:
            if p.heading_level or p.in_table:
                continue
            # Excepcion de portada/carátula: los tamaños 14/16/18 pt (o
            # superiores) se usan para la diagramacion institucional y no se
            # evaluan contra el rango APA del cuerpo (11/12 pt).
            if getattr(p, "estimated_page", 1) == 1:
                continue
            # se ignoran super/subindices y marcas de referencia: no son cuerpo de texto
            sizes = {
                round(r.font_size_pt, 1)
                for r in p.runs
                if r.text.strip() and not r.is_vertical and r.font_size_pt is not None
            }
            if not sizes:
                continue
            bad = sorted(s for s in sizes if s not in ACCEPTED_SIZES)
            if bad:
                out_of_range.update(bad)
                if first_bad is None:
                    first_bad = p
            elif len(sizes) > 1:
                findings.append(
                    self.finding(
                        f"El párrafo mezcla varios tamaños de fuente: {sorted(sizes)} pt.",
                        paragraph_index=p.index,
                        location=f"Párrafo {p.index + 1}",
                        excerpt=p.excerpt(),
                        suggestion="Unificar el tamaño de fuente en todo el párrafo.",
                    )
                )
        if out_of_range and first_bad is not None:
            findings.insert(
                0,
                self.finding(
                    f"Tamaño de fuente fuera de rango APA: {sorted(out_of_range)} pt.",
                    paragraph_index=first_bad.index,
                    location=f"Párrafo {first_bad.index + 1}",
                    excerpt=first_bad.excerpt(),
                    suggestion="Usar 12 pt (o 11 pt según la fuente) de forma consistente.",
                ),
            )
        return findings


class LineSpacingRule(Rule):
    def __init__(self) -> None:
        super().__init__(
            id="FORMAT-004",
            name="Interlineado doble",
            category=Category.FORMATO,
            description="Todo el documento debe tener interlineado doble.",
            default_severity=Severity.ERROR,
        )

    def check(self, document: ParsedDocument) -> list[Finding]:
        # un unico hallazgo por valor de interlineado detectado: reportar por
        # parrafo duplicaba el mismo problema cientos de veces en una tesis
        by_value: dict[float, object] = {}
        for p in document.body_paragraphs:
            if p.in_table:
                continue
            value = p.line_spacing
            if value is None or _approx(value, LINE_SPACING_TARGET, LINE_SPACING_TOLERANCE):
                continue
            key = round(float(value), 2)
            by_value.setdefault(key, p)
        return [
            self.finding(
                f"Interlineado {value} en lugar de doble (2.0) en {self._count(document, value)} párrafo(s).",
                paragraph_index=p.index,
                location=f"Párrafo {p.index + 1}",
                excerpt=p.excerpt(),
                suggestion="Aplicar interlineado doble (2.0) sin espacio adicional antes/después.",
                extra={"line_spacing": value},
            )
            for value, p in sorted(by_value.items())
        ]

    @staticmethod
    def _count(document: ParsedDocument, value: float) -> int:
        return sum(
            1
            for p in document.body_paragraphs
            if p.line_spacing is not None and round(float(p.line_spacing), 2) == value
        )


class AlignmentRule(Rule):
    def __init__(self) -> None:
        super().__init__(
            id="FORMAT-005",
            name="Alineación a la izquierda",
            category=Category.FORMATO,
            description="El texto debe alinearse a la izquierda (no justificado).",
        )

    def check(self, document: ParsedDocument) -> list[Finding]:
        findings: list[Finding] = []
        for p in document.body_paragraphs:
            if p.heading_level or p.in_table:
                continue
            if p.alignment in {"justify"}:
                findings.append(
                    self.finding(
                        f"Párrafo justificado; APA recomienda alinear a la izquierda.",
                        paragraph_index=p.index,
                        location=f"Párrafo {p.index + 1}",
                        excerpt=p.excerpt(),
                        suggestion="Cambiar la alineación a izquierda.",
                    )
                )
        return findings


class FirstLineIndentRule(Rule):
    def __init__(self) -> None:
        super().__init__(
            id="FORMAT-006",
            name="Sangría de primera línea",
            category=Category.FORMATO,
            description="La primera línea de cada párrafo del cuerpo debe tener sangría de 1.27 cm (0.5 in).",
        )

    def check(self, document: ParsedDocument) -> list[Finding]:
        findings: list[Finding] = []
        ref_start = document.references_start
        for p in document.body_paragraphs:
            if p.heading_level or p.is_list_item or p.in_table:
                continue
            if ref_start is not None and p.index > ref_start:
                continue
            if len(p.text.strip()) < 80:
                continue
            indent = p.first_line_indent_in
            if indent is None or abs(indent - INDENT_IN) > INDENT_TOLERANCE_IN:
                shown = f"{indent:.2f} in" if indent is not None else "sin sangría"
                findings.append(
                    self.finding(
                        f"Primera línea con sangría de {shown} en lugar de 0.5 in (1.27 cm).",
                        paragraph_index=p.index,
                        location=f"Párrafo {p.index + 1}",
                        excerpt=p.excerpt(),
                        suggestion="Aplicar sangría de primera línea de 1.27 cm en párrafos del cuerpo.",
                    )
                )
        return findings


class ParagraphSpacingRule(Rule):
    def __init__(self) -> None:
        super().__init__(
            id="FORMAT-007",
            name="Sin espacio extra entre párrafos",
            category=Category.FORMATO,
            description="APA no usa espacio adicional antes o después de los párrafos.",
        )

    def check(self, document: ParsedDocument) -> list[Finding]:
        # igual que FORMAT-004: un hallazgo por configuracion, no por parrafo
        before_found: float | None = None
        after_found: float | None = None
        first: object | None = None
        total = 0
        for p in document.body_paragraphs:
            if p.in_table:
                continue
            before = p.space_before_pt or 0
            after = p.space_after_pt or 0
            if before <= 0.5 and after <= 0.5:
                continue
            total += 1
            if first is None:
                first = p
            if before > 0.5 and before_found is None:
                before_found = before
            if after > 0.5 and after_found is None:
                after_found = after
        if first is None:
            return []
        details = []
        if before_found is not None:
            details.append(f"antes={before_found:.1f} pt")
        if after_found is not None:
            details.append(f"después={after_found:.1f} pt")
        return [
            self.finding(
                f"Espacio extra entre párrafos ({', '.join(details)}) en {total} párrafo(s).",
                paragraph_index=first.index,
                location=f"Párrafo {first.index + 1}",
                excerpt=first.excerpt(),
                suggestion="Definir 0 pt de espacio antes y después del párrafo.",
            )
        ]


RULES = [
    MarginRule(),
    FontFamilyRule(),
    FontSizeRule(),
    LineSpacingRule(),
    AlignmentRule(),
    FirstLineIndentRule(),
    ParagraphSpacingRule(),
]
