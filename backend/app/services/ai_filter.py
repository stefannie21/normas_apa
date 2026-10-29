"""Filtro IA de falsos positivos.

Capa opcional que revisa los hallazgos del motor de reglas deterministas y
propone cuales son falsos positivos (con motivo) y, para los que se mantienen,
una sugerencia de correccion concreta. La IA nunca borra por su cuenta: los
hallazgos descartados se guardan en `dismissed_findings` para auditoria y el
usuario decide.

Principios:
 - Falla abierto: si la IA no responde, se conservan TODOS los hallazgos.
 - La IA solo puede descartar con motivo explicito; sin motivo se mantiene.
 - Temperatura baja y esquema JSON estricto para evitar inventos.
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field

from backend.app.config import BASE_DIR, get_settings
from backend.app.rules.base import Finding
from backend.app.services import ai_reviewer
from backend.app.services.docx_parser import ParsedDocument

logger = logging.getLogger(__name__)

FILTER_MODEL_NOTE = "Filtro IA de falsos positivos"

SYSTEM_PROMPT = """Eres un asistente de IA experto en redaccion academica bajo normas APA (7. edicion) y en la revision de estructura de tesis universitarias. Tu tarea es actuar como un filtro inteligente sobre los hallazgos de un motor de reglas estricto para clasificar cada uno en:
- "keep": Es un problema real en el documento que requiere correccion obligatoria.
- "dismiss": Es un falso positivo provocado por limitaciones del motor de reglas o inconsistencias visuales del editor.

CRITERIOS DE EXCLUSION ESTRICTOS (Falsos Positivos comunes):

1. PORTADA Y DATOS INSTITUCIONALES:
Cualquier hallazgo de tipo HEAD (titulos sin estilo) o FORMAT (tamano de fuente fuera de rango, ej. 14pt, 16pt, 18pt) que ocurra en la primera pagina o portada (nombres de universidades, facultades, titulos de tesis, la palabra "Autor") debe clasificarse obligatoriamente como "dismiss".

2. FALSOS POSITIVOS DE ALINEACION (HEAD-002):
Si un hallazgo indica que un subtitulo (por ejemplo, "1.1. Situacion problematica") incumple el formato de alineacion a la izquierda, pero el texto ya se encuentra visualmente en el margen izquierdo del documento, clasificalo como "dismiss". Esto ocurre por discrepancias entre los estilos por defecto del editor web y la regla estricta.

3. AUTORES CORPORATIVOS (REF):
Los autores institucionales/corporativos (SUNAT, OECD, Municipalidad, El Comercio, etc.) son validos y no requieren "Apellido, Inicial.".

4. APELLIDOS COMPUESTOS (CRUCE):
No marcar "sin entrada" si los apellidos del texto coinciden con el inicio del encabezado de la referencia (apellidos compuestos en espanol, particulas "de los/del/la").

5. TABLAS Y ANEXOS:
Los tamanos de fuente reducidos (8/10 pt) dentro de tablas y matrices de consistencia son validos; no marcarlos como fuera de rango.

EJEMPLOS DE CLASIFICACION:

Ejemplo 1 (Falso positivo en portada):
- Hallazgo: Titulo sin estilo asignado en "Universidad Nacional Mayor de San Marcos". Ubicacion: Pagina 1.
- Salida JSON: {"index": 0, "verdict": "dismiss", "reason": "Elemento correspondiente a la caratula institucional de la primera pagina.", "suggested_fix": ""}

Ejemplo 2 (Falso positivo de alineacion HEAD-002):
- Hallazgo: HEAD-002 Titulo nivel 2 incumple el formato APA: debe alinearse a la izquierda en "1.1. Situacion problematica".
- Salida JSON: {"index": 1, "verdict": "dismiss", "reason": "El subtitulo ya se encuentra alineado correctamente al margen izquierdo en el documento.", "suggested_fix": ""}

Ejemplo 3 (Problema real):
- Hallazgo: Titulo sin estilo en un subtitulo real del cuerpo que no usa la etiqueta adecuada.
- Salida JSON: {"index": 2, "verdict": "keep", "reason": "", "suggested_fix": "Aplicar estilo de Titulo 2 en negrita y alineado a la izquierda."}

Ejemplo 4 (Problema real - cita):
- Hallazgo: Cita sin referencia "Garcia (2020)". Ubicacion: Pagina 12.
- Salida JSON: {"index": 3, "verdict": "keep", "reason": "", "suggested_fix": "Agregar la entrada correspondiente en la lista de Referencias."}

Responde estrictamente en formato JSON valido segun el esquema solicitado, sin texto adicional fuera del JSON:
[
  {"index": 0, "verdict": "keep", "reason": "", "suggested_fix": "Cambiar a 12 pt."},
  {"index": 1, "verdict": "dismiss", "reason": "Es el titulo de la portada.", "suggested_fix": ""}
]
"""



# --- Feedback loop: registro de falsos positivos descartados por la IA ---
DISMISS_LOG = BASE_DIR / "data" / "ai_dismissed_log.jsonl"


def _load_recent_dismissed(limit: int = 5) -> list[dict]:
    """Carga los ultimos casos descartados para usarlos como ejemplos dinamicos."""
    if not DISMISS_LOG.exists():
        return []
    out: list[dict] = []
    try:
        lines = DISMISS_LOG.read_text(encoding="utf-8").splitlines()
    except Exception:
        return []
    for line in lines[-limit:]:
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except Exception:
            continue
    return out


def _log_dismissed(dismissed: list[Finding]) -> None:
    """Persiste los descartes para el ciclo de retroalimentacion."""
    if not dismissed:
        return
    try:
        DISMISS_LOG.parent.mkdir(parents=True, exist_ok=True)
        with DISMISS_LOG.open("a", encoding="utf-8") as fh:
            for f in dismissed:
                entry = {
                    "rule_id": f.rule_id,
                    "message": (f.message or "")[:160],
                    "page": None,
                    "reason": (f.extra or {}).get("ai_dismiss_reason", ""),
                }
                loc = f.location or ""
                import re as _re
                m = _re.search(r"P[aá]gina(?:s)?\s*(\d+)", loc, _re.IGNORECASE)
                if m:
                    entry["page"] = int(m.group(1))
                fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception as exc:
        logger.warning("No se pudo guardar el log de descartes IA: %s", exc)


def _build_system_prompt() -> str:
    """System prompt base + ejemplos aprendidos del historial (feedback loop)."""
    base = SYSTEM_PROMPT
    recent = _load_recent_dismissed(5)
    if not recent:
        return base
    extra = "\n\nEjemplos adicionales aprendidos del historial de descartes:\n"
    for i, e in enumerate(recent, start=100):
        extra += (
            f'- Hallazgo: {e.get("rule_id")} - {e.get("message")} '
            f'(Pagina: {e.get("page")}).\n'
            f'  Clasificacion: {{"index": {i}, "verdict": "dismiss", '
            f'"reason": "{e.get("reason", "")}", "suggested_fix": ""}}\n'
        )
    return base + extra



@dataclass
class FilterResult:
    kept: list[Finding] = field(default_factory=list)
    dismissed: list[Finding] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def _build_user_content(findings: list[Finding]) -> str:
    items = []
    for i, f in enumerate(findings):
        extra = f.extra or {}
        # Metadatos de contexto: página, sección y si está en tabla, para que la
        # IA no trate igual a todo el documento (portada vs. cuerpo vs. anexos).
        page = None
        loc = f.location or ""
        m = re.search(r"P[aá]gina(?:s)?\s*(\d+)", loc, re.IGNORECASE)
        if m:
            page = int(m.group(1))
        if page is None and f.paragraph_index is not None:
            page = None
        items.append(
            {
                "index": i,
                "rule_id": f.rule_id,
                "severity": f.severity.value,
                "message": f.message[:240],
                "page": page,
                "section": extra.get("section", ""),
                "in_table": bool(extra.get("in_table", False)),
                "location": loc[:120],
                "excerpt": (f.excerpt or "")[:120],
                "paragraph": f.paragraph_index,
            }
        )
    return json.dumps({"findings": items}, ensure_ascii=False)


def _apply(items: list[dict], findings: list[Finding], result: FilterResult) -> None:
    by_index = {int(it.get("index", -1)): it for it in items if "index" in it}
    for i, f in enumerate(findings):
        decision = by_index.get(i, {})
        verdict = str(decision.get("verdict", "keep")).lower().strip()
        reason = str(decision.get("reason", "")).strip()
        fix = str(decision.get("suggested_fix", "")).strip()
        if verdict == "dismiss" and reason:
            f.extra = dict(f.extra or {})
            f.extra["ai_dismiss_reason"] = reason
            result.dismissed.append(f)
        else:
            if fix:
                f.extra = dict(f.extra or {})
                f.extra["ai_suggested_fix"] = fix
            result.kept.append(f)


def filter_findings(
    document: ParsedDocument, findings: list[Finding]
) -> FilterResult:
    result = FilterResult()
    settings = ai_reviewer.get_settings() if hasattr(ai_reviewer, "get_settings") else None
    from backend.app.config import get_settings

    settings = get_settings()
    if not settings.ai_available or not findings:
        # Falla abierto: conservar todo, sin filtrar.
        result.kept = list(findings)
        if not settings.ai_available:
            result.notes.append("Filtro IA desactivado (sin clave configurada).")
        return result

    # Procesar en lotes para no exceder el contexto del modelo.
    batch_size = 40
    used_models: list[str] = []
    for start in range(0, len(findings), batch_size):
        batch = findings[start : start + batch_size]
        content = _build_user_content(batch)
        items, used_model, error = _call_with_prompt(settings, content)
        if error is not None:
            logger.warning("Filtro IA fallo en lote %d: %s", start, error)
            result.notes.append(f"Filtro IA no disponible en un lote: {error}")
            # conservar el lote sin filtrar
            result.kept.extend(batch)
            continue
        if used_model:
            used_models.append(used_model)
        _apply(items, batch, result)

    if used_models:
        result.notes.append(
            f"Filtro IA ejecutado con: {', '.join(sorted(set(used_models)))}."
        )
    # Si por algun motivo no se clasifico todo, conservar los faltantes.
    _log_dismissed(result.dismissed)
    classified = len(result.kept) + len(result.dismissed)
    if classified < len(findings):
        missing = findings[classified:]
        result.kept.extend(missing)
    return result


def _call_with_prompt(settings, user_content: str):
    """Llama al proveedor con SYSTEM_PROMPT propio del filtro."""
    import httpx

    models = settings.model_cascade
    last_error = None
    for model in models:
        if settings.provider == "gemini":
            url = f"{settings.base_url}/models/{model}:generateContent"
            headers = {"x-goog-api-key": settings.resolved_key, "Content-Type": "application/json"}
            body = {
                "system_instruction": {"parts": [{"text": _build_system_prompt()}]},
                "contents": [{"parts": [{"text": user_content}]}],
                "generationConfig": {"temperature": 0.1, "responseMimeType": "application/json"},
            }
        else:
            url = f"{settings.base_url}/chat/completions"
            headers = {"Authorization": f"Bearer {settings.resolved_key}", "Content-Type": "application/json"}
            body = {
                "model": model,
                "messages": [
                    {"role": "system", "content": _build_system_prompt()},
                    {"role": "user", "content": user_content},
                ],
                "temperature": 0.1,
                "response_format": {"type": "json_object"},
            }
        try:
            with httpx.Client(timeout=60.0) as client:
                r = client.post(url, json=body, headers=headers)
                r.raise_for_status()
                data = r.json()
            if settings.provider == "gemini":
                content = data["candidates"][0]["content"]["parts"][0]["text"]
            else:
                content = data["choices"][0]["message"]["content"]
            items = ai_reviewer._extract_json(content.strip())
            return items, model, None
        except Exception as exc:
            last_error = f"{model}: {exc}"
            continue
    return [], (models[-1] if models else ""), last_error
