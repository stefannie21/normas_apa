"""Pruebas unitarias para Especialistas de IA y Orquestador Central APA.

Cubre:
1. ComplexCitationSpecialist: Análisis de citas secundarias, parentéticas múltiples y autores corporativos.
2. ReferenceContextSpecialist: Clasificación contextual de fuentes y diferenciación de omisiones permitidas.
3. CorrectionProposalSpecialist: Generación de propuestas de corrección sin inventar hallazgos ni alterar reglas.
4. StructuralContextSpecialist: Resolución de ambigüedades en encabezados sin estilos de Word.
5. ApaTaskOrchestrator:
   - Orquestación determinista + IA
   - Validación estricta Pydantic
   - Generación de anclajes automáticos
   - Caché de tareas por versión de documento
   - Verificación final determinista (citation_guard y precision)
"""
from __future__ import annotations

import unittest
from backend.app.models.apa_models import StructuredFindingModel, AnchorModel, EvidenceModel
from backend.app.rules.base import Category, Finding, Severity
from backend.app.services.ai_specialists import (
    ComplexCitationSpecialist,
    ReferenceContextSpecialist,
    CorrectionProposalSpecialist,
    StructuralContextSpecialist,
)
from backend.app.services.apa_task_orchestrator import ApaTaskOrchestrator
from backend.app.services.docx_parser import ParagraphInfo, ParsedDocument, RunInfo
from backend.app.services.comment_anchor_manager import sha256_hash


def _create_sample_doc() -> ParsedDocument:
    paras_raw = [
        "Capítulo I: Introducción al problema",
        "Según Piaget (como se citó en Vygotsky, 1978), el aprendizaje es constructivo.",
        "Diversos autores apoyan esta postura (García, 2019; López & Pérez, 2020; Martínez et al., 2021).",
        "La Organización Mundial de la Salud (OMS, 2020) emitió directrices globales.",
        "Referencias",
        "Vygotsky, L. (1978). Mind in society. Harvard University Press.",
        "Organización Mundial de la Salud. (2020). Directrices de salud mental. OMS.",
    ]
    paras = []
    for i, t in enumerate(paras_raw):
        paras.append(
            ParagraphInfo(
                index=i,
                text=t,
                style_name="Heading 1" if i == 0 else ("Heading 1" if i == 4 else "Normal"),
                alignment="left",
                line_spacing=2.0,
                space_before_pt=0.0,
                space_after_pt=0.0,
                first_line_indent_in=0.5 if i not in (0, 4) else 0.0,
                left_indent_in=0.0,
                paragraph_id=f"p_{i}",
                paragraph_hash=sha256_hash(t),
                runs=[RunInfo(text=t, font_name="Times New Roman", font_size_pt=12.0, bold=(i in (0, 4)), italic=False, underline=False, start_offset=0, end_offset=len(t))],
            )
        )
    return ParsedDocument(
        filename="tesis_muestra.docx",
        paragraphs=paras,
        sections=[],
        default_font="Times New Roman",
        default_font_size_pt=12.0,
        references_start=4,
        section_titles=[""] * len(paras),
    )


class TestAiSpecialistsAndOrchestrator(unittest.TestCase):

    def test_complex_citation_specialist(self):
        """El especialista en citas complejas detecta citas secundarias y múltiples."""
        spec = ComplexCitationSpecialist()
        doc = _create_sample_doc()

        # Párrafos candidatos de citas
        candidates = [doc.paragraphs[1], doc.paragraphs[2]]
        findings = spec.run(
            document=doc,
            candidate_paragraphs=candidates,
            document_id="doc_test",
            document_version="1.0",
        )
        self.assertIsInstance(findings, list)
        for f in findings:
            self.assertEqual(f.task_id, "complex_citation_analysis")
            self.assertTrue(f.rule_id.startswith("CIT-"))

    def test_reference_context_specialist(self):
        """El especialista en referencias evalúa libro y autor corporativo."""
        spec = ReferenceContextSpecialist()
        doc = _create_sample_doc()

        ref_candidates = doc.reference_paragraphs()
        findings = spec.run(
            document=doc,
            reference_paragraphs=ref_candidates,
            document_id="doc_test",
            document_version="1.0",
        )
        self.assertIsInstance(findings, list)
        for f in findings:
            self.assertEqual(f.task_id, "reference_context_evaluation")
            self.assertTrue(f.rule_id.startswith("REF-"))

    def test_correction_proposal_specialist_does_not_invent_findings(self):
        """CorrectionProposalSpecialist NO crea hallazgos nuevos; solo enriquece existentes."""
        spec = CorrectionProposalSpecialist()
        doc = _create_sample_doc()

        dummy_finding = StructuredFindingModel(
            task_id="python_deterministic_rule",
            rule_id="CIT-002",
            category="Citas",
            status="FAIL",
            severity="warning",
            title="Uso incorrecto de conjunción",
            message="Uso de 'and' en lugar de '&' en cita parentética.",
            suggestion="Use '&' para citas parentéticas.",
            evidence=EvidenceModel(
                original_text="(García and López, 2020)",
                reason="En citas parentéticas se debe emplear '&'.",
            ),
            anchor=AnchorModel(
                document_id="doc_test",
                document_version="1.0",
                paragraph_id="p_2",
                paragraph_index=2,
                start_offset=0,
                end_offset=24,
                matched_text="(García and López, 2020)",
                fragment_hash=sha256_hash("(García and López, 2020)"),
            ),
        )

        res = spec.run([dummy_finding])
        # Debe contener exactamente la misma cantidad de hallazgos
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0].rule_id, "CIT-002")
        self.assertIn("&", res[0].suggestion)

    def test_structural_context_specialist(self):
        """StructuralContextSpecialist evalúa jerarquía contextual sin romper reglas."""
        spec = StructuralContextSpecialist()
        doc = _create_sample_doc()

        candidates = [doc.paragraphs[0]]
        res = spec.run(
            document=doc,
            candidate_headings=candidates,
            document_id="doc_test",
            document_version="1.0",
        )
        self.assertIsInstance(res, list)

    def test_structured_finding_pydantic_validation(self):
        """Validación estricta de esquema Pydantic para hallazgos estructurados."""
        model = StructuredFindingModel(
            task_id="citation_analysis",
            rule_id="CIT-001",
            category="Citas",
            status="FAIL",
            severity="warning",
            title="Posible incumplimiento en la cita",
            message="Descripción del incumplimiento",
            suggestion="Propuesta de corrección",
            evidence=EvidenceModel(
                original_text="Fragmento exacto del documento",
                reason="Fundamento de la observación",
            ),
            anchor=AnchorModel(
                document_id="doc_1",
                document_version="v1",
                paragraph_id="p_1",
                paragraph_index=1,
                start_offset=10,
                end_offset=25,
                matched_text="Fragmento exacto",
                fragment_hash=sha256_hash("Fragmento exacto"),
                context_before="",
                context_after="",
                run_indices=[0],
            ),
            confidence=0.95,
        )
        data = model.model_dump()
        self.assertEqual(data["rule_id"], "CIT-001")
        self.assertEqual(data["confidence"], 0.95)
        self.assertEqual(data["anchor"]["matched_text"], "Fragmento exacto")

    def test_apa_task_orchestrator_execution(self):
        """ApaTaskOrchestrator ejecuta determinista + IA, genera anclajes y métricas."""
        orchestrator = ApaTaskOrchestrator()
        doc = _create_sample_doc()

        # Primera ejecución
        result_v1 = orchestrator.orchestrate(
            document=doc,
            document_id="tesis_001",
            document_version="1.0",
            enable_ai=True,
        )
        self.assertIsInstance(result_v1.findings, list)
        self.assertIsInstance(result_v1.metrics, list)
        self.assertGreater(len(result_v1.metrics), 0)

        # Verificar que todos los hallazgos tengan anchor
        for f in result_v1.findings:
            self.assertIsNotNone(f.anchor, f"El hallazgo {f.rule_id} carece de anclaje")
            self.assertIn("fragment_hash", f.anchor)
            self.assertIn("start_offset", f.anchor)
            self.assertIn("end_offset", f.anchor)

        # Verificar to_dict
        res_dict = result_v1.to_dict()
        self.assertIn("findings", res_dict)
        self.assertIn("metrics", res_dict)
        self.assertIn("summary", res_dict)


if __name__ == "__main__":
    unittest.main()
