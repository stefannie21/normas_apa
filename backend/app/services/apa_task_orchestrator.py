"""Orquestador central de tareas APA con IA especializada y anclaje (Fases 2, 7, 8 y 9).

Nombre sugerido por la especificación: apa_task_orchestrator.py

Responsabilidades:
1. Recibir el documento previamente extraído (ParsedDocument).
2. Ejecutar tareas deterministas en Python (37 reglas activas).
3. Identificar tareas candidatas para IA especializada (citas complejas, referencias,
   propuestas de corrección, jerarquía contextual).
4. Preparar únicamente el contexto necesario y acotado para cada especialista.
5. Ejecutar especialistas independientes en paralelo cuando corresponda.
6. Validar respuestas JSON mediante esquemas Pydantic estrictos.
7. Crear anclajes exactos (paragraph_id, start_offset, end_offset, fragment_hash).
8. Validación final mediante Python (citation_guard y precision.py):
   la IA NUNCA aprueba sus propios hallazgos.
9. Deduplicar y consolidar observaciones aprobadas.
10. Caché inteligente por versión del documento y hash de tarea.
"""
from __future__ import annotations

import concurrent.futures
import hashlib
import logging
import time
from dataclasses import dataclass, field
from typing import Any

from backend.app.config import get_settings
from backend.app.models.apa_models import AnchorModel, EvidenceModel, StructuredFindingModel
from backend.app.rules.base import Category, Finding, Severity
from backend.app.rules.registry import get_rules
from backend.app.services import precision
from backend.app.services.ai_specialists import (
    ComplexCitationSpecialist,
    CorrectionProposalSpecialist,
    ReferenceContextSpecialist,
    StructuralContextSpecialist,
)
from backend.app.services.analyzer import analyze
from backend.app.services.citation_guard import verify as verify_citations
from backend.app.services.comment_anchor_manager import (
    CommentAnchorManager,
    anchor_manager,
    normalize_text,
    sha256_hash,
)
from backend.app.services.docx_parser import ParagraphInfo, ParsedDocument

logger = logging.getLogger(__name__)


@dataclass
class TaskMetrics:
    """Métricas de rendimiento y consumo de recursos por tarea."""

    task_name: str
    engine: str  # "Python" o "IA"
    elapsed_sec: float = 0.0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    findings_count: int = 0


@dataclass
class OrchestrationResult:
    """Resultado integral de la orquestación de tareas y anclaje."""

    document_id: str
    document_version: str
    findings: list[Finding] = field(default_factory=list)
    structured_findings: list[StructuredFindingModel] = field(default_factory=list)
    anchors: list[AnchorModel] = field(default_factory=list)
    metrics: list[TaskMetrics] = field(default_factory=list)
    summary: dict[str, Any] = field(default_factory=dict)
    discarded: list[Finding] = field(default_factory=list)
    validation: dict[str, Any] = field(default_factory=dict)
    total_elapsed_sec: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "document_id": self.document_id,
            "document_version": self.document_version,
            "findings": [f.to_dict() for f in self.findings],
            "total_findings": len(self.findings),
            "summary": self.summary,
            "metrics": [
                {
                    "task_name": m.task_name,
                    "engine": m.engine,
                    "elapsed_sec": m.elapsed_sec,
                    "prompt_tokens": m.prompt_tokens,
                    "completion_tokens": m.completion_tokens,
                    "findings_count": m.findings_count,
                }
                for m in self.metrics
            ],
            "validation": self.validation,
            "total_elapsed_sec": self.total_elapsed_sec,
        }


class ApaTaskOrchestrator:
    """Orquestador central de análisis APA por tareas especializadas."""

    def __init__(self, anchor_mgr: CommentAnchorManager | None = None) -> None:
        self.anchor_manager = anchor_mgr or anchor_manager
        self.citation_specialist = ComplexCitationSpecialist()
        self.reference_specialist = ReferenceContextSpecialist()
        self.correction_specialist = CorrectionProposalSpecialist()
        self.structural_specialist = StructuralContextSpecialist()
        # Caché: key -> list[StructuredFindingModel]
        self._task_cache: dict[str, list[StructuredFindingModel]] = {}

    def _cache_key(self, doc_hash: str, task_id: str, context_str: str) -> str:
        ctx_hash = hashlib.sha256(context_str.encode("utf-8")).hexdigest()[:16]
        return f"{doc_hash}_{task_id}_{ctx_hash}"

    def orchestrate(
        self,
        document: ParsedDocument,
        document_id: str = "doc_default",
        document_version: str = "1.0",
        enable_ai: bool | None = None,
    ) -> OrchestrationResult:
        """Ejecuta el flujo completo de análisis por tareas y anclaje."""
        t_start = time.time()
        settings = get_settings()
        use_ai = settings.ai_available if enable_ai is None else enable_ai

        metrics: list[TaskMetrics] = []

        # 1. Registro y mapa de párrafos
        doc_raw_text = "".join(p.text for p in document.paragraphs)
        doc_hash = hashlib.sha256(doc_raw_text.encode("utf-8")).hexdigest()
        para_map = self.anchor_manager.build_paragraph_map(document, document_id, document_version)

        # 2. Motor determinista en Python (Fase 1: reglas históricas y nuevas)
        t0_py = time.time()
        rule_result = analyze(document)
        t_py_elapsed = round(time.time() - t0_py, 3)

        metrics.append(
            TaskMetrics(
                task_name="Python Deterministic Rules (37 reglas)",
                engine="Python",
                elapsed_sec=t_py_elapsed,
                findings_count=len(rule_result.findings),
            )
        )

        # Convertir hallazgos deterministas en StructuredFindingModel con anclajes
        structured_findings: list[StructuredFindingModel] = []
        for f in rule_result.findings:
            p = None
            if f.paragraph_index is not None and 0 <= f.paragraph_index < len(document.paragraphs):
                p = document.paragraphs[f.paragraph_index]

            if p is not None:
                anchor = self.anchor_manager.create_anchor(
                    p=p,
                    matched_text=f.excerpt or p.text[:80],
                    document_id=document_id,
                    document_version=document_version,
                )
            else:
                # Anclaje general a nivel de documento
                anchor = AnchorModel(
                    document_id=document_id,
                    document_version=document_version,
                    paragraph_id="doc_general",
                    paragraph_index=0,
                    start_offset=0,
                    end_offset=1,
                    matched_text=f.excerpt or "Documento",
                    fragment_hash=sha256_hash(f.excerpt or "doc"),
                )

            # Asociar el anclaje directamente al objeto Finding
            f.anchor = anchor.model_dump()

            cat_str = f.category.value if hasattr(f.category, "value") else str(f.category)
            sev_str = f.severity.value if hasattr(f.severity, "value") else str(f.severity)

            structured_findings.append(
                StructuredFindingModel(
                    task_id="python_deterministic_rule",
                    rule_id=f.rule_id,
                    category=cat_str,
                    status="FAIL",
                    severity=sev_str,
                    title=f.title or f.rule_id,
                    message=f.message,
                    suggestion=f.suggestion,
                    evidence=EvidenceModel(
                        original_text=f.excerpt or f.message,
                        reason=f"Regla determinista {f.rule_id}",
                    ),
                    anchor=anchor,
                    confidence=1.0,
                    extra=f.extra,
                )
            )

        # 3. Tareas especializadas con IA (si está habilitada y autorizada)
        if use_ai:
            ai_findings = self._run_ai_specialists(
                document=document,
                document_id=document_id,
                document_version=document_version,
                doc_hash=doc_hash,
                metrics=metrics,
            )
            structured_findings.extend(ai_findings)

        # 4. Especialista en propuestas de corrección (enriquece sugerencias de hallazgos existentes)
        if use_ai and structured_findings:
            t0_corr = time.time()
            structured_findings = self.correction_specialist.run(structured_findings)
            metrics.append(
                TaskMetrics(
                    task_name="Correction Proposal Specialist",
                    engine="IA",
                    elapsed_sec=round(time.time() - t0_corr, 3),
                    prompt_tokens=self.correction_specialist.last_prompt_tokens,
                    completion_tokens=self.correction_specialist.last_completion_tokens,
                    findings_count=0,
                )
            )

        # 5. Validación final mediante Python (Fase 7)
        # La IA no puede aprobar sus propias observaciones
        validated_findings, discarded_findings = self._final_python_validation(
            document=document,
            findings=structured_findings,
        )

        # 6. Deduplicación por (rule_id, paragraph_id, matched_text)
        deduped: list[Finding] = []
        seen = set()
        for f in validated_findings:
            anc = f.anchor or {}
            key = (
                f.rule_id,
                anc.get("paragraph_id", f.paragraph_index),
                normalize_text(anc.get("matched_text", f.excerpt))[:40],
            )
            if key not in seen:
                seen.add(key)
                deduped.append(f)

        # Registrar versión en el historial de anclajes
        anchors_list = [
            AnchorModel(**f.anchor) for f in deduped if f.anchor and isinstance(f.anchor, dict)
        ]
        self.anchor_manager.record_analysis_version(
            document_id=document_id,
            document_version=document_version,
            document=document,
            anchors=anchors_list,
        )

        total_elapsed = round(time.time() - t_start, 3)

        return OrchestrationResult(
            document_id=document_id,
            document_version=document_version,
            findings=deduped,
            structured_findings=[sf for sf in structured_findings if sf.status == "FAIL"],
            anchors=anchors_list,
            metrics=metrics,
            summary=rule_result.summary,
            discarded=discarded_findings,
            validation=rule_result.validation,
            total_elapsed_sec=total_elapsed,
        )

    def _run_ai_specialists(
        self,
        document: ParsedDocument,
        document_id: str,
        document_version: str,
        doc_hash: str,
        metrics: list[TaskMetrics],
    ) -> list[StructuredFindingModel]:
        """Ejecuta los especialistas de IA de forma acotada y paralela."""
        results: list[StructuredFindingModel] = []

        # Tarea A: Citas complejas (solo párrafos con paréntesis múltiples o 'citado en')
        citation_candidates = [
            p
            for p in document.body_paragraphs
            if ";" in p.text and "(" in p.text
            or "citado en" in p.text.lower()
            or "et al" in p.text.lower()
        ]

        # Tarea B: Evaluación contextual de referencias
        has_refs = bool(document.reference_paragraphs())

        # Tarea C: Encabezados ambiguos (candidatos de HEAD-004)
        heading_candidates = [
            p
            for p in document.body_paragraphs
            if not p.heading_level and p.all_bold and len(p.text.split()) < 12 and not p.in_table
        ]

        def exec_citations():
            if not citation_candidates:
                return []
            key = self._cache_key(
                doc_hash,
                "complex_citations",
                "".join(p.text[:40] for p in citation_candidates[:10]),
            )
            if key in self._task_cache:
                return self._task_cache[key]
            res = self.citation_specialist.run(
                document=document,
                candidate_paragraphs=citation_candidates[:10],
                document_id=document_id,
                document_version=document_version,
            )
            self._task_cache[key] = res
            return res

        def exec_refs():
            if not has_refs:
                return []
            ref_snippet = "".join(p.text[:40] for p in document.reference_paragraphs()[:15])
            key = self._cache_key(doc_hash, "refs_context", ref_snippet)
            if key in self._task_cache:
                return self._task_cache[key]
            res = self.reference_specialist.run(
                document=document,
                document_id=document_id,
                document_version=document_version,
            )
            self._task_cache[key] = res
            return res

        def exec_headings():
            if not heading_candidates:
                return []
            h_snippet = "".join(p.text[:40] for p in heading_candidates[:8])
            key = self._cache_key(doc_hash, "structural_headings", h_snippet)
            if key in self._task_cache:
                return self._task_cache[key]
            res = self.structural_specialist.run(
                document=document,
                candidate_headings=heading_candidates[:8],
                document_id=document_id,
                document_version=document_version,
            )
            self._task_cache[key] = res
            return res

        # Ejecución concurrente de especialistas independientes
        t0 = time.time()
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            f_cit = executor.submit(exec_citations)
            f_refs = executor.submit(exec_refs)
            f_head = executor.submit(exec_headings)

            cit_res = f_cit.result()
            refs_res = f_refs.result()
            head_res = f_head.result()

        results.extend(cit_res)
        results.extend(refs_res)
        results.extend(head_res)

        elapsed = round(time.time() - t0, 3)
        metrics.append(
            TaskMetrics(
                task_name="AI Specialists Parallel Execution",
                engine="IA",
                elapsed_sec=elapsed,
                prompt_tokens=(
                    self.citation_specialist.last_prompt_tokens
                    + self.reference_specialist.last_prompt_tokens
                    + self.structural_specialist.last_prompt_tokens
                ),
                completion_tokens=(
                    self.citation_specialist.last_completion_tokens
                    + self.reference_specialist.last_completion_tokens
                    + self.structural_specialist.last_completion_tokens
                ),
                findings_count=len(results),
            )
        )
        return results

    def _final_python_validation(
        self,
        document: ParsedDocument,
        findings: list[StructuredFindingModel],
    ) -> tuple[list[Finding], list[Finding]]:
        """Validación final determinista estricta en Python (Fase 7)."""
        valid_rules = {r.id for r in get_rules()}
        legacy_findings: list[Finding] = []

        for sf in findings:
            # 1. Regla existe en el catálogo activo
            if sf.rule_id not in valid_rules:
                continue

            # 2. Offsets e integridad del anclaje
            anc = sf.anchor
            if anc.start_offset >= anc.end_offset:
                continue

            # 3. Párrafo existe en el documento
            if anc.paragraph_index >= len(document.paragraphs):
                continue
            p = document.paragraphs[anc.paragraph_index]

            # 4. Fragmento existe en el párrafo
            if normalize_text(anc.matched_text) not in normalize_text(p.text):
                continue

            cat_enum = Category.GENERAL
            for c in Category:
                if c.value == sf.category or c.name == sf.category:
                    cat_enum = c
                    break

            sev_enum = Severity.WARNING
            for s in Severity:
                if s.value == sf.severity:
                    sev_enum = s
                    break

            f = Finding(
                rule_id=sf.rule_id,
                category=cat_enum,
                severity=sev_enum,
                message=sf.message,
                suggestion=sf.suggestion,
                paragraph_index=anc.paragraph_index,
                location=f"Párrafo {anc.paragraph_index + 1}",
                excerpt=anc.matched_text,
                extra={**sf.extra, "task_id": sf.task_id, "confidence": sf.confidence},
                title=sf.title,
                evidence=sf.evidence.original_text,
                validation_status=sf.status,
                anchor=anc.model_dump(),
            )
            legacy_findings.append(f)

        # 5. Filtro textual determinista contra alucinación de autores
        guard_result = verify_citations(document, legacy_findings)
        kept = guard_result.kept

        # 6. Puerta de precisión determinista
        gate = precision.finalize(document, kept, rules=get_rules())
        return gate.kept, guard_result.discarded + gate.discarded


# Instancia central
task_orchestrator = ApaTaskOrchestrator()
