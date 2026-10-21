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
# Para el caso "discrepancia" (sin hallazgos deterministas pero la IA detecta
# un elemento ausente) se exige mayor confianza para no generar ruido.
DISCREPANCY_CONF_MIN = 0.75

# Vocabulario cerrado para 'missing'. El modelo solo puede informar de estas
# carencias: cualquier otra cadena se descarta, de modo que la IA no introduce
# categorias inventadas ni hallazgos fuera del alcance de la herramienta.
MISSING_CATEGORIES = (
    "autoría",
    "fecha",
    "título",
    "fuente",
    "editorial",
    "volumen",
    "número",
    "páginas",
    "doi_url",
    "edición",
    "traducción",
)

# Alias que el modelo suele devolver -> categoria canonica del vocabulario.
_MISSING_ALIASES = {
    "autor": "autoría",
    "autores": "autoría",
    "autoria": "autoría",
    "año": "fecha",
    "ano": "fecha",
    "anio": "fecha",
    "fecha de publicacion": "fecha",
    "titulo": "título",
    "nombre": "título",
    "fuente o contenedor": "fuente",
    "contenedor": "fuente",
    "revista": "fuente",
    "publicacion": "fuente",
    "editor": "editorial",
    "editora": "editorial",
    "vol": "volumen",
    "tomo": "volumen",
    "num": "número",
    "numero": "número",
    "issue": "número",
    "pagina": "páginas",
    "paginas": "páginas",
    "pags": "páginas",
    "doi": "doi_url",
    "url": "doi_url",
    "enlace": "doi_url",
    "doi o url": "doi_url",
    "edicion": "edición",
    "traduccion": "traducción",
}


def normalize_missing(values) -> list[str]:
    """Deja solo categorias del vocabulario cerrado, en orden y sin repetir."""
    if isinstance(values, str):
        values = [values]
    out: list[str] = []
    for raw in values or []:
        key = str(raw).strip().lower()
        if not key:
            continue
        canon = key if key in MISSING_CATEGORIES else _MISSING_ALIASES.get(key)
        if canon and canon not in out:
            out.append(canon)
    return out

SYSTEM_PROMPT = (
    "Eres un asesor experto en normas APA (7.a edición). Recibes un arreglo JSON con "
    "las citas del texto y las entradas de la lista de referencias de una tesis. "
    "Para CADA referencia determina: (1) 'type' entre articulo, libro, capitulo, "
    "tesis, informe, web, otro; (2) 'missing': elementos APA ausentes según ese tipo "
    "de fuente; (3) 'suggestion': corrección concreta; (4) 'confidence' de 0 a 1. "
    "REGLAS DE 'et al.' (APA 7) que debes verificar en las citas: con 1 o 2 autores "
    "NUNCA se usa 'et al.'; se nombran siempre todos los autores en todas las "
    "menciones. El separador depende de la forma de la cita: dentro de un paréntesis "
    "se une con el símbolo '&' (p. ej. '(Pérez & Gómez, 2023)'); en una cita "
    "narrativa, donde los autores forman parte de la oración, se une con 'y' en "
    "español o 'and' en inglés (p. ej. 'Pérez y Gómez (2023)'). Usar 'y' dentro del "
    "paréntesis, o '&' en la narrativa, es un error. Con 3 o más autores se usa "
    "'et al.' desde la primera mención (p. ej. '(Martínez et al., 2022)'). Si una "
    "cita incumple esto, inclúyelo en 'missing'. "
    "No inventes datos que no estén en la entrada. Responde SOLO con un arreglo JSON "
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


def summarize_payload(bib: Bibliography | None) -> dict:
    """Resumen del payload que se enviaria, SIN llamar al proveedor de IA.

    Sirve para que la persona vea exactamente que datos salen del equipo antes
    de dar su consentimiento. No incluye texto del documento: solo recuentos y
    el alcance (cuantos caracteres como maximo, cuantas entradas).
    """
    if bib is None:
        return {
            "references": 0,
            "citations": 0,
            "chars_max": 0,
            "sends_full_document": False,
            "fields": [],
            "model": "",
        }
    payload = build_payload(bib)
    refs = payload["referencias"]
    cites = payload["citas"]
    # campos que viajan por cada referencia/cita, para mostrarlos en la vista previa
    ref_fields = list(refs[0].keys()) if refs else [
        "index", "texto", "autores", "anio", "tipo_detectado", "cursivas", "titulo", "contenedor",
    ]
    cite_fields = list(cites[0].keys()) if cites else ["texto", "anio", "autores", "forma"]
    # cota superior del tamaño real que se enviaria (json compacto, sin acentos escapados)
    chars_max = len(json.dumps(payload, ensure_ascii=False))
    return {
        "references": len(refs),
        "citations": len(cites),
        "chars_max": chars_max,
        "sends_full_document": False,
        "fields": ref_fields + [f"cita.{f}" for f in cite_fields],
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
    raise RuntimeError("el proveedor no respondió")


def _build_request(settings: Settings, model: str, user_content: str) -> tuple[dict, dict]:
    """Construye (url, headers, body) para un modelo concreto de la cascada."""
    if settings.provider == "gemini":
        body = {
            "system_instruction": {"parts": [{"text": SYSTEM_PROMPT}]},
            "contents": [{"parts": [{"text": user_content}]}],
            "generationConfig": {"temperature": 0.1, "responseMimeType": "application/json"},
        }
        url = f"{settings.base_url}/models/{model}:generateContent"
        headers = {"x-goog-api-key": settings.resolved_key, "Content-Type": "application/json"}
    else:
        body = {
            "model": model,
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
    return url, headers, body


def _request_with_cascade(settings: Settings, user_content: str) -> tuple[list[dict], str, str | None]:
    """Intenta cada modelo de la cascada en orden.

    Devuelve (items, modelo_usado, error). Si un modelo falla (no existe, cuota
    agotada, error del proveedor) se pasa al siguiente. El ultimo error se
    devuelve si ninguno responde.
    """
    models = settings.model_cascade
    last_error: str | None = None
    for model in models:
        url, headers, body = _build_request(settings, model, user_content)
        try:
            data = _post_with_retry(url, body, headers)
            if settings.provider == "gemini":
                content = data["candidates"][0]["content"]["parts"][0]["text"]
            else:
                content = data["choices"][0]["message"]["content"]
            items = _extract_json(content.strip())
            logger.info("Revisión IA completada con el modelo %s", model)
            return items, model, None
        except Exception as exc:
            last_error = f"{model}: {exc}"
            logger.warning(
                "Modelo IA %s falló (%s); se prueba el siguiente de la cascada", model, exc
            )
            continue
    return [], models[-1] if models else "", last_error


def classify_references(
    document: ParsedDocument, settings: Settings, rule_findings: list[Finding] | None = None
) -> tuple[list[Finding], list[str], str]:
    """Devuelve (hallazgos, avisos, modelo_usado)."""
    bib = document.bibliography
    if not settings.ai_available or bib is None or not bib.references:
        return [], [], ""

    payload = build_payload(bib)
    user_content = json.dumps(payload, ensure_ascii=False)

    items, used_model, error = _request_with_cascade(settings, user_content)
    if error is not None:
        logger.warning("Clasificación IA falló en toda la cascada: %s", error)
        return (
            [
                Finding(
                    rule_id=MODEL_IA,
                    category=Category.GENERAL,
                    severity=Severity.INFO,
                    message=(
                        "No se pudo completar la clasificación de referencias por IA. "
                        "El resto de verificaciones se mantiene."
                    ),
                    location="IA",
                    extra={"ai_error": error, "models_tried": settings.model_cascade},
                )
            ],
            ["La revisión por IA no se pudo ejecutar; el informe conserva el resto de reglas."],
            "",
        )

    # Contraste con reglas deterministas: por referencia (paragraph_index)
    covered = set()
    if rule_findings:
        for f in rule_findings:
            if f.paragraph_index is not None:
                covered.add(f.paragraph_index)

    findings: list[Finding] = []
    notes: list[str] = []
    if used_model:
        notes.append(f"Revisión IA ejecutada con el modelo {used_model}.")
    for item in items:
        try:
            index = int(item.get("index"))
        except (TypeError, ValueError):
            continue
        if not (0 <= index < len(bib.references)):
            continue
        ref = bib.references[index]
        missing = normalize_missing(item.get("missing"))
        if not missing:
            continue
        try:
            confidence = float(item.get("confidence", 0.5))
        except (TypeError, ValueError):
            confidence = 0.5
        suggestion = str(item.get("suggestion", "")).strip()
        rtype = str(item.get("type", ref.type_hint or "otro"))

        has_rule_coverage = ref.paragraph_index is not None and ref.paragraph_index in covered
        discrepancy = not has_rule_coverage

        if confidence < MODEL_CONF_MIN:
            notes.append(
                f"{ref.label}: la IA sugiere {', '.join(missing[:3])} "
                f"(confianza {confidence:.0%}). Revisar manualmente."
            )
            continue

        # Si no hay hallazgos deterministas para esa referencia, exigir mayor
        # confianza (>= 0.75) para evitar ruido.
        if discrepancy and confidence < DISCREPANCY_CONF_MIN:
            notes.append(
                f"{ref.label}: posible elemento ausente según la IA "
                f"({', '.join(missing[:3])}, confianza {confidence:.0%} < 75%). "
                f"Sin coincidencia con las reglas deterministas; requiere revisión manual."
            )
            continue

        if discrepancy:
            findings.append(
                Finding(
                    rule_id=MODEL_IA,
                    category=Category.REFERENCIAS,
                    severity=Severity.WARNING,
                    message=(
                        f"Discrepancia: referencia de tipo '{rtype}' sin hallazgos de las "
                        f"reglas deterministas, pero la IA detecta elementos ausentes: "
                        f"{', '.join(missing[:4])}."
                    ),
                    suggestion=suggestion
                    or f"Completar {', '.join(missing[:3])} según APA 7 para una fuente tipo '{rtype}'.",
                    paragraph_index=ref.paragraph_index,
                    location=f"Página {ref.page} (Referencias)",
                    excerpt=ref.raw[:160],
                    extra={
                        "ai_source_type": rtype,
                        "ai_missing": missing,
                        "ai_confidence": confidence,
                        "ai_model": used_model,
                        "bib_kind": "ai_missing_element",
                        "ai_discrepancy": True,
                        "auto_fixable": False,
                    },
                )
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
                or f"Completar {', '.join(missing[:3])} según APA 7 para una fuente tipo '{rtype}'.",
                paragraph_index=ref.paragraph_index,
                location=f"Página {ref.page} (Referencias)",
                excerpt=ref.raw[:160],
                extra={
                    "ai_source_type": rtype,
                    "ai_missing": missing,
                    "ai_confidence": confidence,
                    "ai_model": used_model,
                    "bib_kind": "ai_missing_element",
                    "ai_discrepancy": False,
                    "auto_fixable": False,
                },
            )
        )
    return findings, notes, used_model
