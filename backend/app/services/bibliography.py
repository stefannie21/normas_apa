"""Capa 2 - Extraccion estructurada de citas y referencias.

Convierte el texto plano del documento en registros tipados para que las reglas
puedan razonar sobre ellos sin volver a analizar el .docx en cada comprobacion.

Tipos de referencia (APA 7): articulo, libro, capitulo, tesis, informe, web, otro.
Formas de cita: parentetica, narrativa, cita en bloque.
"""
from __future__ import annotations

import difflib
import re
import unicodedata
from dataclasses import dataclass, field

from backend.app.services.docx_parser import ParsedDocument, ParagraphInfo

# ---------------------------------------------------------------- utilidades


def strip_accents(text: str) -> str:
    norm = unicodedata.normalize("NFKD", text or "")
    return "".join(c for c in norm if not unicodedata.combining(c))


def normalize_name(name: str) -> str:
    """'García J.' -> 'garcia' para comparar autores entre citas y referencias."""
    base = strip_accents(name or "").lower()
    base = re.sub(r"[^a-z0-9\s]", " ", base)
    words = base.split()
    # 'García, J.' -> se queda con el primer token que sea de al menos 2 letras
    for w in words:
        if len(w) >= 2:
            return w
    return base.strip()


def first_surname(name: str) -> str:
    """De 'Sánchez, C.' o 'Sánchez C.' toma el apellido."""
    clean = strip_accents(name or "").strip()
    if not clean:
        return ""
    if "," in clean:
        return clean.split(",")[0].strip()
    parts = clean.split()
    if len(parts) >= 2 and len(parts[-1]) <= 3 and parts[-1].replace(".", "").isalpha():
        return parts[0].strip()
    return parts[0].strip()


INITIAL_TAIL_RE = re.compile(r"(?:^|,\s*|\s)([A-ZÁÉÍÓÚÑ])\.?\s*$")


# Particulas y conectores que no identifican a un autor: 'De la Garza' y
# 'Garza' deben compararse igual, y 'Organisation for Economic...' no debe
# contar 'for'. Las iniciales de una letra tampoco cuentan como apellido.
AUTHOR_STOPWORDS = {
    "de", "del", "la", "las", "los", "el", "y", "e", "and", "for", "para",
    "da", "das", "do", "dos", "van", "von", "der", "den", "di", "du", "le",
    "ter", "ten", "the", "of", "en",
    # conectores con los que suele empezar una cita narrativa
    "segun", "cuando", "mientras", "aunque", "pero", "ademas", "tambien",
    "sobre", "entre", "desde", "hasta", "como", "con", "sin", "tras", "ante",
    "bajo", "contra", "su", "sus", "este", "esta", "estos", "estas",
    "dicho", "dicha", "dichos", "dichas", "autor", "autora", "autores",
    "autoras", "teoria", "informe", "estudio", "caso",
}


def author_tokens(text: str) -> list[str]:
    """Palabras significativas de un bloque de autoria, normalizadas."""
    norm = strip_accents(text or "").lower()
    norm = re.sub(r"[^a-z0-9 ]+", " ", norm)
    return [w for w in norm.split() if len(w) > 1 and w not in AUTHOR_STOPWORDS]


def author_heading(raw: str) -> str:
    """Tramo de autoria de una referencia: lo que va antes del anio."""
    m = re.match(
        r"^(.*?)\s*\(\s*(?:[^()]*?(?:1[5-9]\d{2}|20\d{2}|s\.?f\.?)[^()]*?)\s*\)",
        raw or "",
    )
    return (m.group(1) if m else (raw or "")).strip(" .,;")


def acronym_of(text: str) -> str:
    """Siglas del nombre: 'Organizacion Mundial de la Salud' -> 'OMS'.

    Las particulas ('de', 'para', 'y') no aportan sigla y en las palabras con
    guion solo cuenta la primera parte ('Co-operation' -> 'C'), de modo que
    'Organisation for Economic Co-operation and Development' da 'OECD'.
    """
    words = re.findall(r"[A-Za-zÁÉÍÓÚÑÜáéíóúñü]+(?:-[A-Za-zÁÉÍÓÚÑÜáéíóúñü]+)*", text or "")
    if len(words) == 1:
        return words[0].upper()
    out = []
    for w in words:
        if w.lower() in AUTHOR_STOPWORDS:
            continue
        out.append(w.split("-")[0][0])
    return "".join(out).upper()


def _tokens_match(cit: list[str], ref: list[str]) -> bool:
    """El bloque citado encaja en el bloque de la referencia."""
    if not cit or not ref:
        return False
    if cit == ref:
        return True
    joined = " ".join(ref)
    text = " ".join(cit)
    # tramo contiguo en cualquiera de las dos direcciones
    if re.search(rf"(?<![a-z0-9]){re.escape(text)}(?![a-z0-9])", joined):
        return True
    if re.search(rf"(?<![a-z0-9]){re.escape(joined)}(?![a-z0-9])", text):
        return True
    # mismos apellidos en otro orden o con uno de mas (en cualquier direccion:
    # 'Trujillo Valencia' debe encontrar 'Trujillo', y 'Frias' debe encontrar
    # 'Estrada Frias')
    if set(cit) <= set(ref) or set(ref) <= set(cit):
        return True
    # errata de una letra: 'Garcian' frente a 'Garcia'
    return difflib.SequenceMatcher(None, text, joined).ratio() >= 0.86


def author_matches(citation: list[str], reference: "ReferenceRecord") -> bool:
    """True si la cita corresponde al bloque de autoria de la referencia.

    Compara los apellidos sin iniciales ni particulas y acepta el bloque exacto
    ('Estrada Frias'), un tramo contiguo ('Frias' dentro de 'Estrada Frias'),
    los mismos apellidos en otro orden, una errata de una letra y las siglas de
    una entidad ('SUNAT', 'OCDE').
    """
    who = " ".join(s for s in citation if s).strip()
    if not who:
        return False
    heading = author_heading(reference.raw)
    cit = author_tokens(who)
    ref = author_tokens(heading)
    if _tokens_match(cit, ref):
        return True
    # siglas: 'SUNAT' aparece en la entrada aunque el encabezado sea el nombre
    # completo de la entidad
    compact = re.sub(r"[^A-Za-zÁÉÍÓÚÑÜáéíóúñü]", "", who)
    if compact.isupper() and 2 <= len(compact) <= 12:
        if re.search(rf"\b{re.escape(compact)}\b", reference.raw):
            return True
    # siglas equivalentes: 'OCDE' frente a 'Organisation for Economic...'
    acr = acronym_of(who)
    ref_acr = acronym_of(heading)
    if len(acr) >= 3 and ref_acr and (
        acr == ref_acr or sorted(acr) == sorted(ref_acr)
    ):
        return True
    return False


def citation_surname(entry: str) -> str:
    """Apellido o bloque de apellidos de una cita.

    'Estrada Frias' -> 'Estrada Frias' (apellido compuesto, no solo 'Estrada');
    'Garcia, J.' -> 'Garcia' (las iniciales no forman parte del apellido).
    """
    clean = (entry or "").strip(" .,;")
    if not clean:
        return ""
    if "," in clean:
        head, tail = clean.split(",", 1)
        tail = tail.strip()
        if not tail or not _starts_with_initial(tail):
            # la cola no son iniciales: apellido compuesto o entidad corporativa
            return clean
        return head.strip()
    return clean



def name_initials(name: str) -> list[str]:
    """Iniciales declaradas: 'Sánchez, C. M.' -> ['C','M']."""
    if "," in name:
        tail = name.split(",", 1)[1]
        found = re.findall(r"\b([A-ZÁÉÍÓÚÑ])\.", tail)
        if found:
            return found
    return [m.group(1) for m in INITIAL_TAIL_RE.finditer(name or "")]


def has_initials(name: str) -> bool:
    return bool(INITIAL_TAIL_RE.search((name or "").strip()))


def is_corporate_author(name: str) -> bool:
    """Un autor corporativo no tiene iniciales y suele acabar en inc tipo de entidad."""
    clean = name.strip()
    if not clean:
        return False
    if has_initials(clean):
        return False
    corporate_tail = (
        r"(?i)\b(universidad|organizaci[oó]n|instituto|ministerio|agencia|comisi[oó]n|"
        r"asociaci[oó]n|empresa|sociedad|consejo|fundaci[oó]n|centro|colegio|gobierno|"
        r"hospital|museo|banco|corporaci[oó]n)\b"
    )
    return bool(re.search(corporate_tail, strip_accents(clean)))


# ---------------------------------------------------------------- registros


@dataclass
class CitationRecord:
    """Una cita detectada en el cuerpo del documento."""

    paragraph_index: int
    page: int
    raw: str
    surnames: list[str]
    year: int | None
    form: str  # "parentetica" | "narrativa" | "bloque"
    has_et_al: bool = False
    has_locator: bool = False  # p. / pp. / párr.
    locator_text: str = ""
    quoted: bool = False
    word_count: int = 0
    block_quote: bool = False
    ends_with_period_before_paren: bool = False

    @property
    def key(self) -> tuple:
        return (self.surnames[0].lower() if self.surnames else "", self.year)

    @property
    def label(self) -> str:
        if self.form == "narrativa":
            who = " y ".join(self.surnames) or "?"
            return f"{who} ({self.year if self.year else 's/f'})"
        return self.raw


@dataclass
class ReferenceRecord:
    """Una entrada de la lista de referencias."""

    paragraph_index: int
    page: int
    raw: str
    surnames: list[str]
    year: int | None
    author_count: int
    has_et_al: bool = False
    corporate: bool = False
    initials: list[str] = field(default_factory=list)
    title: str = ""
    container: str = ""
    source_kind: str = ""
    doi: str = ""
    url: str = ""
    has_italics: bool = False
    italic_texts: list[str] = field(default_factory=list)
    type_hint: str = ""  # articulo | libro | capitulo | tesis | informe | web | otro
    initials_count: int = 0  # autores con iniciales: confirma que el conteo es fiable

    @property
    def key(self) -> tuple:
        return (self.surnames[0].lower() if self.surnames else "", self.year)

    @property
    def label(self) -> str:
        who = self.surnames[0] if self.surnames else "(sin autor)"
        return f"{who} ({self.year if self.year else 's/f'})"


@dataclass
class Bibliography:
    citations: list[CitationRecord] = field(default_factory=list)
    references: list[ReferenceRecord] = field(default_factory=list)
    references_start: int | None = None

    def citation_pages(self) -> list[CitationRecord]:
        return self.citations

    def uncited_references(self) -> list[ReferenceRecord]:
        """Referencias que nunca aparecen citadas en el cuerpo."""
        seen: set[tuple] = set()
        out = []
        for r in self.references:
            if not r.surnames or not r.surnames[0]:
                continue
            if r.key in seen:
                continue
            seen.add(r.key)
            cited = any(
                (c.year == r.year or r.year is None) and author_matches(c.surnames, r)
                for c in self.citations
            )
            if not cited:
                out.append(r)
        return out

    def missing_references(self) -> list[CitationRecord]:
        """Citas del cuerpo que no tienen entrada en la lista de referencias.

        La comparacion es por bloque de apellidos (no por el primer token), de
        modo que 'Estrada Frias', 'Taminchi Pilco' o 'De la Garza' encuentran su
        entrada aunque la cita venga recortada a 'Frias' o 'Garza'. Se devuelve
        una entrada por autor+ano distintos: si un autor se cita cien veces, el
        problema es uno solo y no debe generar cien hallazgos.
        """
        unique: list[CitationRecord] = []
        for c in self.citations:
            if not c.surnames:
                continue
            if any(
                author_matches(c.surnames, r)
                for r in self.references
            ):
                continue
            # la misma cita puede detectarse dos veces (narrativa y parentetica)
            if any(
                u.year == c.year
                and u.surnames
                and u.surnames[0].lower() == c.surnames[0].lower()
                and "_".join(u.surnames).lower() == "_".join(c.surnames).lower()
                for u in unique
            ):
                continue
            unique.append(c)
        return unique


# ---------------------------------------------------------------- extraccion

YEAR_RE = re.compile(r"(1[5-9]\d{2}|20\d{2})")
LOCATOR_RE = re.compile(r"\b(p{1,2}\.\s*\d+[\-–]?\d*|p[aá]rr?\.\s*\d+)", re.IGNORECASE)
ET_AL_RE = re.compile(r"\bet\s?al\.?", re.IGNORECASE)
PAREN_RE = re.compile(r"\(([^()]{2,120})\)")
# "García (2020)", "Según García y López (2020)" o "Estrada Frías (2023)".
# Se admiten hasta cuatro palabras capitalizadas seguidas para no cortar los
# apellidos compuestos ni el nombre de una entidad.
NARRATIVE_RE = re.compile(
    r"((?:[A-ZÁÉÍÓÚÑ][\wÁÉÍÓÚÑáéíóúñ'\-]+\s+){0,3}"
    r"[A-ZÁÉÍÓÚÑ][\wÁÉÍÓÚÑáéíóúñ'\-]+"
    r"(?:\s*(?:,|&|y|and)\s*[A-ZÁÉÍÓÚÑ][\wÁÉÍÓÚÑáéíóúñ'\-]+)*)"
    r"\s*(?:\([^)]*?)?\s*\((1[5-9]\d{2}|20\d{2}|s\.?f\.?)\)"
)
# Conectores que se descartan del inicio del bloque narrativo ("Según Pérez").
NARRATIVE_LEAD_RE = re.compile(
    r"^(?:segun|cuando|mientras|aunque|pero|ademas|tambien|respecto|"
    r"para|por|como|desde|hasta|entre|sobre|tras|ante|bajo|contra)\s+",
    re.IGNORECASE,
)
AUTHOR_SPLIT_RE = re.compile(r"\s*(?:&|\band\b\s+|\by\b\s+|;)\s*")
ET_AL_MIDDLE_RE = re.compile(r"\.\.\.|\bet\s+al\b", re.IGNORECASE)


def _split_authors(block: str) -> list[str]:
    """Divide el bloque de autores en entradas individuales.

    'Ramos, L., Soto, M., y Vega, P.' -> ['Ramos, L.', 'Soto, M.', 'Vega, P.']
    'Zapata, R.'                     -> ['Zapata, R.']
    'Sanchez Perez, Juan y Lopez, Maria' -> 2 autores
    """
    block = re.sub(r"\.\.\.", ",", block)
    block = ET_AL_MIDDLE_RE.sub(",", block)

    # normaliza 'y'/'&' finales antes de una coma: 'Vega, P., y ' -> coma simple
    block = re.sub(r"(?:,|\s)*(?:&|\band\b|\by\b)\s*", ",", block)

    tokens = [t.strip(" .,;") for t in block.split(",")]
    authors: list[str] = []
    i = 0
    while i < len(tokens):
        token = tokens[i]
        if not token:
            i += 1
            continue
        if _looks_like_surname(token):
            # despues de un apellido pueden venir iniciales sueltas: 'Ramos, L.'
            initials: list[str] = []
            j = i + 1
            while j < len(tokens) and (
                not _looks_like_surname(tokens[j]) or _starts_with_initial(tokens[j])
            ):
                initials.append(tokens[j])
                j += 1
            authors.append(token + (", " + ", ".join(initials) if initials else ""))
            i = j
        else:
            # token suelto sin apellido delante: nombre suelto o inicial
            if i + 1 < len(tokens) and not _looks_like_surname(tokens[i + 1]):
                authors.append(token + ", " + tokens[i + 1])
                i += 2
            elif i + 1 < len(tokens) and tokens[i + 1] and _is_spain_format_pair(token, tokens[i + 1]):
                # 'Sanchez Perez' + 'Juan': dos apellidos seguidos (formato espanol)
                authors.append(token + " " + tokens[i + 1])
                i += 2
            else:
                authors.append(token)
                i += 1
    return authors


def _is_spain_format_pair(first: str, second: str) -> bool:
    """'Sanchez Perez' + 'Juan': dos palabras largas sin iniciales.

    En APA el apellido precede a las iniciales; cuando hay dos palabras seguidas
    ('Sanchez Perez, Juan') es el formato espanol, no dos autores distintos.
    """
    if has_initials(first) or has_initials(second):
        return False
    a, b = first.split(), second.split()
    if len(a) < 2 or len(b) != 1:
        return False
    return all(len(w) > 2 for w in a)


def _starts_with_initial(token: str) -> bool:
    """'L. A.', 'S. de los A.' o 'A. del J.' empiezan por una inicial."""
    t = (token or "").strip()
    if not t:
        return False
    # inicial con punto: 'L.', 'S. de los A.'
    if re.match(r"^[A-ZÁÉÍÓÚÑ]\.", t):
        return True
    # inicial suelta sin punto (el parser quita los puntos al tokenizar): 'L', 'S'
    if re.fullmatch(r"[A-ZÁÉÍÓÚÑ]", t):
        return True
    return False


def _looks_like_surname(token: str) -> bool:
    """Un apellido empieza por mayuscula y no es solo una inicial."""
    t = token.strip()
    if not t:
        return False
    if re.fullmatch(r"[A-ZÁÉÍÓÚÑ]\.?", t):
        return False  # es una inicial
    # 'L. A.' o 'J. J.' son las iniciales del autor anterior, no un apellido:
    # contarlas como autor hacia que 'Clark, L. A., y Watson, D.' pareciera una
    # obra de tres autores y se exigiera 'et al.' en una cita de dos.
    if re.fullmatch(r"(?:[A-ZÁÉÍÓÚÑ]\.?\s*)+", t):
        return False
    return bool(re.match(r"[A-ZÁÉÍÓÚÑ]", t))


def _title_and_container(after_date: str) -> tuple[str, str]:
    """Tras '(año).' viene 'Título. Contenedor, volumen(issue), páginas.'"""
    body = after_date.strip()
    body = re.sub(r"^[.,;:\s]+", "", body)
    if not body:
        return "", ""
    parts = re.split(r"(?<=[a-záéíóúñ0-9\)\]\.])\.\s+", body, maxsplit=1)
    title = parts[0].strip(" .")
    container = parts[1].strip(" .") if len(parts) > 1 else ""
    return title, container


def _source_kind(container: str) -> str:
    c = container.lower()
    if re.search(r"\bhttps?://|doi\.org", c):
        return "web"
    if re.search(r"\(\s*\d+\s*(?:,\s*\d+\s*)?\)", c) or re.search(r",\s*\d+\s*(?:,|\.|$)", c):
        return "articulo"
    if re.search(r"\b(ed\.|editor|ediciones|editorial|press|publisher)\b", c):
        return "libro"
    return ""


def parse_reference(paragraph: ParagraphInfo) -> ReferenceRecord:
    text = paragraph.text.strip()
    italic_texts = [r.text.strip() for r in paragraph.runs if r.italic and r.text.strip()]
    has_italics = bool(italic_texts)

    # El corte correcto es el parentesis DEL ANIO: el autor corporativo puede
    # llevar la sigla antes, p. ej. 'Universidad Cesar Vallejo (UCV). (2024).
    # Titulo. Fuente.' Cortar en el primero hacia '(UCV)' y el titulo acababa
    # siendo '(2024)', que es lo que despues se ponía en cursiva.
    date_pat = r"(?P<date>[^)]*(?:1[89]\d{2}|20\d{2}|s/?f)[^)]*)"
    m = re.match(rf"^(?P<authors>.+?)\s*\({date_pat}\)\.?\s*(?P<rest>.*)$", text, re.S)
    if not m:
        # sin anio reconocible se corta como antes, para no perder la referencia
        m = re.match(r"^(?P<authors>.+?)\s*\((?P<date>[^)]*)\)\.?\s*(?P<rest>.*)$", text, re.S)
    if not m:
        return ReferenceRecord(
            paragraph_index=paragraph.index,
            page=paragraph.estimated_page,
            raw=text,
            surnames=[],
            year=None,
            author_count=0,
            title=text,
            has_italics=has_italics,
            italic_texts=italic_texts,
        )

    authors_block = m.group("authors").strip(" .,;")
    date_block = m.group("date").strip()
    rest = m.group("rest")

    year_match = YEAR_RE.search(date_block)
    year = int(year_match.group(1)) if year_match else None

    has_et_al = bool(ET_AL_RE.search(authors_block))
    authors_raw = _split_authors(authors_block)
    surnames = [citation_surname(a) for a in authors_raw]
    surnames = [s for s in surnames if s]

    corporate = is_corporate_author(authors_block) and not has_initials(authors_block)

    title, container = _title_and_container(rest)
    doi_match = re.search(r"(?:doi\.org/|doi:\s*)(10\.\d{4,9}/[^\s]+)", rest, re.IGNORECASE)
    url_match = re.search(r"https?://[^\s]+", rest)

    rec = ReferenceRecord(
        paragraph_index=paragraph.index,
        page=paragraph.estimated_page,
        raw=text,
        surnames=surnames,
        year=year,
        author_count=len(authors_raw),
        has_et_al=has_et_al,
        corporate=corporate,
        initials=name_initials(authors_raw[0]) if authors_raw else [],
        title=title,
        container=container,
        source_kind=_source_kind(rest),
        doi=doi_match.group(1).rstrip(".") if doi_match else "",
        url=url_match.group(0).rstrip(".") if url_match else "",
        has_italics=has_italics,
        italic_texts=italic_texts,
        initials_count=sum(1 for a in authors_raw if has_initials(a)),
    )
    rec.type_hint = infer_reference_type(rec, title, container, rest)
    return rec


def infer_reference_type(rec: ReferenceRecord, title: str, container: str, rest: str) -> str:
    """Clasificacion tipica (la IA afinara estos casos ambiguos en la fase 3)."""
    low = strip_accents(f"{title} {container} {rest}").lower()
    if re.search(r"\b(tesis|thesis|disertacion|doctorado|maestria|licenciatura)\b", low):
        return "tesis"
    if re.search(r"\b(informe|report|serie|boletin)\b", low) and not container:
        return "informe"
    if rec.doi or re.search(r"https?://", rest or ""):
        if re.search(r"\b(revista|journal|revista|journal of|bulletin)\b", low):
            return "articulo"
        return "web"
    if re.search(r"\(\s*\d+\s*(?:,\s*\d+\s*)?\)\s*,?\s*\d+", low) or re.search(r"\d+\s*[-–]\s*\d+\s*$", low.strip()):
        return "articulo"
    if re.search(r"\b(en|editorial|ediciones|press|publishing|s\.a\.|s\.l\.)\b", low):
        return "libro"
    if re.search(r"\b(cap[ií]tulo|chapter|in|segun)\b", low) and re.search(r"\(\d+ed\.\)|edici", low):
        return "capitulo"
    return "otro" if not container else "libro"


def extract_citations(paragraphs: list[ParagraphInfo]) -> list[CitationRecord]:
    out: list[CitationRecord] = []
    ref_start = None  # se rellena fuera

    for p in paragraphs:
        if p.is_empty:
            continue
        text = p.text
        # citas en bloque: sangria marcada y texto largo
        is_block = (
            p.left_indent_in is not None
            and p.left_indent_in >= 0.4
            and len(text.split()) >= 40
            and '"' not in text
            and not PAREN_RE.search(text.split("(")[0] if "(" in text else text)
        )

        # parenteticas
        for match in PAREN_RE.finditer(text):
            inner = match.group(1).strip()
            if len(inner) < 4:
                continue
            if not (YEAR_RE.search(inner) or re.search(r"\bs\.?f\.?\b", inner, re.I)):
                continue
            if not re.match(r"^[A-ZÁÉÍÓÚÑ(\s]", inner) and not re.match(r"^\(", inner):
                continue
            loc = LOCATOR_RE.search(inner)
            # un parentesis puede contener varias citas separadas por ';'
            segments = [s.strip() for s in re.split(r"\s*;\s*", inner) if s.strip()]
            if len(segments) <= 1:
                segments = [inner]
            for seg in segments:
                if not (YEAR_RE.search(seg) or re.search(r"\bs\.?f\.?\b", seg, re.I)):
                    continue
                surnames = [
                    citation_surname(s)
                    for s in _split_authors(re.sub(r"\d.*$", "", seg).strip(" ,;"))
                ]
                surnames = [s for s in surnames if s]
                if not surnames:
                    continue
                year_match = YEAR_RE.search(seg)
                out.append(
                    CitationRecord(
                        paragraph_index=p.index,
                        page=p.estimated_page,
                        raw=f"({seg})",
                        surnames=surnames,
                        year=int(year_match.group(1)) if year_match else None,
                        form="bloque" if is_block else "parentetica",
                        has_et_al=bool(ET_AL_RE.search(seg)),
                        has_locator=bool(loc),
                        locator_text=loc.group(1) if loc else "",
                        word_count=len(text.split()),
                        block_quote=is_block,
                    )
                )

        # narrativas: 'García (2020)'
        for match in NARRATIVE_RE.finditer(text):
            block = match.group(1).strip()
            # descarta el conector con el que empieza la frase ("Según X")
            block = NARRATIVE_LEAD_RE.sub("", block)
            surnames = [citation_surname(s) for s in _split_authors(block)]
            surnames = [s for s in surnames if s]
            if not surnames:
                continue
            year = match.group(2)
            year_val = int(year) if year.isdigit() else None
            # evita duplicar si ya se capturo como parentetica identica
            dup = any(
                c.paragraph_index == p.index
                and c.year == year_val
                and c.surnames[:1] == surnames[:1]
                for c in out
            )
            if dup:
                continue
            loc = LOCATOR_RE.search(text[match.end() : match.end() + 30])
            out.append(
                CitationRecord(
                    paragraph_index=p.index,
                    page=p.estimated_page,
                    raw=match.group(0),
                    surnames=surnames,
                    year=year_val,
                    form="narrativa",
                    has_et_al=bool(ET_AL_RE.search(match.group(1))),
                    has_locator=bool(loc),
                    locator_text=loc.group(1) if loc else "",
                    word_count=len(text.split()),
                    block_quote=is_block,
                )
            )
    return out


def build_bibliography(document: ParsedDocument) -> Bibliography:
    """Punto de entrada: extrae citas del cuerpo y referencias de la lista."""
    ref_start = document.references_start
    body = [p for p in document.paragraphs if not p.is_empty]
    body_before_refs = [p for p in body if ref_start is None or p.index <= ref_start]

    citations = extract_citations(body_before_refs)

    # solo el tramo de la lista: `reference_paragraphs()` ya corta en el
    # siguiente encabezado / 'Anexos', y aqui se seguia hasta el final del
    # documento. Los anexos (tablas de numeros, fichas, matrices) se parseaban
    # como si fueran referencias y generaban cientos de avisos REF-006/007/008
    # sobre contenido que no es ninguna referencia.
    references: list[ReferenceRecord] = []
    for p in document.reference_paragraphs():
        rec = parse_reference(p)
        if rec.raw.strip():
            references.append(rec)

    return Bibliography(
        citations=citations, references=references, references_start=ref_start
    )