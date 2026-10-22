from __future__ import annotations

import re
import unicodedata

from backend.app.rules.base import Category, Finding, Rule, Severity
from backend.app.services.docx_parser import ParsedDocument

YEAR_RE = re.compile(r"\b(1[89]\d{2}|20\d{2})\b")
PAREN_YEAR_FLEX_RE = re.compile(
    r"\(\s*(?:[^)]*?\b)?(1[89]\d{2}|20\d{2}|\d{4})[a-z]?\b[^)]*\)",
    re.IGNORECASE,
)
PAREN_NO_DATE_RE = re.compile(r"\(\s*(?:s\.?\s*f\.?|n\.?\s*d\.?)\s*\)", re.IGNORECASE)
YEAR_GENERAL_RE = re.compile(r"\b(1[89]\d{2}|20\d{2})\b")
HANGING_TOLERANCE_IN = 0.1
DOI_PLAIN_RE = re.compile(r"\bdoi:\s*10\.", re.IGNORECASE)
URL_RE = re.compile(r"https?://", re.IGNORECASE)


def _sort_key(text: str) -> str:
    text = text.strip().lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    return text


class ReferencesPresenceRule(Rule):
    def __init__(self) -> None:
        super().__init__(
            id="REF-001",
            name="Sección de referencias",
            category=Category.REFERENCIAS,
            description="El documento debe incluir una lista de referencias titulada 'Referencias'.",
            default_severity=Severity.ERROR,
        )

    def check(self, document: ParsedDocument) -> list[Finding]:
        has_any_citation = False
        for p in document.body_paragraphs:
            if document.references_start is not None and p.index > document.references_start:
                continue
            if re.search(r"\(\s*[A-ZÁÉÍÓÚÑ][^()]*\d{4}", p.text):
                has_any_citation = True
                break

        if document.references_start is None:
            if has_any_citation:
                return [
                    self.finding(
                        "Se encontraron citas pero no una sección 'Referencias'.",
                        location="Documento",
                        suggestion="Agregar el título 'Referencias' (centrado, negrita) y la lista correspondiente.",
                    )
                ]
            return [
                self.finding(
                    "No se encontró la sección 'Referencias'.",
                    location="Documento",
                    suggestion="El documento debe cerrar con una lista de referencias bajo el título 'Referencias'.",
                )
            ]
        return []


class HangingIndentRule(Rule):
    def __init__(self) -> None:
        super().__init__(
            id="REF-002",
            name="Sangría francesa en referencias",
            category=Category.REFERENCIAS,
            description="Cada referencia debe usar sangría francesa de 1.27 cm (0.5 in).",
        )

    def check(self, document: ParsedDocument) -> list[Finding]:
        findings: list[Finding] = []
        for p in document.reference_paragraphs():
            indent = p.left_indent_in
            first = p.first_line_indent_in
            hanging = indent is not None and abs(indent - 0.5) <= HANGING_TOLERANCE_IN
            negative_first = first is not None and first < 0
            if not (hanging or negative_first):
                shown = f"izq={indent if indent is not None else 'n/d'}, 1a línea={first if first is not None else 'n/d'}"
                findings.append(
                    self.finding(
                        f"Referencia sin sangría francesa ({shown}).",
                        paragraph_index=p.index,
                        location=f"Párrafo {p.index + 1}",
                        excerpt=p.excerpt(),
                        suggestion="Aplicar sangría francesa: 1.27 cm a la izquierda y -1.27 cm en primera línea.",
                    )
                )
        return findings


class AlphabeticalOrderRule(Rule):
    def __init__(self) -> None:
        super().__init__(
            id="REF-003",
            name="Orden alfabético de referencias",
            category=Category.REFERENCIAS,
            description="La lista de referencias debe ordenarse alfabéticamente por autor.",
            default_severity=Severity.WARNING,
        )

    def check(self, document: ParsedDocument) -> list[Finding]:
        refs = document.reference_paragraphs()
        if len(refs) < 2:
            return []
        keys = [(_sort_key(p.text), p) for p in refs if p.text.strip()]
        findings: list[Finding] = []
        for (prev_key, prev_p), (key, p) in zip(keys, keys[1:]):
            if key < prev_key:
                findings.append(
                    self.finding(
                        "La lista de referencias no está en orden alfabético.",
                        paragraph_index=p.index,
                        location=f"Párrafo {p.index + 1}",
                        excerpt=p.excerpt(),
                        suggestion="Ordenar las referencias alfabéticamente por el apellido del primer autor.",
                    )
                )
                break
        return findings


class ReferenceYearRule(Rule):
    def __init__(self) -> None:
        super().__init__(
            id="REF-004",
            name="Año en cada referencia",
            category=Category.REFERENCIAS,
            description="Cada referencia debe incluir el año de publicación.",
            default_severity=Severity.ERROR,
        )

    def check(self, document: ParsedDocument) -> list[Finding]:
        findings: list[Finding] = []
        bib = document.bibliography
        bib_years: set[int] = set()
        if bib and bib.references:
            bib_years = {r.paragraph_index for r in bib.references if r.year is not None}

        for p in document.reference_paragraphs():
            if len(p.text.strip()) < 15:
                continue
            # 1. Si la referencia estructurada ya identificó el año para este párrafo
            if p.index in bib_years:
                continue
            # 2. Patrón flexible de año (AAAA) o sin fecha (s.f.) entre paréntesis en el encabezado/texto
            if PAREN_YEAR_FLEX_RE.search(p.text) or PAREN_NO_DATE_RE.search(p.text):
                continue
            # 3. Detección general de año de 4 dígitos en el texto
            if YEAR_GENERAL_RE.search(p.text):
                continue

            findings.append(
                self.finding(
                    "Referencia sin año de publicación.",
                    paragraph_index=p.index,
                    location=f"Párrafo {p.index + 1}",
                    excerpt=p.excerpt(),
                    suggestion="Incluir el año entre paréntesis: (2020).",
                )
            )
        return findings


class DoiFormatRule(Rule):
    def __init__(self) -> None:
        super().__init__(
            id="REF-005",
            name="Formato de DOI",
            category=Category.REFERENCIAS,
            description="Los DOI deben presentarse como URL: https://doi.org/xxxx",
            default_severity=Severity.INFO,
        )

    def check(self, document: ParsedDocument) -> list[Finding]:
        findings: list[Finding] = []
        for p in document.reference_paragraphs():
            if DOI_PLAIN_RE.search(p.text) and not URL_RE.search(p.text):
                findings.append(
                    self.finding(
                        "DOI en formato 'doi:...' en lugar de URL.",
                        paragraph_index=p.index,
                        location=f"Párrafo {p.index + 1}",
                        excerpt=p.excerpt(),
                        suggestion="Usar 'https://doi.org/xxxx' o 'https://dx.doi.org/xxxx'.",
                    )
                )
        return findings


RULES = [
    ReferencesPresenceRule(),
    HangingIndentRule(),
    AlphabeticalOrderRule(),
    ReferenceYearRule(),
    DoiFormatRule(),
]
