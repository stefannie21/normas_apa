from __future__ import annotations

import re

from backend.app.rules.base import Category, Finding, Rule, Severity
from backend.app.services.docx_parser import ParsedDocument

YEAR_RE = re.compile(r"\b(1[89]\d{2}|20\d{2})\b")
PAREN_RE = re.compile(r"\(([^()]*)\)")
# Nombres tipo "Garcia" o "Garcia, J." o "Garcia & Lopez"
NAME_TOKEN = r"[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+"
# un solo apellido seguido de coma y/o "et al." (p.ej. "(Garcia, 2020)", "(Garcia et al., 2020)")
SINGLE_AUTHOR_RE = re.compile(
    rf"{NAME_TOKEN}\s*(?:,\s*[A-Z]{{1,3}}\.?)?(?:\s+et\s+al\.?)?\s*(?:,|;|\d)",
)
# dos o mas nombres consecutivos
MULTI_AUTHOR_RE = re.compile(rf"{NAME_TOKEN}(?:\s*(?:,|&|y|and)\s*{NAME_TOKEN}){{1,}}")
CITATION_LIKE_RE = re.compile(f"{SINGLE_AUTHOR_RE.pattern}|{MULTI_AUTHOR_RE.pattern}")
ET_AL_BAD_RE = re.compile(r"\bet\s?al\b(?!\.)", re.IGNORECASE)
AMP_IN_PAREN_RE = re.compile(rf"{NAME_TOKEN}\s+(?:and|y)\s+{NAME_TOKEN}")
QUOTE_CITE_RE = re.compile(r"[\"“«][^\"”»]{0,600}[\"”»]\s*\(([^()]*)\)")


class CitationYearRule(Rule):
    def __init__(self) -> None:
        super().__init__(
            id="CIT-001",
            name="Citas con autor y ano",
            category=Category.CITAS,
            description="Toda cita en el texto debe incluir autor y ano de publicacion.",
            default_severity=Severity.ERROR,
        )

    def check(self, document: ParsedDocument) -> list[Finding]:
        findings: list[Finding] = []
        for p in document.body_paragraphs:
            if document.references_start is not None and p.index > document.references_start:
                continue
            for match in PAREN_RE.finditer(p.text):
                inner = match.group(1).strip()
                if len(inner) < 5:
                    continue
                if not CITATION_LIKE_RE.search(inner):
                    continue
                if not YEAR_RE.search(inner):
                    findings.append(
                        self.finding(
                            f"Cita sin ano de publicacion: '({inner})'.",
                            paragraph_index=p.index,
                            location=f"Parrafo {p.index + 1}",
                            excerpt=p.excerpt(),
                            suggestion="Agregar el ano: (Autor, ano).",
                        )
                    )
                    break  # un hallazgo por parrafo: evita duplicar el mismo problema
        return findings


class AmpersandRule(Rule):
    def __init__(self) -> None:
        super().__init__(
            id="CIT-002",
            name="Uso de & y 'and'/'y'",
            category=Category.CITAS,
            description="Usar '&' dentro del parentesis y 'and'/'y' en el texto narrativo.",
        )

    def check(self, document: ParsedDocument) -> list[Finding]:
        findings: list[Finding] = []
        for p in document.body_paragraphs:
            if document.references_start is not None and p.index > document.references_start:
                continue
            for match in PAREN_RE.finditer(p.text):
                if AMP_IN_PAREN_RE.search(match.group(1)):
                    findings.append(
                        self.finding(
                            "Dentro de una cita parentetica se uso 'and'/'y'; APA usa '&'.",
                            paragraph_index=p.index,
                            location=f"Parrafo {p.index + 1}",
                            excerpt=match.group(0),
                            suggestion="Reemplazar 'and'/'y' por '&' dentro del parentesis.",
                        )
                    )
                    break  # un hallazgo por parrafo
        return findings


class EtAlRule(Rule):
    def __init__(self) -> None:
        super().__init__(
            id="CIT-003",
            name="Formato de 'et al.'",
            category=Category.CITAS,
            description="'et al.' debe escribirse sin cursiva con punto final.",
            default_severity=Severity.WARNING,
        )

    def check(self, document: ParsedDocument) -> list[Finding]:
        findings: list[Finding] = []
        for p in document.body_paragraphs:
            if document.references_start is not None and p.index > document.references_start:
                continue
            for match in ET_AL_BAD_RE.finditer(p.text):
                findings.append(
                    self.finding(
                        "'et al.' sin punto final en una cita.",
                        paragraph_index=p.index,
                        location=f"Parrafo {p.index + 1}",
                        excerpt=p.excerpt(),
                        suggestion="Escribir 'et al.' con punto al final.",
                    )
                )
                break  # un hallazgo por parrafo
        return findings


class QuotePageRule(Rule):
    def __init__(self) -> None:
        super().__init__(
            id="CIT-004",
            name="Citas textuales con pagina",
            category=Category.CITAS,
            description="Las citas textuales (entre comillas) deben indicar numero de pagina o parrafo.",
        )

    def check(self, document: ParsedDocument) -> list[Finding]:
        findings: list[Finding] = []
        for p in document.body_paragraphs:
            if document.references_start is not None and p.index > document.references_start:
                continue
            for match in QUOTE_CITE_RE.finditer(p.text):
                inner = match.group(1)
                if not re.search(r"\b(pp?\.|párr\.|parr\.|para\.)\s*\d", inner, re.IGNORECASE):
                    findings.append(
                        self.finding(
                            "Cita textual sin numero de pagina/parrafo (p., pp., párr.).",
                            paragraph_index=p.index,
                            location=f"Parrafo {p.index + 1}",
                            excerpt=p.excerpt(),
                            suggestion="Agregar 'p. X' o 'pp. X-X' (o 'párr. X') en citas textuales.",
                        )
                    )
        return findings


RULES = [
    CitationYearRule(),
    AmpersandRule(),
    EtAlRule(),
    QuotePageRule(),
]
