from __future__ import annotations

import re

from backend.app.rules.base import Category, Finding, Rule, Severity
from backend.app.services.docx_parser import ParsedDocument, ParagraphInfo

HEADINGS_URL = "https://apastyle.apa.org/style-grammar-guidelines/paper-format/headings"

# APA 7 - formato por nivel de titulo (pagina oficial "Headings").
# Nivel 1: centrado, negrita, titulo en mayuscula de titulo
# Nivel 2: izquierda, negrita
# Nivel 3: izquierda, negrita cursiva
# Nivel 4: sangrado, negrita, termina en punto, EN LINEA con el texto
# Nivel 5: sangrado, negrita cursiva, termina en punto, EN LINEA
HEADING_SPEC = {
    1: {"alignment": "center", "bold": True, "italic": False, "indented": False, "period": False},
    2: {"alignment": "left", "bold": True, "italic": False, "indented": False, "period": False},
    3: {"alignment": "left", "bold": True, "italic": True, "indented": False, "period": False},
    4: {"alignment": "left", "bold": True, "italic": False, "indented": True, "period": True},
    5: {"alignment": "left", "bold": True, "italic": True, "indented": True, "period": True},
}


def _run_style(paragraph: ParagraphInfo) -> tuple[bool, bool]:
    runs = [r for r in paragraph.runs if r.text.strip()]
    if not runs:
        return False, False
    bold = all(r.bold for r in runs)
    italic = all(r.italic for r in runs)
    return bold, italic


def _bold_prefix(paragraph: ParagraphInfo) -> str:
    """Texto en negrita al inicio del parrafo (encabezados en linea 4/5)."""
    out: list[str] = []
    for r in paragraph.runs:
        if r.bold and r.text.strip():
            out.append(r.text)
        elif r.text.strip():
            break
    return "".join(out).strip()


def _inline_period_ok(paragraph: ParagraphInfo) -> bool:
    """Nivel 4/5: el encabezado en linea termina con punto."""
    prefix = _bold_prefix(paragraph)
    if prefix:
        return prefix.rstrip().endswith(".")
    return paragraph.text.strip().endswith(".")


def _indented(paragraph: ParagraphInfo) -> bool:
    return (
        (paragraph.first_line_indent_in or 0) >= 0.4
        or (paragraph.left_indent_in or 0) >= 0.4
    )


class StructureRule(Rule):
    """NO regla: los encabezados son opcionales en APA 7.

    La pagina oficial dice 'short student papers may not require any headings'
    y 'use only the number of headings necessary'. La version anterior emitia
    una observacion (aunque INFO) cuando no habia titulos: convertia un
    elemento opcional en un supuesto incumplimiento. Se conserva el ID por
    compatibilidad, pero se registra como NOT_APPLICABLE y no genera hallazgos.
    """

    def __init__(self) -> None:
        super().__init__(
            id="HEAD-001",
            name="Estructura de títulos (opcional)",
            category=Category.TITULOS,
            description=(
                "APA 7 no exige encabezados en todos los trabajos; se usan solo "
                "los niveles necesarios. Esta regla no genera observaciones."
            ),
            default_severity=Severity.INFO,
            norm_source=HEADINGS_URL,
            exceptions="Trabajos estudiantiles cortos pueden no tener ningún encabezado.",
        )

    def check(self, document: ParsedDocument) -> list[Finding]:
        return []


class HeadingLevelFormatRule(Rule):
    def __init__(self) -> None:
        super().__init__(
            id="HEAD-002",
            name="Formato de títulos por nivel",
            category=Category.TITULOS,
            description=(
                "Cada nivel de título debe cumplir el formato APA: alineación, "
                "negrita, cursiva, sangría y puntuación para niveles 4 y 5."
            ),
            norm_source=HEADINGS_URL,
            exceptions=(
                "Mayúscula de tipo título (title case) no se verifica: en español "
                "no hay evidencia determinista suficiente. Niveles 4/5 son "
                "encabezados en línea; se evalúa el fragmento en negrita."
            ),
        )

    def check(self, document: ParsedDocument) -> list[Finding]:
        findings: list[Finding] = []
        for p in document.body_paragraphs:
            level = p.heading_level
            if not level:
                continue
            spec = HEADING_SPEC.get(level)
            if not spec:
                continue
            bold, italic = _run_style(p)

            problems: list[str] = []
            if not bold and not (level in (4, 5) and _bold_prefix(p)):
                problems.append("debe ir en negrita")
            if italic != spec["italic"]:
                problems.append("debe ir en cursiva" if spec["italic"] else "no debe ir en cursiva")
            if level in (1, 2, 3) and p.alignment not in (spec["alignment"], None):
                expected = "centrado" if spec["alignment"] == "center" else "a la izquierda"
                problems.append(f"debe alinearse {expected}")
            if spec["indented"] and not _indented(p):
                problems.append("debe llevar sangría de 0.5 in")
            if spec["period"] and not _inline_period_ok(p):
                problems.append("debe terminar con punto y el texto sigue en la misma línea")

            if problems:
                expected = (
                    f"Nivel {level}: "
                    f"{'centrado' if spec['alignment'] == 'center' else 'izquierda'}, "
                    f"negrita{' y cursiva' if spec['italic'] else ''}"
                    f"{', sangrado y punto final antes del texto' if spec['indented'] else ''}."
                )
                findings.append(
                    self.finding(
                        f"Título de nivel {level} incumple el formato APA 7: {', '.join(problems)}.",
                        paragraph_index=p.index,
                        location=f"Párrafo {p.index + 1}",
                        excerpt=p.excerpt(),
                        suggestion=expected,
                        extra={"heading_level": level, "problems": problems},
                    )
                )
        return findings


class HeadingHierarchyRule(Rule):
    """Continuidad de niveles, sin exigir que el primer titulo sea nivel 1.

    La pagina oficial: el titulo del trabajo actua como nivel 1 de facto, la
    introduccion NO lleva encabezado y sus subapartados pueden ser nivel 2/3.
    Por tanto 'el primer titulo debe ser nivel 1' era un falso positivo.
    """

    def __init__(self) -> None:
        super().__init__(
            id="HEAD-003",
            name="Jerarquía de títulos sin saltos",
            category=Category.TITULOS,
            description="No deben saltarse niveles de encabezado (1 -> 3).",
            norm_source=HEADINGS_URL,
            exceptions=(
                "El título del trabajo actúa como nivel 1 de facto; la "
                "introducción no lleva encabezado y puede empezar en nivel 2/3."
            ),
        )

    def check(self, document: ParsedDocument) -> list[Finding]:
        findings: list[Finding] = []
        headings = [p for p in document.body_paragraphs if p.heading_level]
        if len(headings) < 2:
            return findings
        prev = headings[0].heading_level or 1
        for p in headings[1:]:
            level = p.heading_level or 1
            if level > prev + 1:
                findings.append(
                    self.finding(
                        f"Salto de jerarquía: nivel {prev} -> nivel {level}.",
                        paragraph_index=p.index,
                        location=f"Párrafo {p.index + 1}",
                        excerpt=p.excerpt(),
                        suggestion="No saltar niveles; usar el nivel inmediatamente inferior.",
                        extra={"from_level": prev, "to_level": level},
                    )
                )
            prev = level
        return findings


HEADING_NUMBER_RE = re.compile(r"^\s*(\d+)(?:[.)]\d+)*[.)]?\s+\S")
NUMBERED_HEADING_RE = re.compile(
    r"^\s*(?:\d+(?:[.)]\d+)*[.)]?|[A-ZÁÉÍÓÚÑ][.)])\s+\S"
)
TOC_ENTRY_RE = re.compile(r"[.\u2026]{3,}|\t|\s{2,}\s*\d{1,3}\s*$")
LETTERS_RE = re.compile(r"[A-Za-z\u00c0-\u00ff]")
# Excepciones: rotulos de elementos, anexos y capitulos de tesis (perfil
# institucional, fuera del alcance de esta etapa).
NUMBERING_EXEMPT_RE = re.compile(
    r"^\s*(?:anexo|ap[eé]ndice|appendix|figura|figure|tabla|table|"
    r"cap[ií]tulo|chapter|resumen|abstract)\b",
    re.IGNORECASE,
)


def _is_uppercase(text: str) -> bool:
    letters = LETTERS_RE.findall(text)
    if len(letters) < 3:
        return False
    return text.upper() == text


def _bold_ratio(paragraph: ParagraphInfo) -> float:
    runs = [r for r in paragraph.runs if r.text.strip()]
    if not runs:
        return 0.0
    total = sum(len(r.text) for r in runs)
    if total == 0:
        return 0.0
    bold_chars = sum(len(r.text) for r in runs if r.bold)
    return bold_chars / total


def _looks_like_old_toc_entry(paragraph: ParagraphInfo) -> bool:
    return bool(TOC_ENTRY_RE.search(paragraph.text))


class NumberedHeadingRule(Rule):
    """APA 7: 'Do not label headings with numbers or letters'.

    Solo se evalúan párrafos que YA usan un estilo de encabezado de Word: hay
    evidencia estructural de que son títulos, no párrafos numerados ni tablas.
    """

    def __init__(self) -> None:
        super().__init__(
            id="HEAD-005",
            name="Encabezados sin numeración",
            category=Category.TITULOS,
            description="APA 7 prohíbe etiquetar los encabezados con números o letras.",
            norm_source=HEADINGS_URL,
            exceptions=(
                "Índice/TOC; rótulos de figuras, tablas, anexos y apéndices; "
                "capítulos de tesis (perfil institucional excluido en esta etapa); "
                "entradas de la lista de referencias."
            ),
        )

    def check(self, document: ParsedDocument) -> list[Finding]:
        # Excepción de perfil institucional: si la institución autoriza o exige títulos numerados
        if getattr(document, "allow_numbered_headings", False) or getattr(document, "institutional_profile", {}).get("allow_numbered_headings", False):
            return []
        findings: list[Finding] = []
        for p in document.body_paragraphs:
            if not p.heading_level:
                continue
            text = p.text.strip()
            if not text or NUMBERING_EXEMPT_RE.match(text):
                continue
            if _looks_like_old_toc_entry(p):
                continue
            if document.references_start is not None and p.index >= document.references_start:
                continue
            if not NUMBERED_HEADING_RE.match(text):
                continue
            findings.append(
                self.finding(
                    f"El encabezado '{p.excerpt(80)}' está numerado; APA 7 no "
                    "etiqueta los títulos con números ni letras.",
                    paragraph_index=p.index,
                    location=f"Página {p.estimated_page} (párrafo {p.index + 1})",
                    excerpt=p.excerpt(90),
                    suggestion=(
                        "Quitar el número o la letra del encabezado y mantener "
                        "la jerarquía con el estilo de Word correspondiente."
                    ),
                    extra={"heading_numbered": True, "heading_level": p.heading_level},
                )
            )
        return findings


class HeadingStyleRule(Rule):
    """Parrafos que parecen titulos pero NO usan estilos nativos de Word.

    Precision: NO se determina el nivel por el tamaño ni por la negrita
    aislada. Se exige estilo de Word, contexto estructural y al menos dos
    señales, y se excluyen los capitulos de tesis (perfil institucional).
    """

    def __init__(self) -> None:
        super().__init__(
            id="HEAD-004",
            name="Títulos sin estilo de encabezado",
            category=Category.TITULOS,
            description=(
                "Los párrafos que funcionan como títulos deben usar los estilos "
                "de encabezado de Word; el índice automático no los reconoce "
                "si solo están en negrita o en un tamaño mayor."
            ),
            default_severity=Severity.ERROR,
            norm_source=HEADINGS_URL,
            exceptions=(
                "Portada, índice/TOC, rótulos de tablas/figuras, lista de "
                "referencias, capítulos de tesis y apéndices. No se infiere el "
                "nivel por el tamaño de fuente ni por la negrita aislada."
            ),
        )

    def _signals(self, p: ParagraphInfo, document: ParsedDocument) -> list[str]:
        signals: list[str] = []
        text = p.text.strip()
        if _is_uppercase(text):
            signals.append("Mayúsculas")
        if _bold_ratio(p) >= 0.6:
            signals.append("Negrita")
        if NUMBERING_EXEMPT_RE.match(text):
            signals.append("Rótulo estructural")
        return signals

    def _is_candidate(
        self,
        p: ParagraphInfo,
        document: ParsedDocument,
        index: int = 0,
        paragraphs: list[ParagraphInfo] | None = None,
    ) -> bool:
        text = p.text.strip()
        if not text or p.heading_level:
            return False
        if p.is_list_item or p.in_table or getattr(p, "has_image", False):
            return False
        try:
            if document.is_chapter_title(p) or document.is_cover_paragraph(p):
                return False
        except Exception:
            pass
        if len(text) > 120 or len(text.split()) > 14:
            return False
        if _looks_like_old_toc_entry(p):
            return False
        if document.references_start is not None and p.index > document.references_start:
            return False
        if NUMBERING_EXEMPT_RE.match(text):
            return False
        if text.endswith((".", ",", ";", ":")) and len(text.split()) > 8:
            return False
        if p.alignment == "center" and len(text.split()) > 10:
            return False
        return self._looks_like_heading_by_context(
            index, paragraphs if paragraphs is not None else [p]
        )

    @staticmethod
    def _looks_like_heading_by_context(index: int, paragraphs: list[ParagraphInfo]) -> bool:
        """Linea corta, aislada y seguida de un parrafo de cuerpo."""
        if index >= len(paragraphs):
            return False
        current = paragraphs[index]
        prev = paragraphs[index - 1] if index > 0 else None
        nxt = paragraphs[index + 1] if index + 1 < len(paragraphs) else None
        if len(current.text.split()) > 8:
            return False
        prev_ok = (
            prev is None
            or prev.is_empty
            or bool(prev.heading_level)
            or prev.text.strip().endswith((".", ":"))
        )
        nxt_ok = (
            nxt is None
            or nxt.is_empty
            or bool(nxt.heading_level)
            or len(nxt.text.split()) >= 5
        )
        return prev_ok and nxt_ok

    def check(self, document: ParsedDocument) -> list[Finding]:
        findings: list[Finding] = []
        paragraphs = document.body_paragraphs
        for index, p in enumerate(paragraphs):
            if getattr(p, "estimated_page", 1) == 1 and index < 6:
                continue  # portada
            if not self._is_candidate(p, document, index, paragraphs):
                continue
            signals = self._signals(p, document)
            # Al menos DOS señales independientes: el tamaño ya no se usa y la
            # negrita aislada no basta.
            if len(signals) < 2:
                continue
            style = (p.style_name or "Normal").strip() or "Normal"
            findings.append(
                self.finding(
                    f"Título sin estilo asignado: \"{p.excerpt(90)}\". "
                    f"Señales: {' / '.join(dict.fromkeys(signals))} "
                    f"(Estilo actual: {style}).",
                    paragraph_index=p.index,
                    location=f"Página {p.estimated_page} (párrafo {p.index + 1})",
                    excerpt=p.excerpt(90),
                    suggestion=(
                        "Aplicar el estilo de encabezado de Word que corresponda "
                        "a su jerarquía real (Título 1, 2 o 3), sin numerar el texto."
                    ),
                    extra={
                        "heading_style_missing": True,
                        "page": p.estimated_page,
                        "text": p.excerpt(120),
                        "detected_format": " / ".join(signals),
                        "style_name": style,
                    },
                )
            )
        return findings


RULES = [
    StructureRule(),
    HeadingLevelFormatRule(),
    HeadingHierarchyRule(),
    HeadingStyleRule(),
    NumberedHeadingRule(),
]
