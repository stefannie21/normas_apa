from __future__ import annotations

import re

from backend.app.rules.base import Category, Finding, Rule, Severity
from backend.app.services.docx_parser import ParsedDocument, ParagraphInfo

# APA 7 - formato por nivel de titulo.
# Nivel 1: centrado, negrita, mayuscula de titulo
# Nivel 2: izquierda, negrita
# Nivel 3: izquierda, negrita cursiva
# Nivel 4: sangrado, negrita, termina en punto
# Nivel 5: sangrado, negrita cursiva, termina en punto
HEADING_SPEC = {
    1: {"alignment": "center", "bold": True, "italic": False},
    2: {"alignment": "left", "bold": True, "italic": False},
    3: {"alignment": "left", "bold": True, "italic": True},
    4: {"alignment": "left", "bold": True, "italic": False},
    5: {"alignment": "left", "bold": True, "italic": True},
}


def _run_style(paragraph: ParagraphInfo) -> tuple[bool, bool]:
    runs = [r for r in paragraph.runs if r.text.strip()]
    if not runs:
        return False, False
    bold = all(r.bold for r in runs)
    italic = all(r.italic for r in runs)
    return bold, italic


class StructureRule(Rule):
    def __init__(self) -> None:
        super().__init__(
            id="HEAD-001",
            name="Estructura de titulos",
            category=Category.TITULOS,
            description="El documento debe organizar el contenido mediante títulos y subtítulos con estilos.",
            default_severity=Severity.INFO,
        )

    def check(self, document: ParsedDocument) -> list[Finding]:
        headings = [p for p in document.body_paragraphs if p.heading_level]
        if not headings:
            return [
                self.finding(
                    "No se detectaron títulos con estilos de encabezado. APA recomienda jerarquizar el contenido.",
                    location="Documento",
                    suggestion="Aplicar estilos Título 1, Título 2, etc. (Heading 1, Heading 2...) segun la jerarquia.",
                )
            ]
        return []


class HeadingLevelFormatRule(Rule):
    def __init__(self) -> None:
        super().__init__(
            id="HEAD-002",
            name="Formato de títulos por nivel",
            category=Category.TITULOS,
            description="Cada nivel de título debe cumplir el formato APA (alineacion, negrita, cursiva).",
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

            problems = []
            if not bold:
                problems.append("debe ir en negrita")
            if italic != spec["italic"]:
                problems.append("debe ir en cursiva" if spec["italic"] else "no debe ir en cursiva")
            if level in (1, 2, 3) and p.alignment not in (spec["alignment"], None):
                expected = "centrado" if spec["alignment"] == "center" else "a la izquierda"
                problems.append(f"debe alinearse {expected}")

            if problems:
                findings.append(
                    self.finding(
                        f"Titulo nivel {level} incumple el formato APA: {', '.join(problems)}.",
                        paragraph_index=p.index,
                        location=f"Parrafo {p.index + 1}",
                        excerpt=p.excerpt(),
                        suggestion=(
                            f"Nivel {level}: {'centrado' if spec['alignment'] == 'center' else 'izquierda'}, "
                            f"{'negrita' if spec['bold'] else 'sin negrita'}"
                            f"{' y cursiva' if spec['italic'] else ''}."
                        ),
                    )
                )
        return findings


class HeadingHierarchyRule(Rule):
    def __init__(self) -> None:
        super().__init__(
            id="HEAD-003",
            name="Jerarquia de titulos sin saltos",
            category=Category.TITULOS,
            description="El primer nivel debe ser 1 y no deben saltarse niveles (1 -> 3).",
        )

    def check(self, document: ParsedDocument) -> list[Finding]:
        findings: list[Finding] = []
        headings = [p for p in document.body_paragraphs if p.heading_level]
        if not headings:
            return findings
        first = headings[0]
        if first.heading_level != 1:
            findings.append(
                self.finding(
                    f"El primer titulo es de nivel {first.heading_level}; APA espera empezar en nivel 1.",
                    paragraph_index=first.index,
                    location=f"Parrafo {first.index + 1}",
                    excerpt=first.excerpt(),
                    suggestion="Usar un titulo de nivel 1 para el primer encabezado del documento.",
                )
            )
        prev = 1
        for p in headings[1:]:
            level = p.heading_level or 1
            if level > prev + 1:
                findings.append(
                    self.finding(
                        f"Salto de jerarquia: nivel {prev} -> nivel {level}.",
                        paragraph_index=p.index,
                        location=f"Parrafo {p.index + 1}",
                        excerpt=p.excerpt(),
                        suggestion="No saltar niveles; usar el nivel inmediatamente inferior.",
                    )
                )
            prev = level
        return findings


HEADING_NUMBER_RE = re.compile(r"^\s*(\d+)(?:[.)]\d+)*[.)]?\s+\S")
TOC_ENTRY_RE = re.compile(r"[.\u2026]{3,}|\t|\s{2,}\s*\d{1,3}\s*$")
LETTERS_RE = re.compile(r"[A-Za-z\u00c0-\u00ff]")


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


class HeadingStyleRule(Rule):
    """Detecta parrafos que parecen titulos pero NO usan estilos nativos de Word.

    Sin estilo 'Heading 1/2/3' el indice automatico de Word no los incluye,
    por lo que se reportan como error con su ubicacion exacta.
    """

    def __init__(self) -> None:
        super().__init__(
            id="HEAD-004",
            name="Titulos sin estilo de encabezado",
            category=Category.TITULOS,
            description=(
                "Los parrafos que parecen titulos (negrita, mayusculas o tamano mayor) "
                "deben usar los estilos Titulo 1, Titulo 2 o Titulo 3 de Word; de lo "
                "contrario el indice automatico no los recognize."
            ),
            default_severity=Severity.ERROR,
        )

    # -- senales de "parece titulo" -------------------------------------
    def _signals(self, p: ParagraphInfo, document: ParsedDocument) -> list[str]:
        signals: list[str] = []
        text = p.text.strip()
        if _is_uppercase(text):
            signals.append("Mayusculas")
        if _bold_ratio(p) >= 0.6:
            signals.append("Negrita")
        size = p.max_size_pt
        base = document.default_font_size_pt or 12.0
        if size is not None and size > base + 0.6:
            signals.append("Tamano mayor")
        elif size is not None and size >= 14.0:
            signals.append("Tamano mayor")
        if HEADING_NUMBER_RE.match(text):
            signals.append("Numeracion de capitulo")
        return signals

    def _is_candidate(
        self,
        p: ParagraphInfo,
        document: ParsedDocument,
        index: int = 0,
        paragraphs: list[ParagraphInfo] | None = None,
    ) -> bool:
        text = p.text.strip()
        if not text or p.heading_level:  # ya usa estilo de titulo
            return False
        if p.is_list_item:
            return False
        if len(text) > 120 or len(text.split()) > 14:
            return False
        if _looks_like_old_toc_entry(p):
            return False
        if document.references_start is not None and p.index > document.references_start:
            return False
        # una frase normal terminada en punto y con mas de 8 palabras no es un titulo
        if text.endswith((".", ",", ";", ":")) and len(text.split()) > 8:
            return False
        # una cita textual centrada no es un encabezado
        if p.alignment == "center" and len(text.split()) > 10:
            return False

        signals = self._signals(p, document)
        if not signals:
            return False
        # La negrita aislada NO basta: en una tesis hay palabras resaltadas en
        # negrita en casi todos los parrafos. Se exige una senal estructural o,
        # en su defecto, que el contexto sea tipico de un encabezado.
        strong = {"Mayusculas", "Tamano mayor", "Numeracion de capitulo"}
        if set(signals) & strong:
            # si es solo "mayusculas", ademas debe ser una linea corta y sin punto final
            if signals == ["Mayusculas"] and len(text.split()) > 8:
                return False
            return True
        return self._looks_like_heading_by_context(
            index, paragraphs if paragraphs is not None else [p]
        )

    @staticmethod
    def _looks_like_heading_by_context(index: int, paragraphs: list[ParagraphInfo]) -> bool:
        """Linea corta en negrita, precedida de un titulo/vacio y seguida de un
        parrafo largo: es un encabezado con formato manual, no una frase resaltada."""
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
            if not self._is_candidate(p, document, index, paragraphs):
                continue
            signals = self._signals(p, document)
            if not (set(signals) & {"Mayusculas", "Tamano mayor", "Numeracion de capitulo"}):
                signals = signals + ["Encabezado por contexto"]
            style = (p.style_name or "Normal").strip() or "Normal"
            detected = " / ".join(dict.fromkeys(signals))
            level_guess = 2 if HEADING_NUMBER_RE.match(p.text.strip()) and "." in p.text.strip()[:6] else 1
            findings.append(
                self.finding(
                    f"Titulo sin estilo asignado: \"{p.excerpt(90)}\" - "
                    f"Formato detectado: {detected} (Estilo actual: {style}).",
                    paragraph_index=p.index,
                    location=f"Pagina {p.estimated_page} (parrafo {p.index + 1})",
                    excerpt=p.excerpt(90),
                    suggestion=(
                        f"Aplicar el estilo 'Titulo {level_guess}' de Word a este parrafo "
                        f"para que aparezca en el indice automatico."
                    ),
                    extra={
                        "heading_style_missing": True,
                        "page": p.estimated_page,
                        "text": p.excerpt(120),
                        "detected_format": detected,
                        "style_name": style,
                        "suggested_level": level_guess,
                    },
                )
            )
        return findings


RULES = [
    StructureRule(),
    HeadingLevelFormatRule(),
    HeadingHierarchyRule(),
    HeadingStyleRule(),
]
