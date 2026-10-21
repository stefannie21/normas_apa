from __future__ import annotations

import re
from dataclasses import dataclass, field
from io import BytesIO
from typing import Iterable

from docx import Document
from docx.document import Document as DocxDocument
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Length
from docx.text.paragraph import Paragraph

W_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
# <wp:extent> guarda el tamaño con el que el autor colocó la imagen.
WP_NS = "{http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing}"
# Las copias de reserva de mc:AlternateContent repiten el mismo dibujo: si se
# leyeran, cada imagen saldría duplicada.
MC_FALLBACK_NS = "{http://schemas.openxmlformats.org/markup-compatibility/2006}Fallback"
EMU_PER_CM = 360000.0

# Tamano de pagina por defecto: A4 (21 x 29.7 cm). Se usa solo cuando el .docx
# no declara w:pgSz. Antes caia en Carta (8.5 x 11 in), que no es el papel
# habitual de las tesis.
DEFAULT_PAGE_W_IN = 8.268
DEFAULT_PAGE_H_IN = 11.693


@dataclass
class RunInfo:
    text: str
    font_name: str | None
    font_size_pt: float | None
    bold: bool
    italic: bool
    underline: bool
    all_caps: bool = False
    small_caps: bool = False
    is_vertical: bool = False  # super/subindice: no es cuerpo de texto


@dataclass
class ParagraphInfo:
    index: int
    text: str
    style_name: str
    alignment: str | None
    line_spacing: float | None
    space_before_pt: float | None
    space_after_pt: float | None
    first_line_indent_in: float | None
    left_indent_in: float | None
    runs: list[RunInfo] = field(default_factory=list)
    heading_level: int | None = None
    is_list_item: bool = False
    is_empty: bool = False
    has_page_break: bool = False
    estimated_page: int = 1
    section_index: int = 0
    in_table: bool = False

    @property
    def fonts(self) -> set[str]:
        return {r.font_name for r in self.runs if r.font_name}

    @property
    def sizes(self) -> set[float]:
        return {round(r.font_size_pt, 1) for r in self.runs if r.font_size_pt is not None}

    @property
    def all_bold(self) -> bool:
        runs = [r for r in self.runs if r.text.strip()]
        return bool(runs) and all(r.bold for r in runs)

    @property
    def max_size_pt(self) -> float | None:
        values = [r.font_size_pt for r in self.runs if r.font_size_pt is not None and r.text.strip()]
        return max(values) if values else None

    def excerpt(self, n: int = 120) -> str:
        return (self.text[:n] + "...") if len(self.text) > n else self.text


@dataclass
class SectionInfo:
    index: int
    top_margin_in: float | None
    bottom_margin_in: float | None
    left_margin_in: float | None
    right_margin_in: float | None
    page_width_in: float | None
    page_height_in: float | None


@dataclass
class TableInfo:
    index: int
    caption_paragraph_index: int | None = None
    caption_text: str = ""
    has_caption_number: bool = False
    title_italic: bool = False
    has_header_row: bool = False
    has_vertical_borders: bool = False
    has_horizontal_borders: bool = False
    cell_font_consistent: bool = True
    cell_font_name: str | None = None
    cell_font_size_pt: float | None = None
    mentioned_in_text: bool = False
    rows: int = 0
    cols: int = 0


@dataclass
class ParsedDocument:
    filename: str
    paragraphs: list[ParagraphInfo]
    sections: list[SectionInfo]
    default_font: str | None
    default_font_size_pt: float | None
    references_start: int | None = None
    bibliography: object | None = None
    tables: list[TableInfo] = field(default_factory=list)

    @property
    def body_paragraphs(self) -> list[ParagraphInfo]:
        return [p for p in self.paragraphs if not p.is_empty]

    def reference_paragraphs(self) -> list[ParagraphInfo]:
        """Parrafos de la lista de referencias (solo el tramo real).

        Va desde el encabezado de 'Referencias' hasta el siguiente encabezado o
        hasta 'Anexos' / 'Apéndices'. Antes se tomaba TODO lo que venia despues
        del titulo, y en las tesis los anexos (y sus tablas de numeros) van
        detras de las referencias: se colaban generando avisos REF-002/004/007
        sobre contenido que no es ninguna referencia.
        """
        if self.references_start is None:
            return []
        out: list[ParagraphInfo] = []
        for p in self.paragraphs[self.references_start + 1 :]:
            if p.is_empty:
                continue
            if _is_references_end(p):
                break
            out.append(p)
        return out

    def iter_text_indexed(self) -> Iterable[tuple[int, str]]:
        for p in self.paragraphs:
            if not p.is_empty:
                yield p.index, p.text


HEADING_STYLES = {
    "heading 1": 1,
    "heading 2": 2,
    "heading 3": 3,
    "heading 4": 4,
    "heading 5": 5,
    "titulo 1": 1,
    "titulo 2": 2,
    "titulo 3": 3,
    "titulo 4": 4,
    "titulo 5": 5,
    "título 1": 1,
    "título 2": 2,
    "título 3": 3,
    "título 4": 4,
    "título 5": 5,
}

REFERENCES_HEADINGS = {
    "referencias",
    "referencias bibliograficas",
    "referencias bibliográficas",
    "bibliografia",
    "bibliografía",
    "references",
    "lista de referencias",
}


def _pt(value) -> float | None:
    if value is None:
        return None
    if isinstance(value, Length):
        return round(value.pt, 2)
    try:
        return round(float(value), 2)
    except (TypeError, ValueError):
        return None


def _inches(value) -> float | None:
    if value is None:
        return None
    if isinstance(value, Length):
        return round(value.inches, 3)
    return None


def _alignment_name(paragraph) -> str | None:
    alignment = paragraph.paragraph_format.alignment
    if alignment is None:
        try:
            alignment = paragraph.style.paragraph_format.alignment
        except Exception:
            alignment = None
    if alignment is None:
        return None
    mapping = {
        WD_ALIGN_PARAGRAPH.LEFT: "left",
        WD_ALIGN_PARAGRAPH.CENTER: "center",
        WD_ALIGN_PARAGRAPH.RIGHT: "right",
        WD_ALIGN_PARAGRAPH.JUSTIFY: "justify",
        WD_ALIGN_PARAGRAPH.DISTRIBUTE: "justify",
    }
    # Word admite mas variantes de justificado; todas equivalen a "justify"
    for name in dir(WD_ALIGN_PARAGRAPH):
        if name.startswith("JUSTIFY") or name == "THAI_JUSTIFY":
            value = getattr(WD_ALIGN_PARAGRAPH, name)
            mapping.setdefault(value, "justify")
    return mapping.get(alignment, "left")


def _line_spacing(paragraph) -> float | None:
    pf = paragraph.paragraph_format
    value = pf.line_spacing
    if value is None:
        try:
            value = paragraph.style.paragraph_format.line_spacing
        except Exception:
            value = None
    if value is None:
        return None
    if isinstance(value, Length):
        # Fixed line spacing expressed as a length -> approximate multiple.
        try:
            return round(value.pt / 12.0, 2)
        except Exception:
            return None
    try:
        return round(float(value), 2)
    except (TypeError, ValueError):
        return None


def _inherited(pf_value, style_value):
    return pf_value if pf_value is not None else style_value


def _heading_level(style_name: str, text: str, runs: list[RunInfo]) -> int | None:
    key = (style_name or "").strip().lower()
    if key in HEADING_STYLES:
        return HEADING_STYLES[key]
    if key.startswith("heading "):
        digits = re.findall(r"\d", key)
        if digits:
            return int(digits[0])
    return None


def _is_list_item(paragraph) -> bool:
    style = (paragraph.style.name or "").lower()
    if "list" in style or "lista" in style:
        return True
    ppr = paragraph._p.pPr
    if ppr is not None and (ppr.find(".//{*}numPr") is not None):
        return True
    return False


def _runs(paragraph) -> list[RunInfo]:
    # valores heredados del estilo del parrafo (Word los aplica si el run no los define)
    try:
        style_font = paragraph.style.font
        style_bold = style_font.bold
        style_italic = style_font.italic
        style_underline = style_font.underline
        style_caps = bool(getattr(style_font, "all_caps", False))
        style_small_caps = bool(getattr(style_font, "small_caps", False))
    except Exception:
        style_bold = style_italic = style_underline = None
        style_caps = style_small_caps = False

    out: list[RunInfo] = []
    for run in paragraph.runs:
        font = run.font
        name = font.name
        if name is None:
            try:
                name = paragraph.style.font.name
            except Exception:
                name = None
        size = font.size
        if size is None:
            try:
                size = paragraph.style.font.size
            except Exception:
                size = None
        bold = font.bold
        if bold is None:
            bold = style_bold
        italic = font.italic
        if italic is None:
            italic = style_italic
        underline = font.underline
        if underline is None:
            underline = style_underline
        all_caps = getattr(font, "all_caps", None)
        if all_caps is None:
            all_caps = style_caps
        small_caps = getattr(font, "small_caps", None)
        if small_caps is None:
            small_caps = style_small_caps
        out.append(
            RunInfo(
                text=run.text,
                font_name=name,
                font_size_pt=_pt(size),
                bold=bool(bold),
                italic=bool(italic),
                underline=bool(underline),
                all_caps=bool(all_caps),
                small_caps=bool(small_caps),
                is_vertical=bool(getattr(font, "subscript", False))
                or bool(getattr(font, "superscript", False)),
            )
        )
    return out


def _has_page_break(paragraph) -> bool:
    """True si el parrafo contiene un salto de pagina manual."""
    try:
        ppr = paragraph._p.pPr
        if ppr is not None and ppr.find(".//{*}pageBreakBefore") is not None:
            return True
        for br in paragraph._p.iter("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}br"):
            if br.get("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}type") == "page":
                return True
    except Exception:
        return False
    return False


def _estimate_pages(
    paragraphs: list[ParagraphInfo], sections: list[SectionInfo]
) -> None:
    """Asigna una pagina estimada a cada parrafo (ubicacion aproximada en el informe).

    Usa la geometria de la seccion a la que pertenece cada parrafo, de modo que las
    paginas apaisadas se contabilizan con su alto real.
    """
    geoms: list[tuple[float, float]] = []
    for s in sections:
        pw = s.page_width_in or DEFAULT_PAGE_W_IN
        ph = s.page_height_in or DEFAULT_PAGE_H_IN
        top = s.top_margin_in if s.top_margin_in is not None else 1.0
        bottom = s.bottom_margin_in if s.bottom_margin_in is not None else 1.0
        left = s.left_margin_in if s.left_margin_in is not None else 1.0
        right = s.right_margin_in if s.right_margin_in is not None else 1.0
        if pw > ph and (top, bottom, left, right) == (1.0, 1.0, 1.0, 1.0):
            # Word marca el apaisado con w:orient y deja w/h verticales
            pw, ph = ph, pw
        geoms.append(
            (
                max(72.0, (pw - left - right) * 72.0),
                max(144.0, (ph - top - bottom) * 72.0),
            )
        )
    if not geoms:
        geoms = [(468.0, 648.0)]

    def geom_for(index: int) -> tuple[float, float]:
        if 0 <= index < len(geoms):
            return geoms[index]
        # ultima seccion definida
        for i in range(len(geoms) - 1, -1, -1):
            if i <= index:
                return geoms[i]
        return geoms[0]

    page = 1
    used = 0.0
    for p in paragraphs:
        content_w_pt, content_h_pt = geom_for(p.section_index)
        size = p.max_size_pt or 12.0
        spacing = p.line_spacing if p.line_spacing is not None else 1.15
        line_h = max(6.0, size * spacing)
        # ancho medio de caracter ~0.46 em para Times/Calibri
        chars_per_line = max(20, int(content_w_pt / max(4.0, size * 0.46)))
        if p.is_empty:
            lines = 1
        else:
            lines = max(1, -(-len(p.text.strip()) // chars_per_line))
        needed = min(lines * line_h, content_h_pt)
        if p.has_page_break and used > 0:
            page += 1
            used = 0.0
        if used + needed > content_h_pt:
            page += 1
            used = needed  # un bloque nunca ocupa mas de una pagina
        else:
            used += needed
        p.estimated_page = page


def _iter_body_paragraphs(doc: DocxDocument):
    """Parrafos del cuerpo EN ORDEN DE DOCUMENTO, incluidos los que estan dentro
    de tablas (doc.paragraphs los omite, con lo que las tablas eran invisibles
    para las reglas y para la estimacion de paginas).
    """
    try:
        body = doc.element.body
    except Exception:
        for p in doc.paragraphs:
            yield p, False
        return

    def walk(element, in_table=False):
        for child in element.iterchildren():
            tag = child.tag
            if tag == W_NS + "p":
                yield Paragraph(child, doc), in_table
            elif tag == W_NS + "tbl":
                yield from walk_table(child, True)
            elif tag in (W_NS + "sdt", W_NS + "sdtContent"):
                content = child.find(W_NS + "sdtContent")
                if content is not None:
                    yield from walk(content, in_table)
                else:
                    yield from walk(child, in_table)

    def walk_table(tbl_el, in_table=True):
        for row in tbl_el.iter(W_NS + "tr"):
            for cell in row.iterchildren(W_NS + "tc"):
                yield from walk(cell, in_table)

    yield from walk(body)


def image_sizes(data: bytes) -> list[dict]:
    """Tamano con el que el autor coloco cada imagen, en centimetros.

    Word guarda ese tamano en <wp:extent> (EMU). Mammoth no lo traslada al HTML,
    asi que sin esto el navegador pinta cada imagen a su tamano natural en
    pixeles: una figura colocada a 6 cm se ve ocupando toda la caja de texto.
    Se devuelven en orden de documento, que es el mismo en que mammoth las
    emite, para poder emparejarlas una a una.
    """
    try:
        doc: DocxDocument = Document(BytesIO(data))
        body = doc.element.body
    except Exception:
        return []

    out: list[dict] = []
    for extent in body.iter(WP_NS + "extent"):
        # se ignoran las copias de reserva: describen el mismo dibujo
        if any(a.tag == MC_FALLBACK_NS for a in extent.iterancestors()):
            continue
        try:
            cx = int(extent.get("cx"))
            cy = int(extent.get("cy"))
        except (TypeError, ValueError):
            continue
        if cx <= 0 or cy <= 0:
            continue
        out.append(
            {
                "width_cm": round(cx / EMU_PER_CM, 3),
                "height_cm": round(cy / EMU_PER_CM, 3),
            }
        )
    return out


def _extract_tables(doc: DocxDocument, paragraphs: list[ParagraphInfo], base_font: str | None, base_size: float | None) -> list[TableInfo]:
    """Extrae las tablas del documento con su estructura basica.

    Se recorre el cuerpo en orden para asociar a cada tabla el parrafo que la
    precede (su posible rotulo 'Tabla N'). La estructura de celdas/bordes no
    se recoge en los parrafos sueltos, por eso se lee aqui del XML.
    """
    tables: list[TableInfo] = []
    last_para_idx: int | None = None
    prev_para_idx: int | None = None
    para_idx = 0
    table_elements: list[tuple[object, int | None, int | None]] = []

    def walk(el):
        nonlocal last_para_idx, prev_para_idx, para_idx
        for child in el.iterchildren():
            tag = child.tag
            if tag == W_NS + "p":
                if para_idx < len(paragraphs) and not paragraphs[para_idx].is_empty:
                    prev_para_idx = last_para_idx
                    last_para_idx = para_idx
                para_idx += 1
            elif tag == W_NS + "tbl":
                table_elements.append((child, last_para_idx, prev_para_idx))
                # contar los parrafos dentro de la tabla (no actualizan last_para_idx)
                para_idx += sum(1 for _ in child.iter(W_NS + "p"))
            elif tag in (W_NS + "sdt", W_NS + "sdtContent"):
                content = child.find(W_NS + "sdtContent")
                if content is not None:
                    walk(content)
                else:
                    walk(child)

    try:
        walk(doc.element.body)
    except Exception:
        return tables

    for ti, (tbl_el, last_idx, prev_idx) in enumerate(table_elements, start=1):
        info = TableInfo(index=ti)
        # el rotulo 'Tabla N' suele estar en su propia linea, seguido del titulo
        candidates = [i for i in (prev_idx, last_idx) if i is not None]
        number_idx = None
        for ci in candidates:
            if ci < len(paragraphs) and re.match(
                r"^(tabla|table)\s*\d+\b", paragraphs[ci].text.strip(), re.IGNORECASE
            ):
                number_idx = ci
                break
        if number_idx is None and candidates:
            number_idx = candidates[-1]
        info.caption_paragraph_index = number_idx
        if number_idx is not None and number_idx < len(paragraphs):
            num_para = paragraphs[number_idx]
            info.caption_text = num_para.text.strip()
            info.has_caption_number = bool(
                re.match(r"^(tabla|table)\s*\d+\b", info.caption_text, re.IGNORECASE)
            )
            # el titulo es el parrafo siguiente al rotulo (si existe) o el mismo
            title_idx = None
            for ci in candidates:
                if ci is not None and ci > number_idx:
                    title_idx = ci
                    break
            if title_idx is None:
                title_idx = number_idx
            if title_idx < len(paragraphs):
                title_para = paragraphs[title_idx]
                if title_idx == number_idx:
                    # titulo en la misma linea: contar cursivas tras el numero
                    info.title_italic = any(r.italic for r in title_para.runs if r.text.strip())
                else:
                    info.title_italic = any(r.italic for r in title_para.runs if r.text.strip())
                    if title_para.text.strip():
                        info.caption_text = num_para.text.strip() + " " + title_para.text.strip()

        # bordes
        try:
            tblPr = tbl_el.find(W_NS + "tblPr")
            borders = tblPr.find(W_NS + "tblBorders") if tblPr is not None else None
            if borders is not None:
                def border_val(name):
                    el = borders.find(W_NS + name)
                    if el is None:
                        return None
                    return el.get(W_NS + "val")

                def present(v):
                    return v not in (None, "none", "nil")

                info.has_horizontal_borders = (
                    present(border_val("top"))
                    or present(border_val("bottom"))
                    or present(border_val("insideH"))
                )
                info.has_vertical_borders = (
                    present(border_val("left"))
                    or present(border_val("right"))
                    or present(border_val("insideV"))
                )
        except Exception:
            pass

        # filas y columnas + encabezado en negrita
        rows = list(tbl_el.iter(W_NS + "tr"))
        info.rows = len(rows)
        if rows:
            first_row = rows[0]
            cells = list(first_row.iterchildren(W_NS + "tc"))
            info.cols = len(cells)
            header_bold = info.cols > 0
            for cell in cells:
                cell_has_text = False
                cell_all_bold = True
                cell_any_text = False
                for r_el in cell.iter(W_NS + "r"):
                    rpr = r_el.find(W_NS + "rPr")
                    bold = False
                    if rpr is not None:
                        b_el = rpr.find(W_NS + "b")
                        if b_el is not None:
                            val = b_el.get(W_NS + "val")
                            bold = val not in ("0", "false")
                    for t_el in r_el.iter(W_NS + "t"):
                        if t_el.text and t_el.text.strip():
                            cell_any_text = True
                            if not bold:
                                cell_all_bold = False
                if cell_any_text and not cell_all_bold:
                    header_bold = False
                if not cell_any_text:
                    # celda vacia no rompe el encabezado
                    pass
            info.has_header_row = header_bold

        # fuente de las celdas
        fonts: set[str] = set()
        sizes: set[int] = set()
        for r_el in tbl_el.iter(W_NS + "r"):
            rpr = r_el.find(W_NS + "rPr")
            if rpr is None:
                continue
            rfonts = rpr.find(W_NS + "rFonts")
            if rfonts is not None:
                for attr in ("ascii", "hAnsi"):
                    v = rfonts.get(W_NS + attr)
                    if v:
                        fonts.add(v)
            sz = rpr.find(W_NS + "sz")
            if sz is not None:
                v = sz.get(W_NS + "val")
                if v:
                    try:
                        sizes.add(int(v) // 2)
                    except ValueError:
                        pass
        info.cell_font_name = next(iter(fonts), None)
        info.cell_font_size_pt = next(iter(sizes), None)
        if base_font and fonts and base_font not in fonts:
            info.cell_font_consistent = False
        if base_size and sizes and base_size not in sizes:
            info.cell_font_consistent = False
        if not fonts and not sizes:
            info.cell_font_consistent = True

        tables.append(info)

    # mencion en el texto: "Tabla N" en parrafos fuera de tabla
    for info in tables:
        needle = re.compile(rf"\btabla\s*{info.index}\b", re.IGNORECASE)
        for p in paragraphs:
            if p.in_table:
                continue
            if p.index == info.caption_paragraph_index:
                continue
            if needle.search(p.text):
                info.mentioned_in_text = True
                break

    return tables


def parse_docx(data: bytes, filename: str = "documento.docx") -> ParsedDocument:
    doc: DocxDocument = Document(BytesIO(data))

    base_font = None
    base_size = None
    try:
        normal = doc.styles["Normal"]
        base_font = normal.font.name
        base_size = _pt(normal.font.size)
    except Exception:
        pass

    paragraphs: list[ParagraphInfo] = []
    section_index = 0
    for i, (paragraph, in_table) in enumerate(_iter_body_paragraphs(doc)):
        text = paragraph.text
        runs = _runs(paragraph)
        for r in runs:
            if r.font_name is None:
                r.font_name = base_font
            if r.font_size_pt is None:
                r.font_size_pt = base_size

        try:
            style_name = paragraph.style.name if paragraph.style else ""
        except Exception:
            style_name = ""
        pf = paragraph.paragraph_format
        try:
            style_pf = paragraph.style.paragraph_format
        except Exception:
            style_pf = pf

        first_line_indent = _inches(pf.first_line_indent)
        if first_line_indent is None:
            first_line_indent = _inches(style_pf.first_line_indent)
        left_indent = _inches(pf.left_indent)
        if left_indent is None:
            left_indent = _inches(style_pf.left_indent)

        paragraphs.append(
            ParagraphInfo(
                index=i,
                text=text,
                style_name=style_name or "",
                alignment=_alignment_name(paragraph),
                line_spacing=_line_spacing(paragraph),
                space_before_pt=_pt(_inherited(pf.space_before, style_pf.space_before)),
                space_after_pt=_pt(_inherited(pf.space_after, style_pf.space_after)),
                first_line_indent_in=first_line_indent,
                left_indent_in=left_indent,
                runs=runs,
                heading_level=_heading_level(style_name or "", text, runs),
                is_list_item=_is_list_item(paragraph),
                is_empty=(text.strip() == ""),
                has_page_break=_has_page_break(paragraph),
                section_index=section_index,
                in_table=in_table,
            )
        )
        # un sectPr dentro del parrafo cierra la seccion: el siguiente es de otra
        try:
            ppr = paragraph._p.pPr
            if ppr is not None and ppr.find(W_NS + "sectPr") is not None:
                section_index += 1
        except Exception:
            pass

    tables = _extract_tables(doc, paragraphs, base_font, base_size)

    sections: list[SectionInfo] = []
    for i, section in enumerate(doc.sections):
        sections.append(
            SectionInfo(
                index=i,
                top_margin_in=_inches(section.top_margin),
                bottom_margin_in=_inches(section.bottom_margin),
                left_margin_in=_inches(section.left_margin),
                right_margin_in=_inches(section.right_margin),
                page_width_in=_inches(section.page_width),
                page_height_in=_inches(section.page_height),
            )
        )

    references_start = _find_references_start(paragraphs)
    _estimate_pages(paragraphs, sections)

    parsed = ParsedDocument(
        filename=filename,
        paragraphs=paragraphs,
        sections=sections,
        default_font=base_font,
        default_font_size_pt=base_size,
        references_start=references_start,
        tables=tables,
    )

    # Capa 2: citas y referencias ya estructuradas (se inyecta aqui para que
    # todas las reglas reciben el mismo objeto, ya construido)
    from backend.app.services.bibliography import build_bibliography

    parsed.bibliography = build_bibliography(parsed)
    return parsed


REFERENCES_END_RE = re.compile(r"^(anexos?|ap[eé]ndices?)\b")


def _is_references_end(p: ParagraphInfo) -> bool:
    """Cierra la lista de referencias en el siguiente bloque de contenido nuevo."""
    text = re.sub(r"\s+", " ", p.text.strip().lower())
    text = re.sub(r"^[\d]+[.)]\s*", "", text).strip(" .:-–—")
    # un encabezado cierra la lista, salvo que parezca una referencia citada
    if p.style_name in HEADING_STYLES and not re.search(r"\(\d{4}\)", p.text):
        return True
    return bool(REFERENCES_END_RE.match(text))


def _find_references_start(paragraphs: list[ParagraphInfo]) -> int | None:
    """Encuentra el encabezado de la lista de referencias.

    Acepta las variantes reales: '6. REFERENCIAS', '7. Bibliografía',
    'Referencias APA', 'REFERENCIAS BIBLIOGRÁFICAS:'.
    Si hay varios candidatos se toma el último (en una tesis, la lista de
    referencias va al final; una 'Introducción' citada al principio no debe ganar).
    """
    found: int | None = None
    for p in paragraphs:
        normalized = re.sub(r"\s+", " ", p.text.strip().lower())
        normalized = re.sub(r"^[\d]+[.)]\s*", "", normalized)  # "6. Referencias"
        normalized = normalized.strip(" .:-–—")
        normalized = re.sub(r"\b(apa|bibliografica|bibliograficas|bibliografico)\b", " ", normalized)
        normalized = re.sub(r"\s+", " ", normalized).strip()
        if normalized in REFERENCES_HEADINGS:
            found = p.index
    return found
