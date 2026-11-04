"""Verificacion textual determinista de las observaciones sobre citas.

Regla estricta, aplicada en codigo y NUNCA delegada a la IA:

    Se analiza unicamente el texto escrito en el documento. Antes de mostrar
    una observacion sobre una cita o referencia se comprueba que el apellido
    del autor mencionado en la observacion aparece literalmente en el parrafo
    que se esta evaluando. Si no aparece, la observacion se descarta.

El apellido se toma de los metadatos del hallazgo (`extra`) o del propio
mensaje (las observaciones de la IA no traen metadatos). El `excerpt` solo
aporta el apellido que hay que buscar como ultimo recurso: JAMAS se usa como
prueba de que el autor existe, porque podria haber sido inventado.

No hay llamadas a ningun proveedor: esta comprobacion se ejecuta siempre,
incluso cuando la revision por IA esta desactivada o falla.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

from backend.app.rules.base import Finding
from backend.app.services.bibliography import author_tokens, strip_accents

logger = logging.getLogger(__name__)

DISMISS_REASON = "apellido no presente en el texto del parrafo evaluado"

# Letra inicial en mayuscula: evita confundir conectores ('Segun', 'La cita')
# con apellidos. Las particulas se permiten dentro del bloque ('De la Cruz').
_CAP = r"[A-ZÁÉÍÓÚÑÜ]"
_LETTERS = r"[A-Za-zÁÉÍÓÚÑÜáéíóúñü'’\-]"
_NAME = _CAP + _LETTERS + r"*"
_PARTICLE = r"(?:de|del|la|los|las|van|von|der|den|da|dos|di|y|e|&)"
_YEAR = r"(?:1[5-9]\d{2}|20\d{2}|s\.?f\.?|n\.?d\.?)"

# 'Hadi (2023)', '(Hadi, 2023)', 'Garcia y Lopez (2020)', 'Ramos et al. (2021)'
_CLAIMED_AUTHOR_RE = re.compile(
    rf"(?P<author>{_NAME}(?:\s+(?:{_PARTICLE}\s+)?{_NAME})*)"
    rf"\s*(?:et\s+al\.?\s*)?(?:\(|,\s*|\s+)\s*{_YEAR}",
)


@dataclass
class Verification:
    kept: list[Finding] = field(default_factory=list)
    discarded: list[Finding] = field(default_factory=list)


def _words(text: str) -> list[str]:
    """Texto real del documento reducido a palabras comparables."""
    return re.findall(r"[a-z0-9]+", strip_accents(text or "").lower())


def _authors_in(text: str) -> list[str]:
    return [m.group("author") for m in _CLAIMED_AUTHOR_RE.finditer(text or "")]


def _claimed_surnames(f: Finding) -> list[str]:
    """Apellidos que la observacion afirma que existen, por orden de fiabilidad.

    1. Metadatos estructurados del motor de reglas (`surname` / `surnames`).
    2. El mensaje de la observacion (aqui es donde la IA puede inventar autores).
    3. El fragmento citado, solo si no hay nada mas.

    Se devuelve una sola capa: comprobarla entera evita que un autor real del
    fragmento 'salve' una observacion cuyo mensaje nombra a otro autor falso.
    """
    extra = f.extra or {}

    structured: list[str] = []
    single = extra.get("surname")
    if isinstance(single, str) and single.strip():
        structured.append(single)
    many = extra.get("surnames")
    if isinstance(many, (list, tuple)):
        structured.extend(str(s) for s in many if isinstance(s, str) and s.strip())
    if structured:
        return _unique(structured)

    from_message = _authors_in(f.message)
    if from_message:
        return _unique(from_message)

    return _unique(_authors_in(f.excerpt))


def _unique(values: list[str]) -> list[str]:
    out: list[str] = []
    for value in values:
        value = str(value).strip()
        if value and value not in out:
            out.append(value)
    return out


def _contains(haystack: list[str], needle: list[str]) -> bool:
    n = len(needle)
    return any(haystack[i : i + n] == needle for i in range(len(haystack) - n + 1))


def _appears(surname: str, haystack: list[str]) -> bool:
    """El apellido (o su bloque de apellidos) esta escrito literalmente.

    Se comparan palabras completas: 'Hadi' NO coincide con 'Hadid'. En
    apellidos compuestos basta el apellido principal ('Estrada' en
    'Estrada Frias') porque en las citas suele abreviarse con 'et al.'.
    """
    wanted = author_tokens(surname)
    if not wanted:
        return False
    if _contains(haystack, wanted):
        return True
    return any(len(w) >= 4 and w in haystack for w in wanted)


def verify(document, findings: list[Finding]) -> Verification:
    """Descarta las observaciones de cita cuyo apellido no esta en el texto.

    El alcance es el parrafo evaluado (`paragraph_index`); solo cuando no hay
    parrafo localizable se usa el texto completo del documento. No se consulta
    ninguna otra fuente: ni la lista de referencias de otros documentos, ni
    ejemplos, ni el historial de la IA.
    """
    result = Verification()
    paragraphs = list(getattr(document, "paragraphs", None) or [])
    full_words = _words("\n".join(getattr(p, "text", "") for p in paragraphs))
    by_paragraph: dict[int, list[str]] = {}

    for f in findings:
        claimed = _claimed_surnames(f)
        if not claimed:
            # La observacion no nombra ningun autor: no hay nada que verificar.
            result.kept.append(f)
            continue

        idx = f.paragraph_index
        if isinstance(idx, int) and 0 <= idx < len(paragraphs):
            if idx not in by_paragraph:
                by_paragraph[idx] = _words(getattr(paragraphs[idx], "text", ""))
            haystack = by_paragraph[idx] or full_words
        else:
            haystack = full_words

        if any(_appears(surname, haystack) for surname in claimed):
            result.kept.append(f)
        else:
            f.extra = dict(f.extra or {})
            f.extra["deterministic_dismiss_reason"] = DISMISS_REASON
            result.discarded.append(f)
            logger.info(
                "Observacion %s descartada: %s no aparece en el texto (%s)",
                f.rule_id,
                ", ".join(claimed[:3]),
                DISMISS_REASON,
            )

    return result
