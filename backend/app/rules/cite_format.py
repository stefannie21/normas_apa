"""Reglas de formato de citas en el texto que el documento de asesoria exige y que
no se verificaban: umbral de 'et al.', tratamiento de la cita en bloque y
posicion del punto final segun el tipo de cita.
"""
from __future__ import annotations

import re

from backend.app.rules.base import Category, Finding, Rule, Severity
from backend.app.services.docx_parser import ParsedDocument

BLOCK_MIN_WORDS = 40
ET_AL_THRESHOLD = 3


class EtAlThresholdRule(Rule):
    """Con tres o más autores se usa 'primer apellido et al.' desde la primera mención."""

    def __init__(self) -> None:
        super().__init__(
            id="CIT-005",
            name="Uso de 'et al.' con tres o más autores",
            category=Category.CITAS,
            description=(
                "Las obras de tres o más autores se citan con el primer apellido "
                "seguido de 'et al.' desde la primera mención."
            ),
            default_severity=Severity.WARNING,
        )

    def check(self, document: ParsedDocument) -> list[Finding]:
        bib = document.bibliography
        if not bib or not bib.references:
            return []
        # solo se considera fiable un conteo confirmado por iniciales: sin ellas
        # el conteo de autores es ambiguo ('Sanchez Perez, Juan y Lopez, Maria')
        multi_author = {
            r.surnames[0]
            for r in bib.references
            if r.surnames
            and r.author_count >= ET_AL_THRESHOLD
            and r.initials_count >= 2
            and not r.corporate
        }
        if not multi_author:
            return []
        findings: list[Finding] = []
        seen: set[tuple[int, str]] = set()
        for c in bib.citations:
            if not c.surnames:
                continue
            surname = c.surnames[0]
            if surname not in multi_author:
                continue
            if c.has_et_al:
                continue
            # cita que lista dos o mas apellidos de una obra de 3+ autores
            if len(c.surnames) >= 2:
                key = (c.paragraph_index, surname.lower())
                if key in seen:
                    continue
                seen.add(key)
                findings.append(
                    self.finding(
                        f"Obra de {len(c.surnames)}+ autores citada sin 'et al.': {surname}.",
                        paragraph_index=c.paragraph_index,
                        location=f"Página {c.page} (párrafo {c.paragraph_index + 1})",
                        excerpt=c.raw,
                        suggestion=f"Usar '{surname} et al.' desde la primera mención.",
                        extra={"bib_kind": "et_al_missing", "surname": surname},
                    )
                )
        return findings


class BlockQuoteRule(Rule):
    """Cita en bloque de 40 palabras o más: sin comillas, sangría y punto antes del paréntesis."""

    def __init__(self) -> None:
        super().__init__(
            id="CIT-006",
            name="Cita textual en bloque",
            category=Category.CITAS,
            description=(
                "Las citas de 40 palabras o más van en bloque independiente, sin "
                "comillas, con sangría de 1.27 cm y con el punto antes del paréntesis."
            ),
            default_severity=Severity.WARNING,
        )

    def check(self, document: ParsedDocument) -> list[Finding]:
        bib = document.bibliography
        if not bib:
            return []
        findings: list[Finding] = []
        for p in document.body_paragraphs:
            text = p.text.strip()
            words = len(text.split())
            if words < BLOCK_MIN_WORDS:
                continue
            has_quotes = '"' in text or "\u201c" in text
            indented = p.left_indent_in is not None and p.left_indent_in >= 0.4
            if has_quotes and not indented:
                findings.append(
                    self.finding(
                        f"Cita de {words} palabras entrecomillada; a partir de "
                        f"{BLOCK_MIN_WORDS} palabras debe ir en bloque, sin comillas.",
                        paragraph_index=p.index,
                        location=f"Página {p.estimated_page} (párrafo {p.index + 1})",
                        excerpt=p.excerpt(140),
                        suggestion="Quitar comillas y aplicar sangría de 1.27 cm al bloque.",
                        extra={"bib_kind": "block_should_be_plain", "words": words},
                    )
                )
            elif indented and has_quotes:
                findings.append(
                    self.finding(
                        f"Cita en bloque de {words} palabras conserva las comillas.",
                        paragraph_index=p.index,
                        location=f"Página {p.estimated_page} (párrafo {p.index + 1})",
                        excerpt=p.excerpt(140),
                        suggestion="En bloque no se usan comillas.",
                        extra={"bib_kind": "block_has_quotes", "words": words},
                    )
                )
        return findings


class CitationPeriodRule(Rule):
    """Posición del punto final: después del paréntesis en citas cortas, antes en bloque."""

    def __init__(self) -> None:
        super().__init__(
            id="CIT-007",
            name="Punto final de la cita",
            category=Category.CITAS,
            description=(
                "En citas cortas el punto va después del paréntesis; en la cita en "
                "bloque, antes del paréntesis."
            ),
            default_severity=Severity.WARNING,
        )

    def check(self, document: ParsedDocument) -> list[Finding]:
        bib = document.bibliography
        if not bib:
            return []
        findings: list[Finding] = []
        by_paragraph = {p.index: p for p in document.body_paragraphs}
        for c in bib.citations:
            if c.form == "narrativa" or not c.raw.startswith("("):
                continue
            p = by_paragraph.get(c.paragraph_index)
            if p is None:
                continue
            text = p.text
            pos = text.find(c.raw)
            if pos < 0:
                continue
            before = text[:pos].rstrip()
            after = text[pos + len(c.raw) :]
            is_block = c.block_quote
            if is_block:
                # en bloque el punto debe ir ANTES del parentesis
                if before.endswith("."):
                    findings.append(
                        self.finding(
                            "En la cita en bloque el punto va antes del paréntesis.",
                            paragraph_index=p.index,
                            location=f"Página {c.page} (párrafo {p.index + 1})",
                            excerpt=p.excerpt(140),
                            suggestion="Mover el punto antes del paréntesis de la cita.",
                            extra={"bib_kind": "period_in_block"},
                        )
                    )
            else:
                # en cita corta el punto va DESPUES del parentesis
                if before.endswith("."):
                    findings.append(
                        self.finding(
                            "En una cita parentética corta el punto va después del paréntesis.",
                            paragraph_index=p.index,
                            location=f"Página {c.page} (párrafo {p.index + 1})",
                            excerpt=p.excerpt(140),
                            suggestion="Mover el punto después del paréntesis de la cita.",
                            extra={"bib_kind": "period_before_short_citation"},
                        )
                    )
        return findings

RULES = [
    EtAlThresholdRule(),
    BlockQuoteRule(),
    CitationPeriodRule(),
]
