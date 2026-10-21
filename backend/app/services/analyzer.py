from __future__ import annotations

from dataclasses import dataclass, field

from backend.app.rules.base import Finding, Severity
from backend.app.rules.registry import get_rules
from backend.app.services.docx_parser import ParsedDocument


@dataclass
class AnalysisResult:
    filename: str
    findings: list[Finding] = field(default_factory=list)
    summary: dict = field(default_factory=dict)
    # avisos de la capa IA (modelo usado, notas). Se rellena cuando se fusiona la
    # revision por IA; el informe los usa para la seccion de auditoria.
    ai_notes: list[str] = field(default_factory=list)


def analyze(document: ParsedDocument) -> AnalysisResult:
    findings: list[Finding] = []
    for rule in get_rules():
        try:
            findings.extend(rule.check(document))
        except Exception as exc:  # una regla no debe romper el analisis completo
            findings.append(
                Finding(
                    rule_id=rule.id,
                    category=rule.category,
                    severity=Severity.INFO,
                    message=f"La regla '{rule.name}' no pudo ejecutarse: {exc}",
                    location="Sistema",
                )
            )

    findings.sort(key=lambda f: (f.paragraph_index if f.paragraph_index is not None else 10**9, f.rule_id))
    result = AnalysisResult(filename=document.filename, findings=findings)
    result.summary = build_summary(document, findings)
    return result


def build_summary(document: ParsedDocument, findings: list[Finding]) -> dict:
    by_severity = {s.value: 0 for s in Severity}
    by_category: dict[str, int] = {}
    for f in findings:
        by_severity[f.severity.value] += 1
        by_category[f.category.value] = by_category.get(f.category.value, 0) + 1

    total_paras = len(document.body_paragraphs)

    # El score mide la proporcion de PARRAFOS con problemas, con un tope por
    # documento para que un unico error no baje un 100% y para que las reglas de
    # documento (margenes, fuentes) no hundan la nota por si solas.
    errors = by_severity[Severity.ERROR.value]
    warnings = by_severity[Severity.WARNING.value]
    infos = by_severity[Severity.INFO.value]

    doc_level = document_level_penalty(errors, warnings, infos)
    per_paragraph = ((errors * 1.0 + warnings * 0.4 + infos * 0.1) / max(total_paras, 1)) * 100.0
    per_paragraph = min(100.0, per_paragraph)
    score = max(0, min(100, round(100 - doc_level - per_paragraph)))

    return {
        "total_findings": len(findings),
        "by_severity": by_severity,
        "by_category": by_category,
        "paragraphs": total_paras,
        "has_references_section": document.references_start is not None,
        "compliance_score": score,
    }


def document_level_penalty(errors: int, warnings: int, infos: int) -> float:
    """Penalizacion por problemas que afectan a todo el documento."""
    penalty = min(35.0, errors * 4.0) + min(25.0, warnings * 1.5) + min(10.0, infos * 0.5)
    return penalty
