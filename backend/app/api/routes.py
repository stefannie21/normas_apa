from __future__ import annotations

import io
import re
import unicodedata

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Length
from lxml import etree
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, Response

from backend.app.config import get_settings
from backend.app.rules.registry import get_rules
from backend.app.services import ai_reviewer, report
from backend.app.services.analyzer import analyze
from backend.app.services.docx_parser import parse_docx
from backend.app.services.docx_writer import apply_corrections
from backend.app.services.report_docx import build_report_docx

router = APIRouter(prefix="/api", tags=["apa"])


@router.get("/health")
def health() -> dict:
    settings = get_settings()
    return {
        "status": "ok",
        "ai_enabled": settings.ai_available,
        "ai_provider": settings.provider,
        "ai_model": settings.resolved_model,
        "ai_cascade": settings.model_cascade,
    }


@router.get("/rules")
def list_rules() -> dict:
    return {
        "rules": [
            {
                "id": r.id,
                "name": r.name,
                "category": r.category.value,
                "description": r.description,
                "severity": r.default_severity.value,
            }
            for r in get_rules()
        ]
    }


def _align_value(alignment):
    if alignment == WD_ALIGN_PARAGRAPH.CENTER:
        return "center"
    if alignment == WD_ALIGN_PARAGRAPH.RIGHT:
        return "right"
    if alignment in (WD_ALIGN_PARAGRAPH.JUSTIFY, WD_ALIGN_PARAGRAPH.DISTRIBUTE):
        return "justify"
    return "left"


def _text_key(text: str, n: int = 48) -> str:
    """Clave estable para emparejar parrafos del docx con los del HTML de mammoth.

    Se normalizan acentos y se conservan las letras de cualquier alfabeto: con una
    clave solo-ASCII, un parrafo en chino (u otros alfabetos) se descartaba entero.
    """
    norm = unicodedata.normalize("NFKD", text or "")
    norm = "".join(c for c in norm if not unicodedata.combining(c))
    norm = re.sub(r"[^\w]+", " ", norm.lower(), flags=re.UNICODE)
    return norm.strip().replace("_", " ")[:n]


W_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"

# Tamano de pagina por defecto: A4 (21 x 29.7 cm). Se usa solo cuando el .docx
# no declara w:pgSz. Antes caia en Carta (8.5 x 11 in), que no es el papel
# habitual de las tesis.
DEFAULT_PAGE_W_IN = 8.268
DEFAULT_PAGE_H_IN = 11.693


def _in(value, default: float) -> float:
    if value is None:
        return default
    try:
        return round(float(value.inches), 3)
    except Exception:
        return default


def _doc_defaults(doc) -> dict:
    """Fuente y tamano por defecto del documento (mammoth los descarta)."""
    font = None
    size_pt = None
    try:
        rpr = doc.styles.element.find(
            W_NS + "docDefaults/" + W_NS + "rPrDefault/" + W_NS + "rPr"
        )
        if rpr is not None:
            fonts = rpr.find(W_NS + "rFonts")
            if fonts is not None:
                font = fonts.get(W_NS + "ascii") or fonts.get(W_NS + "hAnsi")
            sz = rpr.find(W_NS + "sz")
            if sz is not None and sz.get(W_NS + "val"):
                size_pt = round(int(sz.get(W_NS + "val")) / 2.0, 1)
    except Exception:
        pass
    if not font or not size_pt:
        try:
            normal = doc.styles["Normal"].font
            font = font or normal.name
            if not size_pt and normal.size is not None:
                size_pt = round(normal.size.pt, 1)
        except Exception:
            pass
    if not font:
        font = _theme_font(doc) or "Calibri"
    return {"font": font, "size_pt": size_pt}


def _theme_font(doc) -> str | None:
    """Fuente menor del tema de Word (Calibri/Arial), que es la que se aplica
    cuando el documento no declara una fuente explicita."""
    try:
        for part in doc.part.package.iter_parts():
            if "theme" not in str(part.partname):
                continue
            root = etree.fromstring(part.blob)
            ns = {"a": "http://schemas.openxmlformats.org/drawingml/2006/main"}
            minor = root.find(".//a:themeElements/a:fontScheme/a:minorFont/a:latin", ns)
            if minor is not None and minor.get("typeface"):
                return minor.get("typeface")
    except Exception:
        pass
    return None


def _breaks_before(paragraph) -> bool:
    """True si este parrafo empieza en una pagina nueva (salto explicito)."""
    try:
        ppr = paragraph._p.pPr
        if ppr is not None and ppr.find(W_NS + "pageBreakBefore") is not None:
            return True
    except Exception:
        pass
    return False


def _ends_with_page_break(paragraph) -> bool:
    try:
        for br in paragraph._p.iter(W_NS + "br"):
            if br.get(W_NS + "type") == "page":
                return True
    except Exception:
        pass
    return False


def _paragraph_metrics(p) -> dict:
    """Interlineado, separaciones y tamano de fuente resueltos del parrafo."""
    pf = p.paragraph_format
    ls = pf.line_spacing
    if ls is None:
        try:
            ls = p.style.paragraph_format.line_spacing
        except Exception:
            ls = None
    if isinstance(ls, Length):
        ls = None

    def pt(value, style_value):
        v = value if value is not None else style_value
        if v is None:
            return None
        try:
            return round(float(v.pt), 1)
        except Exception:
            return None

    try:
        spf = p.style.paragraph_format
    except Exception:
        spf = pf

    sizes = []
    for r in p.runs:
        s = r.font.size
        if s is None:
            try:
                s = p.style.font.size
            except Exception:
                s = None
        if s is not None and r.text.strip():
            sizes.append(round(s.pt, 1))

    return {
        "ls": round(float(ls), 2) if isinstance(ls, (int, float)) else None,
        "sb": pt(pf.space_before, spf.space_before),
        "sa": pt(pf.space_after, spf.space_after),
        "size": max(sizes) if sizes else None,
    }


def _sections_meta(doc) -> list[dict]:
    """Geometria de cada seccion del docx (vertical/horizontal, tamaño y margenes).

    Word marca la orientacion con w:orient y muchas veces deja w:w/w:h en
    medidas verticales, de modo que comparar ancho vs alto NO es suficiente.
    """
    section_of: list[int] = []
    first_key: dict[int, str] = {}
    idx = 0
    for p in doc.paragraphs:
        section_of.append(idx)
        key = _text_key(p.text)
        if key and idx not in first_key:
            first_key[idx] = key
        ppr = p._p.pPr
        if ppr is not None and ppr.find(W_NS + "sectPr") is not None:
            idx += 1

    out: list[dict] = []
    for i, s in enumerate(doc.sections):
        # A4 (21 x 29.7 cm) si el .docx no declara tamano de pagina
        w = _in(s.page_width, DEFAULT_PAGE_W_IN)
        h = _in(s.page_height, DEFAULT_PAGE_H_IN)
        orient = None
        try:
            pg_sz = s._sectPr.find(W_NS + "pgSz")
            if pg_sz is not None:
                orient = pg_sz.get(W_NS + "orient")
        except Exception:
            orient = None
        landscape = orient == "landscape" or w > h
        if landscape and w < h:
            w, h = h, w
        out.append(
            {
                "index": i,
                "width_in": w,
                "height_in": h,
                "top_in": _in(s.top_margin, 1.0),
                "bottom_in": _in(s.bottom_margin, 1.0),
                "left_in": _in(s.left_margin, 1.0),
                "right_in": _in(s.right_margin, 1.0),
                "orient": orient or ("landscape" if landscape else "portrait"),
                "landscape": landscape,
                "first_key": first_key.get(i),
            }
        )
    return out


def _read_upload(file: UploadFile, settings) -> bytes:
    """Lee por tramos y aborta en cuanto se supera el limite (no carga todo en memoria)."""
    limit = settings.max_upload_mb * 1024 * 1024
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = file.file.read(256 * 1024)
        if not chunk:
            break
        total += len(chunk)
        if total > limit:
            raise HTTPException(
                status_code=413, detail=f"El archivo supera {settings.max_upload_mb} MB"
            )
        chunks.append(chunk)
    if total == 0:
        raise HTTPException(status_code=400, detail="El archivo esta vacio")
    return b"".join(chunks)


def _load_doc(file: UploadFile):
    if not file.filename or not file.filename.lower().endswith(".docx"):
        raise HTTPException(status_code=400, detail="Solo se aceptan archivos .docx")
    data = _read_upload(file, get_settings())
    try:
        return parse_docx(data, file.filename)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=422, detail=f"No se pudo leer el documento: {exc}"
        ) from exc


# Handlers sincronos (def): FastAPI los ejecuta en un threadpool, de modo que el
# parseo del .docx y las llamadas al proveedor de IA no bloquean el event loop.
@router.post("/docx-meta")
def docx_meta(file: UploadFile = File(...)) -> JSONResponse:
    """Metadatos por parrafo (alineacion, interlineado, saltos) y geometria por seccion."""
    if not file.filename or not file.filename.lower().endswith(".docx"):
        raise HTTPException(status_code=400, detail="Solo se aceptan archivos .docx")
    data = _read_upload(file, get_settings())
    try:
        doc = Document(io.BytesIO(data))
        paragraphs = []
        break_next = False
        for p in doc.paragraphs:
            key = _text_key(p.text)
            starts_new_page = _breaks_before(p) or break_next
            break_next = _ends_with_page_break(p)
            if not key:
                continue
            meta = {
                "key": key,
                "align": _align_value(p.alignment),
                "pb": bool(starts_new_page),
            }
            meta.update(_paragraph_metrics(p))
            paragraphs.append(meta)
        payload = {
            "paragraphs": paragraphs,
            "sections": _sections_meta(doc),
            "defaults": _doc_defaults(doc),
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=422, detail=f"No se pudo leer el documento: {exc}"
        ) from exc
    return JSONResponse(payload)


@router.post("/analyze")
def analyze_endpoint(file: UploadFile = File(...)) -> JSONResponse:
    document = _load_doc(file)
    result = analyze(document)
    return JSONResponse(report.build_report(result))


@router.post("/analyze/html", response_class=HTMLResponse)
def analyze_html_endpoint(file: UploadFile = File(...)) -> HTMLResponse:
    document = _load_doc(file)
    result = analyze(document)
    return HTMLResponse(report.render_html(report.build_report(result)))


@router.post("/report/docx")
def report_docx_endpoint(file: UploadFile = File(...)):
    """Genera el informe APA como documento .docx descargable.

    Devuelve un Word con el resumen de cumplimiento, el desglose por categoria
    y la tabla completa de hallazgos (errores, advertencias y observaciones).
    """
    if not file.filename or not file.filename.lower().endswith(".docx"):
        raise HTTPException(status_code=400, detail="Solo se aceptan archivos .docx")
    document = _load_doc(file)
    result = analyze(document)
    payload = report.build_report(result)
    try:
        data = build_report_docx(payload)
    except Exception as exc:  # pragma: no cover - defensivo
        raise HTTPException(
            status_code=422,
            detail=f"No se pudo generar el informe en Word: {exc}",
        ) from exc
    base = file.filename.rsplit(".docx", 1)[0]
    out_name = f"Informe-APA-{base}.docx"
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{out_name}"'},
    )


@router.post("/ai/preview")
def ai_preview_endpoint(file: UploadFile = File(...)) -> JSONResponse:
    """Que se enviaria a la IA, SIN llamarla.

    Permite que la interfaz pida consentimiento mostrando el alcance real: numero
    de referencias y citas, el tamanio maximo del payload y la garantia de que el
    texto completo de la tesis nunca se envia.
    """
    settings = get_settings()
    document = _load_doc(file)
    summary = ai_reviewer.summarize_payload(document.bibliography)
    summary["ai_enabled"] = settings.ai_available
    summary["provider"] = settings.provider
    summary["model"] = settings.resolved_model
    return JSONResponse(summary)


@router.post("/ai/classify")
def ai_classify_endpoint(
    file: UploadFile = File(...),
    consent: int = Form(0),
) -> JSONResponse:
    """Fase 3: la IA clasifica las referencias y senala elementos APA ausentes.

    Va en un endpoint aparte y asincrono a proposito: el informe instantaneo se
    entrega ya y la IA se consulta despues, de modo que una llamada lenta del
    proveedor no bloquea al asesor.

    Exige consentimiento explicito (consent=1). Sin el se responde 428 y no se
    contacta al proveedor: la revision por IA envia datos del documento fuera del
    equipo y nunca debe ocurrir sin que la persona lo haya autorizado.
    """
    if consent != 1:
        raise HTTPException(
            status_code=428,
            detail="Falta el consentimiento para enviar datos a la IA.",
        )
    settings = get_settings()
    document = _load_doc(file)
    # Contraste con reglas deterministas: se vuelven a ejecutar para detectar
    # discrepancias (sin hallazgos deterministas pero la IA sugiere con confianza >= 0.75)
    try:
        rule_result = analyze(document)
        rule_findings = rule_result.findings
    except Exception:
        rule_findings = []
    findings, notes, used_model = ai_reviewer.classify_references(
        document, settings, rule_findings=rule_findings
    )
    return JSONResponse(
        {
            "ai_enabled": settings.ai_available,
            "provider": settings.provider,
            "model": used_model or settings.resolved_model,
            "cascade": settings.model_cascade,
            "findings": [f.to_dict() for f in findings],
            "notes": notes,
        }
    )


@router.post("/export")
def export_endpoint(
    file: UploadFile = File(...),
    rules: str = Form(""),
):
    """Devuelve un .docx nuevo con las correcciones aplicadas de forma permanente.

    Recibe el .docx original y la lista de IDs de reglas corregidas (separados
    por coma). Aplica los cambios directamente con python-docx y devuelve el
    archivo binario.
    """
    if not file.filename or not file.filename.lower().endswith(".docx"):
        raise HTTPException(status_code=400, detail="Solo se aceptan archivos .docx")
    data = _read_upload(file, get_settings())
    rule_ids = [r.strip() for r in rules.split(",") if r.strip()] if rules else []
    try:
        corrected = apply_corrections(data, rule_ids)
    except Exception as exc:
        raise HTTPException(
            status_code=422, detail=f"No se pudo generar el documento: {exc}"
        ) from exc
    # Nombre del archivo: original sin .docx + "-correcciones.docx"
    base = file.filename.rsplit(".docx", 1)[0]
    out_name = f"{base}-correcciones.docx"
    return Response(
        content=corrected,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{out_name}"'},
    )
