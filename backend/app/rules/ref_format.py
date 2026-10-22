"""Reglas de formato de la lista de referencias que el documento de asesoria exige
y que hasta ahora no se verificaban: cursivas segun el tipo de fuente, umbral de
autores (hasta 20 / 19+...+ultimo), autor corporativo con sigla y elementos obligatorios.
"""
from __future__ import annotations

import re

from backend.app.rules.base import Category, Finding, Rule, Severity
from backend.app.services.bibliography import (
    ReferenceRecord,
    author_heading,
    is_corporate_author,
)
from backend.app.services.docx_parser import ParsedDocument

# Tipos cuya referencia lleva el TITULO en cursiva (libros, tesis, informes)
TITLE_ITALIC_TYPES = {"libro", "tesis", "informe"}
# Tipos donde solo el CONTENEDOR (revista, volumen) va en cursiva
CONTAINER_ITALIC_TYPES = {"articulo", "capitulo"}
MAX_LISTED_AUTHORS = 20


def _rec_par(r: ReferenceRecord):
    return r.paragraph_index, r


class ReferenceItalicsRule(Rule):
    """Cursiva obligatoria según el tipo de fuente."""

    def __init__(self) -> None:
        super().__init__(
            id="REF-006",
            name="Cursivas en la referencia",
            category=Category.REFERENCIAS,
            description=(
                "Libros, tesis e informes llevan el título en cursiva; artículos y "
                "capítulos llevan en cursiva el nombre de la revista o libro contenedor."
            ),
            default_severity=Severity.WARNING,
        )

    def check(self, document: ParsedDocument) -> list[Finding]:
        bib = document.bibliography
        if not bib or not bib.references:
            return []
        findings: list[Finding] = []
        for r in bib.references:
            ptype = r.type_hint
            if ptype in TITLE_ITALIC_TYPES:
                if not r.has_italics:
                    findings.append(
                        self.finding(
                            f"Referencia tipo '{ptype}': el título debe ir en cursiva.",
                            paragraph_index=r.paragraph_index,
                            location=f"Página {r.page} (Referencias)",
                            excerpt=r.raw[:160],
                            suggestion=f"Aplicar cursiva al título: {r.title[:80]}",
                            extra={"bib_kind": "missing_italics", "expected": "título", "type": ptype},
                        )
                    )
            elif ptype in CONTAINER_ITALIC_TYPES and r.container:
                if not r.has_italics:
                    findings.append(
                        self.finding(
                            f"Referencia tipo '{ptype}': el contenedor debe ir en cursiva.",
                            paragraph_index=r.paragraph_index,
                            location=f"Página {r.page} (Referencias)",
                            excerpt=r.raw[:160],
                            suggestion=f"Aplicar cursiva al contenedor: {r.container[:80]}",
                            extra={"bib_kind": "missing_italics", "expected": "contenedor", "type": ptype},
                        )
                    )
        return findings


class ReferenceAuthorsRule(Rule):
    """Umbral de autores de APA 7: hasta 20 listados; más de 20, los 19 + ... + último."""

    def __init__(self) -> None:
        super().__init__(
            id="REF-007",
            name="Número de autores en la referencia",
            category=Category.REFERENCIAS,
            description=(
                "Se listan hasta 20 autores; con más de 20 se escriben los primeros "
                "19, puntos suspensivos y el último."
            ),
            default_severity=Severity.WARNING,
        )

    def check(self, document: ParsedDocument) -> list[Finding]:
        bib = document.bibliography
        if not bib or not bib.references:
            return []
        findings: list[Finding] = []
        for r in bib.references:
            # Exime a autores institucionales/corporativos (entidades publicas,
            # organizaciones internacionales, municipios y medios de comunicacion)
            # de la exigencia del patron de persona natural ("Apellido, Inicial.")
            if (
                r.corporate
                or r.has_et_al
                or is_corporate_author(author_heading(r.raw))
                or (r.surnames and any(is_corporate_author(s) for s in r.surnames))
            ):
                continue
            # se exige confirmacion por iniciales para no contar mal autores
            if r.author_count > MAX_LISTED_AUTHORS and r.initials_count >= 10:
                findings.append(
                    self.finding(
                        f"Referencia con {r.author_count} autores; con más de 20 se "
                        f"indican los primeros 19, puntos suspensivos y el último.",
                        paragraph_index=r.paragraph_index,
                        location=f"Página {r.page} (Referencias)",
                        excerpt=r.raw[:160],
                        suggestion="Recortar a 19 autores + '...' + el último.",
                        extra={"bib_kind": "too_many_authors", "count": r.author_count},
                    )
                )
            elif r.author_count == 0 and not r.corporate:
                findings.append(
                    self.finding(
                        "Referencia sin autor reconocible.",
                        paragraph_index=r.paragraph_index,
                        location=f"Página {r.page} (Referencias)",
                        excerpt=r.raw[:160],
                        suggestion="Verificar el formato Autor (año). Título. Fuente.",
                        extra={"bib_kind": "no_author"},
                    )
                )
        return findings


class CorporateAuthorRule(Rule):
    """El autor corporativo se escribe completo y la sigla entre corchetes."""

    def __init__(self) -> None:
        super().__init__(
            id="REF-008",
            name="Autor corporativo",
            category=Category.REFERENCIAS,
            description=(
                "En la referencia, el autor corporativo es el nombre completo de la "
                "entidad; en la primera cita del texto se incluye la sigla entre corchetes."
            ),
            default_severity=Severity.INFO,
        )

    def check(self, document: ParsedDocument) -> list[Finding]:
        bib = document.bibliography
        if not bib or not bib.references:
            return []
        findings: list[Finding] = []
        abbreviations: dict[str, int] = {}
        for c in bib.citations:
            raw = c.raw or ""
            for m in re.finditer(r"\[([A-ZÁÉÍÓÚÑ]{2,})\]", raw):
                abbreviations[m.group(1)] = c.paragraph_index

        for r in bib.references:
            if not r.corporate or not r.surnames:
                continue
            name = r.surnames[0]
            # busca sigla entre corchetes dentro del nombre de la entidad
            has_brackets = bool(re.search(r"\[[A-ZÁÉÍÓÚÑ]{2,}\]", r.raw))
            if not has_brackets:
                # la sigla suele aparecer en las citas; se comprueba alli
                cited = [
                    c for c in bib.citations
                    if name.split()[0].lower() in (c.raw or "").lower()
                ]
                if not any(re.search(r"\[[A-ZÁÉÍÓÚÑ]{2,}\]", c.raw or "") for c in cited):
                    findings.append(
                        self.finding(
                            f"Autor corporativo '{name}': incluir la sigla entre corchetes "
                            "en la primera cita del texto.",
                            paragraph_index=r.paragraph_index,
                            location=f"Página {r.page} (Referencias)",
                            excerpt=r.raw[:160],
                            suggestion=f"Primera cita: {name} [SIGLA] (año).",
                            extra={"bib_kind": "corporate_acronym", "entity": name},
                        )
                    )
        return findings

RULES = [
    ReferenceItalicsRule(),
    ReferenceAuthorsRule(),
    CorporateAuthorRule(),
]
