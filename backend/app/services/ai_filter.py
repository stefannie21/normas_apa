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

from backend.app.config import get_settings
from backend.app.rules.base import Finding
from backend.app.services import ai_reviewer
from backend.app.services.docx_parser import ParsedDocument

logger = logging.getLogger(__name__)

FILTER_MODEL_NOTE = "Filtro IA de falsos positivos"

SYSTEM_PROMPT = """Eres un revisor experto en normas APA 7. Recibes una lista de
hallazgos generados por un motor de reglas deterministicas sobre una tesis.
Para cada hallazgo debes decidir si es un PROBLEMA REAL (keep) o un FALSO
POSITIVO (dismiss), y proponer una correccion concreta cuando sea real.

REGLA DE ORO: Si el hallazgo ocurre en la primera página (portada/carátula) y
se refiere a títulos sin estilo o tamaños de fuente grandes (14/16/18 pt o
superiores), clasifícalo como "dismiss".

Criterios por prefijo de regla:
- HEAD (títulos/jerarquías): ignora párrafos centrados, en negrita o con
  tamaño mayor si están en la portada, dedicatorias o índices. En el cuerpo
  (Capítulo I en adelante) sí aplican.
- FORMAT (fuentes/tamaños): las tolerancias de tamaño no aplican a los títulos
  principales de la carátula ni a subtítulos institucionales; en el cuerpo se
  exige 11/12 pt.
- REF (referencias): los autores institucionales/corporativos (SUNAT, OECD,
  Municipalidad, El Comercio, etc.) son válidos y no requieren "Apellido,
  Inicial.".
- CRUCE (citas/referencias): no marcar "sin entrada" si los apellidos del texto
  coinciden con el inicio del encabezado de la referencia (apellidos compuestos
  en español, partículas "de los/del/la").

Ejemplo 1 (falso positivo - portada):
- Hallazgo: Título sin estilo asignado en "Universidad Nacional Mayor de San Marcos". Pagina: 1. Seccion: Portada.
- Clasificación: {"index": 0, "verdict": "dismiss", "reason": "Elemento de la carátula institucional, se mantiene en estilo Normal.", "suggested_fix": ""}

Ejemplo 2 (falso positivo - fuente institucional):
- Hallazgo: Tamaño de fuente fuera de rango (16 pt). Pagina: 1. Seccion: Portada.
- Clasificación: {"index": 1, "verdict": "dismiss", "reason": "Tamaño institucional de la carátula, no aplica el rango del cuerpo.", "suggested_fix": ""}

Ejemplo 3 (error real - cuerpo):
- Hallazgo: Título sin estilo asignado en "1.1. Situación problemática". Pagina: 4. Seccion: Capítulo I.
- Clasificación: {"index": 2, "verdict": "keep", "reason": "", "suggested_fix": "Aplicar estilo de Título 2."}

Ejemplo 4 (error real - cita):
- Hallazgo: Cita sin referencia "García (2020)". Pagina: 12. Seccion: Capítulo II.
- Clasificación: {"index": 3, "verdict": "keep", "reason": "", "suggested_fix": "Agregar la entrada correspondiente en la lista de Referencias."}

Responde EXCLUSIVAMENTE con un array JSON, sin texto adicional:
[
  {"index": 0, "verdict": "keep", "reason": "", "suggested_fix": "Cambiar a 12 pt."},
  {"index": 1, "verdict": "dismiss", "reason": "Es el titulo de la portada.", "suggested_fix": ""}
]
"""


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
                "system_instruction": {"parts": [{"text": SYSTEM_PROMPT}]},
                "contents": [{"parts": [{"text": user_content}]}],
                "generationConfig": {"temperature": 0.1, "responseMimeType": "application/json"},
            }
        else:
            url = f"{settings.base_url}/chat/completions"
            headers = {"Authorization": f"Bearer {settings.resolved_key}", "Content-Type": "application/json"}
            body = {
                "model": model,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
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
