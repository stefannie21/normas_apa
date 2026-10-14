"""Fase 3 - Capa IA acotada.

Encargo unico: clasificar el tipo de cada referencia y detectar elementos APA
que faltan. Recibe SOLO el JSON estructurado de citas y referencias (nunca la
tesis completa) y debe devolver un esquema estricto.

Principios:
 - La IA nunca escribe en el documento: clasifica y propone.
 - Cada respuesta lleva confianza; por debajo del umbral es solo sugerencia.
 - Ante cualquier fallo se informa; nunca se finge una revision limpia.
"""
from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass

import httpx

from backend.app.config import Settings
from backend.app.rules.base import Category, Finding, Severity
from backend.app.services.bibliography import Bibliography
from backend.app.services.docx_parser import ParsedDocument

logger = logging.getLogger(__name__)

MODEL_IA = "AI-010"
MODEL_CONF_MIN = 0.6  # por debajo de esto es sugerencia, nunca correccion

SYSTEM_PROMPT = (
    "Eres un asesor experto en normas APA (7.a edicion). Recibes un arreglo JSON con "
    "las citas del texto y las entradas de la lista de referencias de una tesis. "
    "Para CADA referencia determina: (1) 'type' entre articulo, libro, capitulo, "
    "tesis, informe, web, otro; (2) 'missing': elementos APA ausentes segun ese tipo "
    "de fuente; (3) 'suggestion': correccion concreta; (4) 'confidence' de 0 a 1. "
    "No inventes datos que no esten en la entrada. Responde SOLO con un arreglo JSON "
    "de objetos con las claves: index, type, missing (arreglo de cadenas), "
    "suggestion, confidence. Sin texto fuera del JSON."
)


@dataclass
class AiNote:
    message: str
    severity: str = "info"


def build_payload(bib: Bibliography) -> dict:
    """JSON minimo: solo referencias y citas relevantes."""
    return {
        "referencias": [
            {
                "index": i,
                "texto": r.raw[:400],
                "autores": r.author_count,
                "anio": r.year,
                "tipo_detectado": r.type_hint,
                "cursivas": r.has_italics,
                "titulo": r.title[:160],
                "contenedor": r.container[:120],
            }
            for i, r in enumerate(bib.references)
        ],
        "citas": [
            {"texto": c.raw[:120], "anio": c.year, "autores": c.surnames, "forma": c.form}
            for c in bib.citations[:80]
        ],
    }


def _extract_json(content: str) -> list[dict]:
    """Aisla el arreglo JSON aunque el modelo lo envuelva en texto o codigo."""
    if content.startswith("```"):
        content = re.sub(r"^```[a-zA-Z]*\s*", "", content)
        content = re.sub(r"\s*```$", "", content.strip())
    start = content.find("[")
    end = content.rfind("]")
    if start >= 0 and end > start:
        content = content[start : end + 1]
    data = json.loads(content)
    if not isinstance(data, list):
        raise ValueError("la respuesta no es un arreglo JSON")
    return [d for d in data if isinstance(d, dict)]


MAX_ATTEMPTS = 3
REQUEST_TIMEOUT = 20.0  # con 3 intentos el peor caso son ~65 s, no 3 minutos
RETRY_STATUS = {429, 500, 502, 503, 504}


def _post_with_retry(url: str, body: dict, headers: dict, attempts: int = MAX_ATTEMPTS):
    """Reintenta ante errores transitorios.

    Google responde 503 con frecuencia por demanda alta y 429 por cuota; sin
    reintento, la revision por IA fallaria de forma intermitente y el asesor lo
    interpretaria como un fallo real del documento.
    """
    last: Exception | None = None
    for attempt in range(attempts):
        try:
            with httpx.Client(timeout=REQUEST_TIMEOUT) as client:
                response = client.post(url, json=body, headers=headers)
            if response.status_code in RETRY_STATUS and attempt < attempts - 1:
                logger.info(
                    "Proveedor IA ocupado (HTTP %s); reintento %s/%s",
                    response.status_code, attempt + 1, attempts,
                )
                time.sleep(1 * (attempt + 1))
                continue
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as exc:
            last = exc
            if exc.response.status_code in RETRY_STATUS and attempt < attempts - 1:
                time.sleep(1 * (attempt + 1))
                continue
            raise
        except httpx.RequestError as exc:
            last = exc
            if attempt < attempts - 1:
                time.sleep(1 * (attempt + 1))
                continue
            raise
    if last is not None:
        raise last
    raise RuntimeError("el proveedor no respondio")


def classify_references(
    document: ParsedDocument, settings: Settings
) -> tuple[list[Finding], list[str]]:
    """Devuelve (hallazgos, avisos)."""
    bib = document.bibliography
    if not settings.ai_available or bib is None or not bib.references:
        return [], []

    payload = build_payload(bib)
    user_content = json.dumps(payload, ensure_ascii=False)

    if settings.provider == "gemini":
        body = {
            "system_instruction": {"parts": [{"text": SYSTEM_PROMPT}]},
            "contents": [{"parts": [{"text": user_content}]}],
            "generationConfig": {"temperature": 0.1, "responseMimeType": "application/json"},
        }
        url = f"{settings.base_url}/models/{settings.resolved_model}:generateContent"
        headers = {"x-goog-api-key": settings.resolved_key, "Content-Type": "application/json"}
    else:
        body = {
            "model": settings.resolved_model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            "temperature": 0.1,
            "response_format": {"type": "json_object"},
        }
        url = f"{settings.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {settings.resolved_key}",
            "Content-Type": "application/json",
        }

    try:
        data = _post_with_retry(url, body, headers)
        if settings.provider == "gemini":
            content = data["candidates"][0]["content"]["parts"][0]["text"]
        else:
            content = data["choices"][0]["message"]["content"]
        items = _extract_json(content.strip())
    except Exception as exc:
        logger.warning("Clasificacion IA fallo: %s", exc)
        return (
            [
                Finding(
                    rule_id=MODEL_IA,
                    category=Category.GENERAL,
                    severity=Severity.INFO,
                    message=(
                        "No se pudo completar la clasificacion de referencias por IA. "
                        "El resto de verificaciones se mantiene."
                    ),
                    location="IA",
                    extra={"ai_error": type(exc).__name__},
                )
            ],
["La revision por IA no se pudo ejecutar; el informe conserva el resto de reglas."],
        )

    findings: list[Finding] = []
    notes: list[str] = []
    for item in items:
        try:
            index = int(item.get("index"))
        except (TypeError, ValueError):
            continue
        if not (0 <= index < len(bib.references)):
            continue
        ref = bib.references[index]
        missing = item.get("missing") or []
        if isinstance(missing, str):
            missing = [missing]
        missing = [str(m).strip() for m in missing if str(m).strip()]
        if not missing:
            continue
        try:
            confidence = float(item.get("confidence", 0.5))
        except (TypeError, ValueError):
            confidence = 0.5
        suggestion = str(item.get("suggestion", "")).strip()
        rtype = str(item.get("type", ref.type_hint or "otro"))

        if confidence < MODEL_CONF_MIN:
            notes.append(
                f"{ref.label}: la IA sugiere {', '.join(missing[:3])} "
                f"(confianza {confidence:.0%}). Revisar manualmente."
            )
            continue

        findings.append(
            Finding(
                rule_id=MODEL_IA,
                category=Category.REFERENCIAS,
                severity=Severity.WARNING,
                message=(
                    f"Referencia de tipo '{rtype}': faltan {', '.join(missing[:4])}."
                ),
                suggestion=suggestion
                or f"Completar {', '.join(missing[:3])} segun APA 7 para una fuente tipo '{rtype}'.",
                paragraph_index=ref.paragraph_index,
                location=f"Pagina {ref.page} (Referencias)",
                excerpt=ref.raw[:160],
                extra={
                    "ai_source_type": rtype,
                    "ai_missing": missing,
                    "ai_confidence": confidence,
                    "bib_kind": "ai_missing_element",
                    "auto_fixable": False,
                },
            )
        )
    return findings, notes