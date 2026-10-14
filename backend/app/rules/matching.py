"""Cruce bidireccional entre citas del cuerpo y lista de referencias.

Cubre el requisito explicito del documento de asesoria: "Confirmar que toda cita
en el texto tenga su referencia al final, y que ninguna referencia sobre sin
haber sido citada".
"""
from __future__ import annotations

import re

from backend.app.rules.base import Category, Finding, Rule, Severity
from backend.app.services.bibliography import Bibliography, first_surname
from backend.app.services.docx_parser import ParsedDocument

SUG_CITA = (
    "Agregar la entrada correspondiente en la lista de Referencias, o corregir "
    "el apellido/ano en la cita para que coincida con una referencia existente."
)
SUG_REF = (
    "Citar esta fuente en el cuerpo del texto, o eliminarla de la lista de "
    "Referencias si no se utilizo en el trabajo."
)


def _similar(a: str, b: str) -> bool:
    from backend.app.services.bibliography import normalize_name

    na, nb = normalize_name(a), normalize_name(b)
    if not na or not nb:
        return False
    if na == nb:
        return True
    # coincidencias parciales: 'garcia' vs 'garcian'
    return na.startswith(nb[:4]) or nb.startswith(na[:4])


class MissingReferenceRule(Rule):
    """Citas del cuerpo sin entrada en la lista de referencias."""

    def __init__(self) -> None:
        super().__init__(
            id="CRUCE-001",
            name="Cita sin referencia",
            category=Category.CITAS,
            description=(
                "Toda cita en el texto debe tener su entrada en la lista de "
                "referencias."
            ),
            default_severity=Severity.ERROR,
        )

    def check(self, document: ParsedDocument) -> list[Finding]:
        bib: Bibliography = document.bibliography
        if bib.references_start is None:
            return []  # sin lista de referencias lo reporta REF-001
        if not bib.references:
            return []
        missing = bib.missing_references()
        findings: list[Finding] = []
        # un hallazgo por autor+ano, listando donde aparece: si un autor se cita
        # 50 veces, el problema sigue siendo uno solo
        for first in missing:
            appearances = [
                c
                for c in bib.citations
                if c.key == first.key
            ]
            pages = ", ".join(
                str(p) for p in dict.fromkeys(a.page for a in appearances)
            )
            findings.append(
                self.finding(
                    f"La cita {first.label} no tiene entrada en la lista de referencias"
                    + (f" (aparece en {len(appearances)} lugar/es)" if len(appearances) > 1 else "")
                    + ".",
                    paragraph_index=first.paragraph_index,
                    location=f"Pagina(s) {pages} (parrafo {first.paragraph_index + 1})",
                    excerpt=first.raw,
                    suggestion=SUG_CITA,
                    extra={
                        "bib_kind": "missing_reference",
                        "surname": first.surnames[0] if first.surnames else "",
                        "year": first.year,
                        "occurrences": len(appearances),
                        "pages": [a.page for a in appearances],
                    },
                )
            )
        return findings


class UncitedReferenceRule(Rule):
    """Referencias que nunca se citan en el cuerpo del documento."""

    def __init__(self) -> None:
        super().__init__(
            id="CRUCE-002",
            name="Referencia no citada",
            category=Category.REFERENCIAS,
            description="Ninguna referencia debe quedar sin citarse en el texto.",
            default_severity=Severity.WARNING,
        )

    def check(self, document: ParsedDocument) -> list[Finding]:
        bib: Bibliography = document.bibliography
        if bib.references_start is None or not bib.references:
            return []
        orphans = bib.uncited_references()
        findings: list[Finding] = []
        for r in orphans:
            findings.append(
                self.finding(
                    f"Referencia sin citar en el cuerpo: {r.label}.",
                    paragraph_index=r.paragraph_index,
                    location=f"Pagina {r.page} (Referencias)",
                    excerpt=r.raw[:160],
                    suggestion=SUG_REF,
                    extra={
                        "bib_kind": "uncited_reference",
                        "year": r.year,
                        "surnames": r.surnames,
                        "source": r.source_kind,
                    },
                )
            )
        return findings


class YearMismatchRule(Rule):
    """El ano de la cita no coincide con ninguna referencia de ese autor."""

    def __init__(self) -> None:
        super().__init__(
            id="CRUCE-003",
            name="Ano inconsistente entre cita y referencia",
            category=Category.CITAS,
            description=(
                "Cuando el autor y el ano de la cita coinciden con una referencia "
                "pero el ano difiere, suele haber un error de transcripcion."
            ),
            default_severity=Severity.WARNING,
        )

    def check(self, document: ParsedDocument) -> list[Finding]:
        bib: Bibliography = document.bibliography
        if bib.references_start is None or not bib.references:
            return []
        findings: list[Finding] = []
        seen: set[tuple[str, int, int]] = set()
        for c in bib.citations:
            if not c.surnames or c.year is None:
                continue
            same_author = [
                r for r in bib.references if r.surnames and _similar(r.surnames[0], c.surnames[0])
            ]
            if not same_author:
                continue
            if any(r.year == c.year for r in same_author):
                continue
            key = (c.surnames[0].lower(), c.year, same_author[0].year or 0)
            if key in seen:
                continue
            seen.add(key)
            available = sorted({r.year for r in same_author if r.year})
            findings.append(
                self.finding(
                    f"El ano {c.year} de la cita de {c.surnames[0]} no aparece en "
                    f"las referencias (anos disponibles: {', '.join(str(a) for a in available) or 'sin ano'}).",
                    paragraph_index=c.paragraph_index,
                    location=f"Pagina {c.page} (parrafo {c.paragraph_index + 1})",
                    excerpt=c.raw,
                    suggestion=(
                        "Verificar el ano: si es correcto, agregar la referencia "
                        f"{c.surnames[0]} ({c.year}); si no, corregir la cita al ano "
                        f"{available[0] if available else 'correcto'}."
                    ),
                    extra={
                        "bib_kind": "year_mismatch",
                        "citation_year": c.year,
                        "reference_years": available,
                        "surname": c.surnames[0],
                    },
                )
            )
        return findings

RULES = [
    MissingReferenceRule(),
    UncitedReferenceRule(),
    YearMismatchRule(),
]
