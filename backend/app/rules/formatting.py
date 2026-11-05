from __future__ import annotations

import re

from backend.app.rules.base import Category, Finding, Rule, Severity
from backend.app.services.docx_parser import ParsedDocument

# APA 7: 1 in (2.54 cm) en los cuatro margenes.
# https://apastyle.apa.org/style-grammar-guidelines/paper-format/margins
MARGIN_IN = 1.0
MARGIN_TOLERANCE_IN = 0.05  # Tolerancia técnica estricta: 0.95 a 1.05 in (±1.27 mm por redondeo twips)

# La pagina oficial de tipografia NO impone una lista cerrada: "A variety of
# fonts are permitted in APA Style papers, including the default font of your
# word-processing program". Estas son las fuentes RECOMENDADAS (incluye Aptos,
# que falto en la version anterior del motor). No se usan para generar errores.
RECOMMENDED_FONTS = {
    "aptos",                    # 12 pt, sans serif (pagina oficial)
    "times new roman",          # 12 pt, serif
    "calibri",                  # 11 pt
    "arial",                    # 11 pt
    "georgia",                  # 11 pt
    "lucida sans unicode",      # 10 pt
    "computer modern",          # 10 pt (LaTeX)
}
# Compatibilidad con el nombre anterior del modulo (no se usa para validar).
ACCEPTED_FONTS = set(RECOMMENDED_FONTS)

# Excepcion oficial: las fuentes monoespaciadas se reservan para CODIGO; las
# sans serif de 8-14 pt para el interior de imagenes de figuras; los pies de
# pagina conservan el ajuste por defecto del procesador.
MONOSPACE_FONTS = {
    "courier new", "lucida console", "consolas", "monaco", "menlo",
    "source code pro", "courier", "monospace",
}
SYMBOL_FONTS = {"wingdings", "webdings", "symbol", "zapf dingbats"}

ACCEPTED_SIZES = {10.0, 11.0, 12.0}

INDENT_IN = 0.5
INDENT_TOLERANCE_IN = 0.1

LINE_SPACING_TARGET = 2.0
LINE_SPACING_TOLERANCE = 0.15

FONT_URL = "https://apastyle.apa.org/style-grammar-guidelines/paper-format/font"
MARGINS_URL = "https://apastyle.apa.org/style-grammar-guidelines/paper-format/margins"


def _approx(value, target, tol) -> bool:
    return value is not None and abs(value - target) <= tol


def _is_landscape(section) -> bool:
    """Seccion apaisada: excepcion oficial para tablas anchas."""
    w, h = section.page_width_in, section.page_height_in
    return w is not None and h is not None and w > h


def _is_binding_margin(section) -> bool:
    """Margen izquierdo ampliado para encuadernacion de tesis/doctorado.

    Fuente oficial: 'if you are writing a dissertation or thesis, your advisor
    or institution may specify different margins (e.g., a 1.5-inch left margin
    to accommodate binding)'. No es un incumplimiento.
    """
    left = section.left_margin_in
    if left is None or not (1.4 <= left <= 1.8):
        return False
    others = (
        section.top_margin_in,
        section.bottom_margin_in,
        section.right_margin_in,
    )
    return all(v is None or _approx(v, MARGIN_IN, MARGIN_TOLERANCE_IN) for v in others)


def _excluded(document: ParsedDocument, p) -> bool:
    """Zonas con excepcion de formato: portada y bloques de imagen."""
    if getattr(p, "has_image", False):
        return True
    try:
        return bool(document.is_cover_paragraph(p))
    except Exception:
        return False


class MarginRule(Rule):
    def __init__(self) -> None:
        super().__init__(
            id="FORMAT-001",
            name="Márgenes de 2.54 cm (1 in)",
            category=Category.FORMATO,
            description="Todos los márgenes de la página deben ser de 1 pulgada (2.54 cm).",
            default_severity=Severity.ERROR,
            norm_source=MARGINS_URL,
            exceptions=(
                "Tesis/doctorado con margen izquierdo de 1.5 in para encuadernación "
                "(la propia página oficial lo contempla); secciones apaisadas "
                "para tablas anchas."
            ),
        )

    def check(self, document: ParsedDocument) -> list[Finding]:
        findings: list[Finding] = []
        for section in document.sections:
            # Excepciones documentadas: no se genera observacion.
            if _is_landscape(section) or _is_binding_margin(section):
                continue
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
                        suggestion=(
                            "Configurar 2.54 cm (1 in) en los cuatro márgenes. Si la "
                            "institución exige 1.5 in a la izquierda para encuadernar "
                            "una tesis, esa excepción es válida en APA 7."
                        ),
                        extra={
                            "evidence_kind": "document_property",
                            "property": f"márgenes de la sección {section.index + 1}: {', '.join(wrong)}",
                            "section_index": section.index,
                            "margins": {
                                "top": section.top_margin_in,
                                "bottom": section.bottom_margin_in,
                                "left": section.left_margin_in,
                                "right": section.right_margin_in,
                            },
                        },
                    )
                )
        return findings


class FontFamilyRule(Rule):
    """Consistencia de tipografia, NO lista cerrada de fuentes permitidas.

    La version anterior marcaba como error cualquier fuente que no estuviera en
    una lista de seis nombres. La pagina oficial permite 'a variety of fonts
    ... including the default font of your word-processing program', de modo
    que aquello generaba falsos positivos. Lo que SI exige la norma es usar la
    misma fuente en todo el trabajo, con excepciones explicitas para codigo,
    figuras y notas al pie.
    """

    def __init__(self) -> None:
        super().__init__(
            id="FORMAT-002",
            name="Consistencia de tipografía",
            category=Category.FORMATO,
            description=(
                "APA 7 permite una variedad de fuentes legibles, pero exige usar "
                "la misma en todo el documento; las monoespaciadas se reservan "
                "para código informático."
            ),
            norm_source=FONT_URL,
            exceptions=(
                "Monoespaciada (Courier New, Lucida Console...) solo para código; "
                "sans serif 8-14 pt dentro de imágenes de figuras; notas al pie "
                "con la fuente por defecto del procesador."
            ),
        )

    def check(self, document: ParsedDocument) -> list[Finding]:
        default = (document.default_font or "").strip().lower()
        findings: list[Finding] = []

        # Un estilo Normal monoespaciado/simbolico convierte TODO el cuerpo en
        # una excepcion de 'codigo': es un incumplimiento demostrable.
        if default and (default in MONOSPACE_FONTS or default in SYMBOL_FONTS):
            findings.append(
                self.finding(
                    f"La fuente del documento es '{document.default_font}'. APA 7 "
                    "reserva las tipografías monoespaciadas y de símbolos para "
                    "código informático, no para el cuerpo del trabajo.",
                    location="Documento (estilo Normal)",
                    suggestion=(
                        "Usar una fuente legible y uniforme en todo el documento: "
                        "12 pt Times New Roman o Aptos, 11 pt Calibri, Arial o "
                        "Georgia, 10 pt Lucida Sans Unicode o Computer Modern."
                    ),
                    extra={
                        "evidence_kind": "document_property",
                        "property": f"estilo Normal = {document.default_font}",
                        "font": document.default_font,
                    },
                )
            )

        # Mezcla de fuentes en el cuerpo (excluidas zonas con excepcion).
        fonts: dict[str, object] = {}
        for p in document.body_paragraphs:
            if p.in_table or _excluded(document, p):
                continue
            for name in p.fonts:
                key = (name or "").strip().lower()
                if not key or key in MONOSPACE_FONTS or key in SYMBOL_FONTS:
                    continue  # codigo / simbolos: excepcion oficial
                fonts.setdefault(key, p)
        if len(fonts) > 1:
            names = ", ".join(sorted(fonts))
            first = next(iter(fonts.values()))
            findings.append(
                self.finding(
                    f"El documento mezcla tipografías en el cuerpo: {names}. "
                    "APA 7 exige usar la misma fuente en todo el trabajo.",
                    paragraph_index=first.index,
                    location=f"Párrafo {first.index + 1}",
                    excerpt=first.excerpt(120),
                    suggestion=(
                        "Unificar la fuente en todo el documento. APA 7 admite "
                        "cualquier fuente legible, incluida la predeterminada del "
                        "procesador; se recomiendan 12 pt Times New Roman/Aptos, "
                        "11 pt Calibri/Arial/Georgia o 10 pt Lucida Sans Unicode."
                    ),
                    extra={
                        "evidence_kind": "document_property",
                        "property": f"fuentes del cuerpo: {names}",
                        "fonts": sorted(fonts),
                    },
                )
            )
        return findings


class FontSizeRule(Rule):
    def __init__(self) -> None:
        super().__init__(
            id="FORMAT-003",
            name="Tamaño de fuente consistente",
            category=Category.FORMATO,
            description="El cuerpo del texto debe usar un tamaño de fuente APA consistente.",
            norm_source=FONT_URL,
            exceptions=(
                "8-14 pt dentro de imágenes de figuras; portada; notas al pie; "
                "código; celdas de tabla (pueden tener otro interlineado)."
            ),
        )

    def check(self, document: ParsedDocument) -> list[Finding]:
        findings: list[Finding] = []
        out_of_range: set[float] = set()
        first_bad: object | None = None
        for p in document.body_paragraphs:
            if p.heading_level or p.in_table or _excluded(document, p):
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
                    suggestion="Usar 12 pt (o 11/10 pt según la fuente) de forma consistente.",
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
            norm_source="https://apastyle.apa.org/style-grammar-guidelines/paper-format/headings",
            exceptions=(
                "Portada/carátula; cuerpo de tablas (puede ser simple, 1.5 o doble); "
                "interior de imágenes de figuras; pies de página. Los encabezados "
                "y las citas en bloque SI deben ir a doble espacio."
            ),
        )

    def check(self, document: ParsedDocument) -> list[Finding]:
        # un unico hallazgo por valor de interlineado detectado: reportar por
        # parrafo duplicaba el mismo problema cientos de veces en una tesis
        by_value: dict[float, object] = {}
        for p in document.body_paragraphs:
            if p.in_table or _excluded(document, p):
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
            exceptions="Portada, títulos centrados, tablas, rotulos de figuras, citas en bloque y perfil institucional justificado.",
        )

    def check(self, document: ParsedDocument) -> list[Finding]:
        # Excepción institucional: si la institución solicita expresamente texto justificado
        if getattr(document, "allow_justified", False) or getattr(document, "institutional_profile", {}).get("allow_justified", False):
            return []
        findings: list[Finding] = []
        for p in document.body_paragraphs:
            if p.heading_level or p.in_table or _excluded(document, p):
                continue
            if p.alignment in {"justify"}:
                findings.append(
                    self.finding(
                        "Párrafo justificado; APA recomienda alinear a la izquierda.",
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
            exceptions=(
                "Portada, resumen/abstract (sin sangría en APA 7 sec. 2.9), encabezados, listas, "
                "citas en bloque (sangría izquierda completa de 0.5 in), "
                "tablas, figuras, referencias (sangría francesa) y apéndices."
            ),
        )

    def check(self, document: ParsedDocument) -> list[Finding]:
        findings: list[Finding] = []
        ref_start = document.references_start
        for p in document.body_paragraphs:
            if p.heading_level or p.is_list_item or p.in_table or _excluded(document, p):
                continue
            if ref_start is not None and p.index > ref_start:
                continue
            # Excepción normativa APA 7 sec. 2.9: el resumen / abstract va sin sangría de primera línea
            sec_title = getattr(p, "section_title", "") or ""
            if sec_title.strip().lower() in {"resumen", "abstract"} or getattr(p, "is_abstract", False):
                continue
            # Excepción normativa APA 7 sec. 8.27: citas en bloque (sangría izquierda completa)
            if getattr(p, "is_block_quote", False) or (p.left_indent_in and p.left_indent_in >= 0.4):
                continue
            if len(p.text.strip()) < 80:
                continue

            raw_text = p.text
            has_manual_tab = raw_text.startswith("\t") or bool(re.match(r"^\s{4,}", raw_text))
            indent = p.first_line_indent_in

            if has_manual_tab and (indent is None or indent < 0.2):
                findings.append(
                    self.finding(
                        "Se detectó sangría manual con tabulador o espacios en lugar de sangría de párrafo Word.",
                        paragraph_index=p.index,
                        location=f"Párrafo {p.index + 1}",
                        excerpt=p.excerpt(),
                        suggestion="Configurar la sangría de primera línea a 1.27 cm en el estilo de párrafo y retirar tabuladores manuales.",
                        extra={"manual_indent": True},
                    )
                )
                continue

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
            norm_source="https://apastyle.apa.org/style-grammar-guidelines/paper-format/headings",
            exceptions=(
                "Portada/carátula; separación entre una figura o tabla y el texto; "
                "ajustes de maquetación de apéndices."
            ),
        )

    def check(self, document: ParsedDocument) -> list[Finding]:
        # igual que FORMAT-004: un hallazgo por configuracion, no por parrafo
        before_found: float | None = None
        after_found: float | None = None
        first: object | None = None
        total = 0
        for p in document.body_paragraphs:
            if p.in_table or _excluded(document, p):
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
