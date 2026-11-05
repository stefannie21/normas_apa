"""Puerta determinista de precision (secciones 6, 7 y 8 del proyecto CEA).

Se ejecuta SIEMPRE, con o sin IA y con o sin clave de API. Ninguna observacion
puede llegar al editor o al informe Word sin pasar por aqui.

Etapas, en orden:

    0. Estado interno: solo FAIL es reportable. UNCERTAIN / NOT_APPLICABLE /
       PASS se registran en el ledger de auditoria y se descartan.
    1. Verificacion textual de apellidos (citation_guard): una observacion que
       nombra un autor que no esta escrito en el parrafo evaluado se descarta.
    2. Verificacion del fragmento: el `excerpt` debe corresponder a palabras
       reales del documento. Un fragmento inventado se descarta.
    3. Evidencia verificable: todo hallazgo debe tener un fragmento o una
       propiedad del documento que demuestre el incumplimiento, y esa propiedad
       debe existir en el ParsedDocument (parrafo, tabla, figura, seccion).
    4. Enriquecimiento uniforme: title, page, evidence, validation_status y
       sugerencia de correccion.
    5. Deduplicacion por (regla, parrafo, mensaje normalizado).

El modulo no consulta fuentes externas, ni historial de IA, ni ejemplos de
prompts: unica y exclusivamente el documento parseado.
"""
from __future__ import annotations

import logging
import re
from collections import Counter
from dataclasses import dataclass, field

from backend.app.rules.base import Finding
from backend.app.rules.status import ValidationLedger, ValidationStatus
from backend.app.services import citation_guard
from backend.app.services.bibliography import strip_accents

logger = logging.getLogger(__name__)

DEFAULT_SUGGESTION = (
    "Verificar el elemento señalado en el documento y ajustarlo a la norma APA 7 "
    "correspondiente."
)

# Cobertura minima de palabras del fragmento que deben existir en el documento.
# 0.6 deja pasar recortes con '...' y rotulos compuestos por dos parrafos, pero
# descarta fragmentos fabricados con vocabulario ajeno al documento.
MIN_EVIDENCE_COVERAGE = 0.6
MIN_EVIDENCE_WORDS = 4


@dataclass
class PrecisionResult:
    kept: list[Finding] = field(default_factory=list)
    discarded: list[Finding] = field(default_factory=list)
    reasons: dict[str, int] = field(default_factory=dict)
    ledger: ValidationLedger = field(default_factory=ValidationLedger)

    def _drop(self, finding: Finding, reason: str) -> None:
        self.discarded.append(finding)
        self.reasons[reason] = self.reasons.get(reason, 0) + 1
        finding.extra = dict(finding.extra or {})
        finding.extra["precision_dismiss_reason"] = reason
        logger.info("Hallazgo %s descartado: %s", finding.rule_id, reason)

    def to_dict(self) -> dict:
        return {
            "kept": len(self.kept),
            "discarded": len(self.discarded),
            "discard_reasons": dict(self.reasons),
        }


def _words(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", strip_accents(text or "").lower())


def _coverage(needle: list[str], haystack: Counter) -> float:
    if not needle:
        return 1.0
    present = sum(min(n, haystack[w]) for w, n in Counter(needle).items())
    return present / len(needle)


def _paragraphs(document) -> list:
    return list(getattr(document, "paragraphs", None) or [])


def _document_bag(paragraphs: list) -> Counter:
    bag: Counter = Counter()
    for p in paragraphs:
        bag.update(_words(getattr(p, "text", "")))
    return bag


def _paragraph_bag(paragraphs: list, index: int | None) -> Counter:
    if isinstance(index, int) and 0 <= index < len(paragraphs):
        return Counter(_words(getattr(paragraphs[index], "text", "")))
    return Counter()


def _excerpt_verifiable(
    finding: Finding,
    paragraphs: list,
    doc_bag: Counter,
) -> tuple[bool, str]:
    """El fragmento señalado debe corresponder al documento original.

    Primero se compara contra el parrafo indicado; si el rotulo se construyo con
    varios parrafos (tablas/figuras) se admite la comprobacion contra el texto
    completo del documento. En ningun caso se acepta un fragmento cuyo
    vocabulario no existe en el archivo analizado.
    """
    excerpt = (finding.excerpt or "").strip()
    if not excerpt:
        return True, ""
    words = _words(excerpt)
    if len(words) < MIN_EVIDENCE_WORDS:
        # Fragmentos muy cortos (p. ej. '(Garcia, 2020)') se controlan con la
        # verificacion de apellidos, que es mas estricta que la cobertura.
        return True, ""
    para_bag = _paragraph_bag(paragraphs, finding.paragraph_index)
    if para_bag and _coverage(words, para_bag) >= MIN_EVIDENCE_COVERAGE:
        return True, ""
    if _coverage(words, doc_bag) >= MIN_EVIDENCE_COVERAGE:
        return True, ""
    return False, "fragmento no verificable en el documento"


def _derive_evidence(finding: Finding, document, paragraphs: list) -> str:
    """Fragmento o propiedad que demuestra el incumplimiento."""
    if finding.evidence and finding.evidence.strip():
        return finding.evidence.strip()[:200]

    extra = finding.extra or {}
    kind = str(extra.get("evidence_kind") or "").lower()
    if kind == "table":
        return f"Tabla {extra.get('table_index', '?')} (w:tbl)"
    if kind == "figure":
        return f"Figura {extra.get('figure_index', '?')} (w:drawing)"
    if kind == "section":
        return f"Seccion {extra.get('section_index', '?')} (w:sectPr)"
    if kind == "document_property":
        return f"Propiedad del documento: {extra.get('property', 'estado global')}"

    location = (finding.location or "").strip()
    match = re.match(r"^(tabla|table)\s*(\d+)", location, re.IGNORECASE)
    if match:
        return f"Tabla {match.group(2)} (w:tbl)"
    match = re.match(r"^(figura|figure)\s*(\d+)", location, re.IGNORECASE)
    if match:
        return f"Figura {match.group(2)} (w:drawing)"

    excerpt = (finding.excerpt or "").strip()
    if excerpt:
        return excerpt[:200]

    idx = finding.paragraph_index
    if isinstance(idx, int) and 0 <= idx < len(paragraphs):
        text = (getattr(paragraphs[idx], "text", "") or "").strip()
        if text:
            return text[:200]

    if location and location not in {"Sistema", "IA"}:
        return f"Propiedad del documento: {location}"
    return "Documento completo (sin elemento localizable)"


def _evidence_verifiable(
    finding: Finding,
    evidence: str,
    document,
    paragraphs: list,
    doc_bag: Counter,
) -> tuple[bool, str]:
    match = re.match(r"^Tabla\s+(\d+)\s*\(w:tbl\)", evidence)
    if match:
        ok = any(t.index == int(match.group(1)) for t in (getattr(document, "tables", None) or []))
        return ok, "" if ok else "tabla inexistente en el documento"

    match = re.match(r"^Figura\s+(\d+)", evidence)
    if match:
        ok = any(t.index == int(match.group(1)) for t in (getattr(document, "figures", None) or []))
        return ok, "" if ok else "figura inexistente en el documento"

    if evidence.startswith("Parrafo ") or evidence.startswith("Párrafo "):
        idx = finding.paragraph_index
        ok = isinstance(idx, int) and 0 <= idx < len(paragraphs)
        return ok, "" if ok else "parrafo inexistente en el documento"

    if evidence.startswith("Propiedad del documento:") or evidence.startswith("Documento completo"):
        # Regla de nivel documento: la evidencia es el estado real parseado
        # (secciones, margenes, ausencia de la lista de referencias...).
        return True, ""

    words = _words(evidence)
    if len(words) < MIN_EVIDENCE_WORDS:
        return True, ""
    if _coverage(words, doc_bag) >= MIN_EVIDENCE_COVERAGE:
        return True, ""
    return False, "sin evidencia verificable"


def _page_for(finding: Finding, paragraphs: list) -> int | None:
    idx = finding.paragraph_index
    if isinstance(idx, int) and 0 <= idx < len(paragraphs):
        page = getattr(paragraphs[idx], "estimated_page", None)
        if isinstance(page, int):
            return page
    extra = finding.extra or {}
    if isinstance(extra.get("page"), int):
        return extra["page"]
    pages = extra.get("pages")
    if isinstance(pages, (list, tuple)) and pages:
        first = next((p for p in pages if isinstance(p, int)), None)
        if first is not None:
            return first
    match = re.search(r"P[áa]gina\s+(\d+)", finding.location or "", re.IGNORECASE)
    return int(match.group(1)) if match else None


def _dedupe_key(finding: Finding) -> tuple:
    return (
        finding.rule_id,
        finding.paragraph_index,
        tuple(_words(finding.message)[:16]),
    )


def _applicable(rule_id: str, document) -> bool:
    """NOT_APPLICABLE declarativo: la regla no corresponde al elemento."""
    tables = getattr(document, "tables", None) or []
    figures = getattr(document, "figures", None) or []
    bib = getattr(document, "bibliography", None)

    if rule_id == "HEAD-001":
        # Los encabezados son opcionales en APA 7: la regla no corresponde.
        return False
    if rule_id.startswith("TABLE-"):
        return bool(tables)
    if rule_id.startswith("FIG-"):
        return bool(figures)
    if rule_id.startswith("CRUCE-"):
        return bool(bib and bib.references_start is not None and bib.references)
    if rule_id in {"CIT-005", "CIT-006", "CIT-007", "CIT-008", "CIT-009", "CIT-010"}:
        return bool(bib and bib.references and bib.citations)
    if rule_id in {"REF-006", "REF-007", "REF-008"}:
        return bool(bib and bib.references)
    if rule_id in {"REF-002", "REF-003", "REF-004", "REF-005"}:
        return getattr(document, "references_start", None) is not None
    return True


def _build_ledger(
    rules: list,
    document,
    result: PrecisionResult,
    findings_before_gate: list[Finding],
) -> None:
    by_rule: dict[str, list[Finding]] = {}
    for f in findings_before_gate:
        by_rule.setdefault(f.rule_id, []).append(f)

    for rule in rules:
        produced = by_rule.get(rule.id, [])
        if not _applicable(rule.id, document):
            result.ledger.add(rule.id, ValidationStatus.NOT_APPLICABLE, "elemento no presente en el documento")
            continue
        if any(f.validation_status == ValidationStatus.FAIL for f in produced):
            kept = [f for f in result.kept if f.rule_id == rule.id]
            if kept:
                result.ledger.add(rule.id, ValidationStatus.FAIL, f"{len(kept)} incumplimiento(s) demostrado(s)")
            else:
                result.ledger.add(rule.id, ValidationStatus.UNCERTAIN, "hallazgos descartados por la puerta de precision")
            continue
        if any(f.validation_status == ValidationStatus.UNCERTAIN for f in produced):
            result.ledger.add(rule.id, ValidationStatus.UNCERTAIN, "evidencia insuficiente declarada por la regla")
            continue
        result.ledger.add(rule.id, ValidationStatus.PASS, "condicion verificable evaluada y cumplida")


def finalize(
    document,
    findings: list[Finding],
    rules: list | None = None,
    build_ledger: bool = True,
) -> PrecisionResult:
    """Aplica la puerta de precision y devuelve solo observaciones demostradas."""
    result = PrecisionResult()
    rule_list = list(rules or [])
    rules_by_id = {r.id: r for r in rule_list}
    paragraphs = _paragraphs(document)
    doc_bag = _document_bag(paragraphs)
    before_gate = list(findings)

    # 0. Solo FAIL puede aparecer como error/observacion en el informe.
    active: list[Finding] = []
    for f in findings:
        if f.validation_status == ValidationStatus.FAIL:
            active.append(f)
        else:
            result._drop(f, f"estado interno no reportable: {f.validation_status.value}")

    # 1. Apellidos inventados: verificacion textual ya existente, sin IA.
    verified = citation_guard.verify(document, active)
    for f in verified.discarded:
        result._drop(f, citation_guard.DISMISS_REASON)
    active = verified.kept

    # 2. El fragmento debe corresponder al documento original.
    stage: list[Finding] = []
    for f in active:
        ok, reason = _excerpt_verifiable(f, paragraphs, doc_bag)
        if ok:
            stage.append(f)
        else:
            result._drop(f, reason)

    # 3. Toda observacion debe apoyarse en evidencia verificable.
    with_evidence: list[Finding] = []
    for f in stage:
        evidence = _derive_evidence(f, document, paragraphs)
        ok, reason = _evidence_verifiable(f, evidence, document, paragraphs, doc_bag)
        if not ok:
            result._drop(f, reason)
            continue
        f.evidence = evidence
        with_evidence.append(f)

    # 4. Estructura uniforme.
    for f in with_evidence:
        if not f.title:
            rule = rules_by_id.get(f.rule_id)
            f.title = rule.name if rule is not None else f.rule_id
        if f.page is None:
            f.page = _page_for(f, paragraphs)
        if not (f.suggestion or "").strip():
            f.suggestion = DEFAULT_SUGGESTION
        f.validation_status = ValidationStatus.FAIL

    # 5. Deduplicacion.
    seen: set[tuple] = set()
    for f in with_evidence:
        key = _dedupe_key(f)
        if key in seen:
            result._drop(f, "observacion repetida")
            continue
        seen.add(key)
        result.kept.append(f)

    if build_ledger and rule_list:
        _build_ledger(rule_list, document, result, before_gate)

    return result
