"""Evaluación empírica de Falsos Positivos, Falsos Negativos, Precisión y Recall (Sección 3).

Evalúa sistemáticamente reglas representativas del motor APA 7 con:
- Caso Correcto (No debe disparar hallazgo)
- Caso Incorrecto (Debe disparar hallazgo)
- Excepción Válida (Regla con excepción APA 7: no debe disparar falso positivo)
- Caso Ambiguo (No debe disparar observación arbitraria)
- Caso Propenso a Falso Positivo (Apellidos compuestos, acrónimos, etc.)
"""
from __future__ import annotations

import unittest
from backend.app.services.docx_parser import ParagraphInfo, ParsedDocument, RunInfo, SectionInfo
from backend.app.services.analyzer import analyze
from backend.app.services.comment_anchor_manager import sha256_hash


def _make_eval_doc(
    paragraphs_spec: list[dict],
    margins: tuple[float, float, float, float] = (1.0, 1.0, 1.0, 1.0),
    references_start: int | None = None,
) -> ParsedDocument:
    paras = []
    for i, spec in enumerate(paragraphs_spec):
        text = spec["text"]
        style = spec.get("style", "Normal")
        indent = spec.get("indent", 0.5)
        left_indent = spec.get("left_indent", 0.0)
        line_spacing = spec.get("spacing", 2.0)
        paras.append(
            ParagraphInfo(
                index=i,
                text=text,
                style_name=style,
                alignment="left",
                line_spacing=line_spacing,
                space_before_pt=0.0,
                space_after_pt=0.0,
                first_line_indent_in=indent,
                left_indent_in=left_indent,
                paragraph_id=f"p_{i}",
                paragraph_hash=sha256_hash(text or "[vacio]"),
                runs=[
                    RunInfo(
                        text=text,
                        font_name="Times New Roman",
                        font_size_pt=12.0,
                        bold=spec.get("bold", False),
                        italic=spec.get("italic", False),
                        underline=False,
                        start_offset=0,
                        end_offset=len(text),
                    )
                ],
            )
        )
    sec = SectionInfo(
        index=0,
        top_margin_in=margins[0],
        bottom_margin_in=margins[1],
        left_margin_in=margins[2],
        right_margin_in=margins[3],
        page_width_in=8.5,
        page_height_in=11.0,
    )
    doc = ParsedDocument(
        filename="eval.docx",
        paragraphs=paras,
        sections=[sec],
        default_font="Times New Roman",
        default_font_size_pt=12.0,
        references_start=references_start,
        section_titles=[""] * len(paras),
    )
    from backend.app.services.bibliography import build_bibliography
    doc.bibliography = build_bibliography(doc)
    return doc


class TestPrecisionRecallBenchmark(unittest.TestCase):

    def test_benchmark_metrics_calculation(self):
        """Ejecuta los casos controlados y calcula TP, FP, TN, FN, Precisión y Recall."""

        test_cases = [
            # 1. CIT-002: Ampersand en citas parentéticas
            {
                "id": "CIT-002_incorrect",
                "target_rule": "CIT-002",
                "ground_truth": True,  # Incumplimiento real
                "doc": _make_eval_doc([
                    {"text": "Estudio previo de (García and López, 2020) sobre el tema."},
                    {"text": "Referencias", "style": "Heading 1"},
                    {"text": "García, A., & López, B. (2020). Título. Editorial."},
                ], references_start=1),
            },
            {
                "id": "CIT-002_correct",
                "target_rule": "CIT-002",
                "ground_truth": False,  # Cumple norma
                "doc": _make_eval_doc([
                    {"text": "Estudio previo de (García & López, 2020) sobre el tema."},
                    {"text": "Referencias", "style": "Heading 1"},
                    {"text": "García, A., & López, B. (2020). Título. Editorial."},
                ], references_start=1),
            },
            {
                "id": "CIT-002_exception_narrative",
                "target_rule": "CIT-002",
                "ground_truth": False,  # En cita narrativa SE DEBE usar 'y' / 'and', NO '&'
                "doc": _make_eval_doc([
                    {"text": "Según García y López (2020), el rendimiento mejoró."},
                    {"text": "Referencias", "style": "Heading 1"},
                    {"text": "García, A., & López, B. (2020). Título. Editorial."},
                ], references_start=1),
            },

            # 2. CRUCE-001: Cita en el texto no hallada en referencias
            {
                "id": "CRUCE-001_incorrect",
                "target_rule": "CRUCE-001",
                "ground_truth": True,  # Autor fantasma sin referencia
                "doc": _make_eval_doc([
                    {"text": "Como indica (Mendoza, 2018), el modelo es robusto."},
                    {"text": "Referencias", "style": "Heading 1"},
                    {"text": "García, A. (2020). Título. Editorial."},
                ], references_start=1),
            },
            {
                "id": "CRUCE-001_correct",
                "target_rule": "CRUCE-001",
                "ground_truth": False,  # Cita y referencia coinciden
                "doc": _make_eval_doc([
                    {"text": "Como indica (García, 2020), el modelo es robusto."},
                    {"text": "Referencias", "style": "Heading 1"},
                    {"text": "García, A. (2020). Título. Editorial."},
                ], references_start=1),
            },
            {
                "id": "CRUCE-001_compound_surname_fp_check",
                "target_rule": "CRUCE-001",
                "ground_truth": False,  # Apellido compuesto: no debe disparar falso positivo
                "doc": _make_eval_doc([
                    {"text": "Como indica (García-Márquez, 2015), la literatura evoluciona."},
                    {"text": "Referencias", "style": "Heading 1"},
                    {"text": "García-Márquez, G. (2015). Obras completas. Editorial."},
                ], references_start=1),
            },

            # 3. CRUCE-002: Referencia no citada en el cuerpo del texto
            {
                "id": "CRUCE-002_incorrect",
                "target_rule": "CRUCE-002",
                "ground_truth": True,  # Referencia huérfana
                "doc": _make_eval_doc([
                    {"text": "Texto sin ninguna cita en el contenido principal."},
                    {"text": "Referencias", "style": "Heading 1"},
                    {"text": "Ortega, J. (2019). Filosofía. Editorial."},
                ], references_start=1),
            },

            # 4. FORMAT-001: Márgenes de 1 pulgada (2.54 cm)
            {
                "id": "FORMAT-001_incorrect",
                "target_rule": "FORMAT-001",
                "ground_truth": True,  # Márgenes de 0.5 in
                "doc": _make_eval_doc([
                    {"text": "Párrafo en documento con márgenes estrechos."},
                ], margins=(0.5, 0.5, 0.5, 0.5)),
            },
            {
                "id": "FORMAT-001_correct",
                "target_rule": "FORMAT-001",
                "ground_truth": False,  # Márgenes correctos de 1 in
                "doc": _make_eval_doc([
                    {"text": "Párrafo en documento con márgenes estándar APA."},
                ], margins=(1.0, 1.0, 1.0, 1.0)),
            },

            # 5. REF-002: Sangría francesa en referencias (0.5 in)
            {
                "id": "REF-002_incorrect",
                "target_rule": "REF-002",
                "ground_truth": True,  # Sin sangría francesa
                "doc": _make_eval_doc([
                    {"text": "Referencias", "style": "Heading 1"},
                    {"text": "Álvarez, C. (2021). Metodología. Editorial.", "indent": 0.0, "left_indent": 0.0},
                ], references_start=0),
            },
            {
                "id": "REF-002_correct",
                "target_rule": "REF-002",
                "ground_truth": False,  # Con sangría francesa válida (-0.5 in first_line, 0.5 in left)
                "doc": _make_eval_doc([
                    {"text": "Referencias", "style": "Heading 1"},
                    {"text": "Álvarez, C. (2021). Metodología. Editorial.", "indent": -0.5, "left_indent": 0.5},
                ], references_start=0),
            },

            # 6. REF-003: Orden alfabético de referencias
            {
                "id": "REF-003_incorrect",
                "target_rule": "REF-003",
                "ground_truth": True,  # Desorden alfabético (Zapata antes de Álvarez)
                "doc": _make_eval_doc([
                    {"text": "Referencias", "style": "Heading 1"},
                    {"text": "Zapata, M. (2020). Título Z. Editorial.", "indent": -0.5, "left_indent": 0.5},
                    {"text": "Álvarez, C. (2021). Metodología. Editorial.", "indent": -0.5, "left_indent": 0.5},
                ], references_start=0),
            },
            {
                "id": "REF-003_correct",
                "target_rule": "REF-003",
                "ground_truth": False,  # Orden alfabético correcto (Álvarez antes de Zapata)
                "doc": _make_eval_doc([
                    {"text": "Referencias", "style": "Heading 1"},
                    {"text": "Álvarez, C. (2021). Metodología. Editorial.", "indent": -0.5, "left_indent": 0.5},
                    {"text": "Zapata, M. (2020). Título Z. Editorial.", "indent": -0.5, "left_indent": 0.5},
                ], references_start=0),
            },

            # 7. REF-007: Autores corporativos (exención válida: no deben invertirse apellidos)
            {
                "id": "REF-007_corporate_exception",
                "target_rule": "REF-007",
                "ground_truth": False,  # Excepción válida: OMS no debe marcarse como autor sin coma
                "doc": _make_eval_doc([
                    {"text": "Referencias", "style": "Heading 1"},
                    {"text": "Organización Mundial de la Salud. (2020). Directrices de salud. OMS.", "indent": -0.5, "left_indent": 0.5},
                ], references_start=0),
            },
        ]

        tp = 0
        fp = 0
        tn = 0
        fn = 0

        for case in test_cases:
            res = analyze(case["doc"])
            fired_rules = {f.rule_id for f in res.findings}
            fired = case["target_rule"] in fired_rules

            if case["ground_truth"] is True:
                if fired:
                    tp += 1
                else:
                    fn += 1
                    print(f"FN detectado en {case['id']}: esperaba {case['target_rule']}, no disparó. Reglas disparadas: {fired_rules}")
            else:
                if fired:
                    fp += 1
                    print(f"FP detectado en {case['id']}: NO esperaba {case['target_rule']}, pero disparó.")
                else:
                    tn += 1

        total = len(test_cases)
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0

        print("\n--- RESULTADOS EMPÍRICOS DE PRECISIÓN Y RECALL ---")
        print(f"Total de casos de prueba controlados: {total}")
        print(f"Verdaderos Positivos (TP): {tp}")
        print(f"Verdaderos Negativos (TN): {tn}")
        print(f"Falsos Positivos (FP):     {fp}")
        print(f"Falsos Negativos (FN):     {fn}")
        print(f"Precisión Calculada:       {precision:.4f} ({precision * 100:.1f} %)")
        print(f"Recall Calculado:          {recall:.4f} ({recall * 100:.1f} %)")
        print(f"F1-Score:                  {f1:.4f}")

        self.assertEqual(fp, 0, f"Se detectaron {fp} falsos positivos en el conjunto de control")
        self.assertEqual(fn, 0, f"Se detectaron {fn} falsos negativos en el conjunto de control")
        self.assertGreaterEqual(precision, 0.95)
        self.assertGreaterEqual(recall, 0.95)


if __name__ == "__main__":
    unittest.main()
