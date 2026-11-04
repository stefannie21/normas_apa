from __future__ import annotations

import re

from backend.app.rules.base import Category, Finding, Rule, Severity
from backend.app.services.bibliography import author_heading, is_corporate_author
from backend.app.services.docx_parser import ParsedDocument

YEAR_RE = re.compile(r"\b(1[89]\d{2}|20\d{2})\b")
PAREN_RE = re.compile(r"\(([^()]*)\)")
# Fechas validas en APA 7 que NO son un ano de cuatro cifras:
# n.d. / s.f. (sin fecha) e 'in press' / 'en prensa'.
NO_DATE_RE = re.compile(
    r"\b(?:n\.?\s*d\.?|s\.?\s*f\.?|sin\s+fecha|in\s+press|en\s+prensa)\b",
    re.IGNORECASE,
)
CITATION_DATE_RE = re.compile(
    r"\b(?:1[89]\d{2}|20\d{2}|n\.?\s*d\.?|s\.?\s*f\.?|in\s+press|en\s+prensa)\b",
    re.IGNORECASE,
)
# Nombres tipo "Garcia" o "Garcia, J." o "Garcia & Lopez"
NAME_TOKEN = r"[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+"
SINGLE_AUTHOR_RE = re.compile(
    rf"{NAME_TOKEN}\s*(?:,\s*[A-Z]{{1,3}}\.?)?(?:\s+et\s+al\.?)?\s*(?:,|;|\d)",
)
MULTI_AUTHOR_RE = re.compile(rf"{NAME_TOKEN}(?:\s*(?:,|&|y|and)\s*{NAME_TOKEN}){{1,}}")
CITATION_LIKE_RE = re.compile(f"{SINGLE_AUTHOR_RE.pattern}|{MULTI_AUTHOR_RE.pattern}")
ET_AL_BAD_RE = re.compile(r"\bet\s?al\b(?!\.)", re.IGNORECASE)
AMP_IN_PAREN_RE = re.compile(rf"{NAME_TOKEN}\s+(?:and|y)\s+{NAME_TOKEN}")
QUOTE_CITE_RE = re.compile(r"[\"“«][^\"”»]{0,600}[\"”»]\s*\(([^()]*)\)")
# Localizadores: pagina, parrafo, capitulo, linea, seccion, marca de tiempo...
# La pagina oficial admite 'another way for the reader to locate the quotation'
# cuando la obra no tiene paginas.
LOCATOR_RE = re.compile(
    r"\b(?:pp?\.|p[áa]rr\.|parr\.|para\.|p[áa]rrafo|cap\.|cap[ií]tulo|"
    r"l[ií]nea|line|secci[oó]n|section|min\.?|timestamp)\s*\d",
    re.IGNORECASE,
)

QUOTATIONS_URL = "https://apastyle.apa.org/style-grammar-guidelines/citations/quotations"
AUTHOR_DATE_URL = (
    "https://apastyle.apa.org/style-grammar-guidelines/citations/basic-principles/author-date"
)


def _body_paragraphs(document: ParsedDocument):
    for p in document.body_paragraphs:
        if document.references_start is not None and p.index > document.references_start:
            continue
        yield p


class CitationYearRule(Rule):
    def __init__(self) -> None:
        super().__init__(
            id="CIT-001",
            name="Citas con autor y fecha",
            category=Category.CITAS,
            description="Toda cita en el texto debe incluir autor y fecha de publicación.",
            default_severity=Severity.ERROR,
            norm_source=AUTHOR_DATE_URL,
            exceptions=(
                "Obras sin fecha se citan con 'n.d.' / 's.f.'; las aceptadas para "
                "publicación con 'in press' / 'en prensa'. Ninguna de estas es "
                "una cita sin fecha."
            ),
        )

    def check(self, document: ParsedDocument) -> list[Finding]:
        findings: list[Finding] = []
        for p in _body_paragraphs(document):
            for match in PAREN_RE.finditer(p.text):
                inner = match.group(1).strip()
                if len(inner) < 5 or not CITATION_LIKE_RE.search(inner):
                    continue
                if YEAR_RE.search(inner) or NO_DATE_RE.search(inner):
                    continue
                findings.append(
                    self.finding(
                        f"Cita sin fecha de publicación: '({inner})'.",
                        paragraph_index=p.index,
                        location=f"Párrafo {p.index + 1}",
                        excerpt=p.excerpt(),
                        suggestion=(
                            "Agregar el año: (Autor, 2020). Si la obra no tiene "
                            "fecha, usar (Autor, n.d.); si está en prensa, "
                            "(Autor, in press)."
                        ),
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
            description="Usar '&' dentro del paréntesis y 'and'/'y' en el texto narrativo.",
            norm_source=AUTHOR_DATE_URL,
            exceptions=(
                "Solo se evalúan paréntesis que contienen una fecha de cita; "
                "las expresiones 'y'/'and' en nombres propios o en texto "
                "explicativo no son citas parentéticas."
            ),
        )

    def check(self, document: ParsedDocument) -> list[Finding]:
        findings: list[Finding] = []
        for p in _body_paragraphs(document):
            for match in PAREN_RE.finditer(p.text):
                inner = match.group(1).strip()
                if not AMP_IN_PAREN_RE.search(inner):
                    continue
                # Se requiere fecha de cita o que el contenido del parentesis
                # sea exclusivamente una lista de autores (ej: "Garcia and Lopez").
                is_authors_only = bool(
                    re.fullmatch(
                        rf"{NAME_TOKEN}(?:\s*(?:,|;|y|and|&)\s*{NAME_TOKEN})+",
                        inner,
                    )
                )
                if not (CITATION_DATE_RE.search(inner) or is_authors_only):
                    continue
                findings.append(
                    self.finding(
                        "Dentro de una cita parentética se usó 'and'/'y'; APA usa '&'.",
                        paragraph_index=p.index,
                        location=f"Párrafo {p.index + 1}",
                        excerpt=match.group(0),
                        suggestion="Reemplazar 'and'/'y' por '&' dentro del paréntesis.",
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
            norm_source=AUTHOR_DATE_URL,
            exceptions="La lista de referencias y las abreviaturas de otro tipo no se evalúan.",
        )

    def check(self, document: ParsedDocument) -> list[Finding]:
        findings: list[Finding] = []
        for p in _body_paragraphs(document):
            for match in ET_AL_BAD_RE.finditer(p.text):
                findings.append(
                    self.finding(
                        "'et al.' sin punto final en una cita.",
                        paragraph_index=p.index,
                        location=f"Párrafo {p.index + 1}",
                        excerpt=p.excerpt(),
                        suggestion="Escribir 'et al.' con punto al final.",
                    )
                )
                break  # un hallazgo por parrafo
        return findings


class QuotePageRule(Rule):
    """Localizador en CITAS TEXTUALES DIRECTAS, nunca en paráfrasis.

    Fuente oficial: 'For a direct quotation, always include a full citation
    ... including the page number (or other location information)'. Las citas
    parafraseadas NO exigen número de página (PEND-004).
    """

    def __init__(self) -> None:
        super().__init__(
            id="CIT-004",
            name="Citas textuales con localizador",
            category=Category.CITAS,
            description=(
                "Las citas textuales directas deben indicar página, párrafo u "
                "otro localizador que permita ubicar el fragmento."
            ),
            norm_source=f"{QUOTATIONS_URL}/page-numbers",
            exceptions=(
                "Comillas de énfasis o términos sueltos (menos de 4 palabras); "
                "citas parafraseadas; paréntesis que no contienen una cita; "
                "obras sin paginación con localizador alternativo "
                "(párr., cap., línea, sección, minuto)."
            ),
        )

    def check(self, document: ParsedDocument) -> list[Finding]:
        findings: list[Finding] = []
        for p in _body_paragraphs(document):
            for match in QUOTE_CITE_RE.finditer(p.text):
                inner = match.group(1)
                quoted = re.search(r"[\"“«]([^\"”»]*)[\"”»]", match.group(0))
                words = len((quoted.group(1) if quoted else "").split())
                # Las comillas sobre una palabra o expresion corta NO son una
                # cita textual directa: exigirles pagina seria un falso positivo.
                if words < 4:
                    continue
                if LOCATOR_RE.search(inner):
                    continue
                # Solo se evalua cuando el parentesis es realmente una cita bibliografica.
                if not CITATION_DATE_RE.search(inner) or not NAME_TOKEN_RE.search(inner):
                    continue

                # Criterio de precision normativa APA 7:
                # Comillas de 4 a 7 palabras que constituyen terminos tecnicos, conceptos
                # o comillas de enfasis (scare quotes) dentro de una oracion parafraseada.
                # Si no hay locucion de cita previa ni verbo atributivo/interno, es UNCERTAIN.
                quoted_text = quoted.group(1).strip() if quoted else ""
                intro_text = p.text[:match.start()].split(".")[-1].lower()
                has_intro = bool(re.search(r"\b(?:seg[uú]n|afirma|sostiene|se[ñn]ala|menciona|indica|dice|refiere|plantea|expresa|concluye|define)\b|:\s*$", intro_text))
                has_verb_or_clause = bool(re.search(r"\b(?:es|son|fue|fueron|era|eran|ha|han|debe|puede|establece|indica|senala|señala|afirma|concluye|demuestra|implica|considera|depende|dependen)\b", quoted_text, re.IGNORECASE))
                if 4 <= words <= 7 and not has_intro and not has_verb_or_clause and not quoted_text.endswith((".", ",", ";")):
                    findings.append(
                        self.uncertain(
                            f"Fragmento entrecomillado de {words} palabras seguido de cita: evidencia insuficiente "
                            "para distinguir si se trata de una cita directa o de un término técnico/énfasis.",
                            paragraph_index=p.index,
                            location=f"Párrafo {p.index + 1}",
                            excerpt=match.group(0),
                            suggestion="Verificar si corresponde a una cita textual (requiere p. o párr.) o solo a un concepto entrecomillado.",
                        )
                    )
                    continue

                findings.append(
                    self.finding(
                        "Cita textual directa sin localizador (p., pp., párr., "
                        "cap., línea, sección...).",
                        paragraph_index=p.index,
                        location=f"Párrafo {p.index + 1}",
                        excerpt=p.excerpt(),
                        suggestion=(
                            "Agregar 'p. X' o 'pp. X-X' (o 'párr. X', 'cap. X', "
                            "'línea X') a la cita de la cita textual."
                        ),
                    )
                )
        return findings


NAME_TOKEN_RE = re.compile(NAME_TOKEN)


class GroupAuthorAbbreviationRule(Rule):
    """La sigla de un autor corporativo se define UNA vez en el texto.

    Fuente oficial: 'Define the abbreviation for a group author only once in
    the text ... Thereafter, use the abbreviation for all mentions'.

    Solo se activa cuando hay DOBLE evidencia: (1) la sigla aparece en una
    cita parentética sin definir y (2) existe una referencia corporativa en
    el documento cuyas iniciales coinciden con esa sigla. Sin esa
    correspondencia el resultado es UNCERTAIN y no se comenta.
    """

    def __init__(self) -> None:
        super().__init__(
            id="CIT-009",
            name="Sigla institucional definida en la primera cita",
            category=Category.CITAS,
            description=(
                "La primera cita de un autor corporativo con sigla incluye el "
                "nombre completo y la sigla entre corchetes."
            ),
            norm_source=AUTHOR_DATE_URL,
            exceptions=(
                "Autores corporativos sin abreviatura; siglas que no corresponden "
                "a ninguna referencia del documento; definiciones posteriores "
                "repetidas (no se evalúan por falta de evidencia estructural)."
            ),
        )

    @staticmethod
    def _acronym(name: str) -> str:
        stop = {
            "de", "del", "la", "las", "los", "el", "y", "e", "of", "the",
            "and", "for", "in", "a", "un", "una",
        }
        words = re.findall(r"[A-Za-zÁÉÍÓÚÑ][a-záéíóúñ]+", name or "")
        return "".join(w[0].upper() for w in words if w.lower() not in stop)

    def check(self, document: ParsedDocument) -> list[Finding]:
        bib = getattr(document, "bibliography", None)
        if not bib or not bib.references:
            return []

        corporate: dict[str, str] = {}
        for r in bib.references:
            heading = author_heading(r.raw)
            if not (r.corporate or is_corporate_author(heading)):
                continue
            acronym = self._acronym(heading)
            if len(acronym) >= 2:
                corporate[acronym] = heading
        if not corporate:
            return []

        paragraphs = [p for p in _body_paragraphs(document)]
        defined: set[str] = set()
        findings: list[Finding] = []
        for p in paragraphs:
            for m in re.finditer(r"\[([A-ZÁÉÍÓÚÑ]{2,})\]", p.text):
                defined.add(m.group(1).upper())
            for m in re.finditer(
                r"\(\s*([A-ZÁÉÍÓÚÑ]{2,})\s*,\s*"
                r"(?:1[89]\d{2}|20\d{2}|n\.?\s*d\.?|s\.?\s*f\.?|in\s+press)\s*\)",
                p.text,
                re.IGNORECASE,
            ):
                acronym = m.group(1).upper()
                if acronym not in corporate or acronym in defined:
                    continue
                # La definicion puede estar en este mismo parrafo, antes de la cita.
                if re.search(rf"\[{re.escape(acronym)}\]", p.text[: m.start()]):
                    defined.add(acronym)
                    continue
                findings.append(
                    self.finding(
                        f"La sigla '{acronym}' se usa en una cita sin haberse "
                        "definido antes con el nombre completo del autor corporativo.",
                        paragraph_index=p.index,
                        location=f"Página {p.estimated_page} (párrafo {p.index + 1})",
                        excerpt=m.group(0),
                        suggestion=(
                            f"Primera cita: {corporate[acronym]} [{acronym}] (año); "
                            f"en las siguientes usar solo ({acronym}, año)."
                        ),
                        extra={
                            "bib_kind": "group_abbreviation_undefined",
                            "surname": acronym,
                            "corporate_name": corporate[acronym],
                        },
                    )
                )
        return findings


RULES = [
    CitationYearRule(),
    AmpersandRule(),
    EtAlRule(),
    QuotePageRule(),
    GroupAuthorAbbreviationRule(),
]
