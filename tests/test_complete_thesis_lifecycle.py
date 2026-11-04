"""Prueba integral de documentos DOCX completos (Sección 2).

Valida un documento académico con todas las secciones de una tesis:
- Portada
- Resumen y abstract
- Índice (TOC)
- Introducción
- Títulos y subtítulos (niveles 1 a 3)
- Párrafos normales
- Citas narrativas
- Citas parentéticas
- Citas textuales cortas y en bloque
- Citas secundarias
- Tablas con formato APA
- Figuras con notas
- Referencias bibliográficas
- Anexos / Apéndices
"""
from __future__ import annotations

import io
import unittest
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Inches, Pt, RGBColor

from backend.app.services.docx_parser import parse_docx
from backend.app.services.apa_task_orchestrator import ApaTaskOrchestrator
from backend.app.services.report_docx import build_report_docx


def create_full_thesis_docx() -> bytes:
    """Genera en memoria un documento DOCX con las 14 secciones obligatorias de tesis."""
    doc = Document()

    # 1. Configuración de página general (1 pulgada por lado)
    for s in doc.sections:
        s.top_margin = Inches(1)
        s.bottom_margin = Inches(1)
        s.left_margin = Inches(1)
        s.right_margin = Inches(1)

    # Estilo Normal
    normal = doc.styles["Normal"]
    normal.font.name = "Times New Roman"
    normal.font.size = Pt(12)
    normal.paragraph_format.line_spacing = 2.0

    # 1. PORTADA (Cover page)
    p_univ = doc.add_paragraph("UNIVERSIDAD NACIONAL DE EDUCACIÓN")
    p_univ.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_univ.runs[0].bold = True

    p_fac = doc.add_paragraph("FACULTAD DE CIENCIAS SOCIALES")
    p_fac.alignment = WD_ALIGN_PARAGRAPH.CENTER

    p_tit = doc.add_paragraph("IMPACTO DEL APRENDIZAJE SIGNIFICATIVO EN LA EDUCACIÓN SUPERIOR")
    p_tit.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_tit.runs[0].bold = True

    p_aut = doc.add_paragraph("Tesis presentada por:\nLic. Juan Pérez\nAsesor: Dr. Mario Vargas")
    p_aut.alignment = WD_ALIGN_PARAGRAPH.CENTER

    p_date = doc.add_paragraph("Lima - Perú\n2026")
    p_date.alignment = WD_ALIGN_PARAGRAPH.CENTER
    doc.add_page_break()

    # 2. RESUMEN / ABSTRACT
    h_res = doc.add_heading("Resumen", level=1)
    p_res = doc.add_paragraph(
        "El presente estudio analiza la correlación entre la motivación intrínseca y el rendimiento académico "
        "en estudiantes universitarios. La muestra estuvo conformada por 150 participantes seleccionados por muestreo "
        "aleatorio simple. Los resultados demuestran una correlación positiva y estadísticamente significativa."
    )
    p_res.paragraph_format.first_line_indent = Inches(0.5)

    p_kw = doc.add_paragraph("Palabras clave: aprendizaje, motivación, educación superior, rendimiento.")
    p_kw.paragraph_format.first_line_indent = Inches(0.5)
    p_kw.runs[0].italic = True

    h_abs = doc.add_heading("Abstract", level=1)
    p_abs = doc.add_paragraph(
        "This study examines the relationship between intrinsic motivation and academic achievement among university students. "
        "The sample consisted of 150 participants selected through simple random sampling. Results show a statistically significant positive correlation."
    )
    p_abs.paragraph_format.first_line_indent = Inches(0.5)
    doc.add_page_break()

    # 3. ÍNDICE / TABLA DE CONTENIDOS
    h_toc = doc.add_heading("Tabla de Contenido", level=1)
    doc.add_paragraph("Capítulo I: Introducción .................................................... 1")
    doc.add_paragraph("Capítulo II: Marco Teórico ................................................ 5")
    doc.add_paragraph("Capítulo III: Metodología ................................................ 12")
    doc.add_paragraph("Referencias ..................................................................... 20")
    doc.add_paragraph("Anexos ............................................................................ 25")
    doc.add_page_break()

    # 4. CAPÍTULO I: INTRODUCCIÓN Y TÍTULOS
    doc.add_heading("Capítulo I: Introducción", level=1)
    doc.add_heading("Planteamiento del Problema", level=2)
    doc.add_paragraph(
        "La problemática actual de la educación universitaria requiere un examen crítico de las metodologías empleadas. "
        "Diversos investigadores afirman que los métodos pasivos reducen la capacidad de pensamiento crítico de los estudiantes."
    )

    doc.add_heading("Justificación de la Investigación", level=3)
    doc.add_paragraph(
        "Esta investigación se fundamenta en la necesidad de proveer evidencia empírica cuantitativa aplicable al diseño curricular moderno."
    )

    # 5. CAPÍTULO II: MARCO TEÓRICO Y TIPOS DE CITAS
    doc.add_heading("Capítulo II: Marco Teórico", level=1)

    # Cita narrativa
    p_cn = doc.add_paragraph(
        "De acuerdo con Ausubel (1968), el factor más importante que influye en el aprendizaje es lo que el alumno ya sabe."
    )
    p_cn.paragraph_format.first_line_indent = Inches(0.5)

    # Cita parentética con múltiples autores
    p_cp = doc.add_paragraph(
        "Investigaciones recientes coinciden en señalar que las estrategias metacognitivas potencian la retención a largo plazo "
        "(González & Morales, 2020; Salazar et al., 2021)."
    )
    p_cp.paragraph_format.first_line_indent = Inches(0.5)

    # Cita textual corta (menos de 40 palabras entre comillas)
    p_tc = doc.add_paragraph(
        'Al respecto, Bruner (1960) sostuvo que "cualquier materia puede enseñarse a cualquier niño de manera honesta" (p. 33).'
    )
    p_tc.paragraph_format.first_line_indent = Inches(0.5)

    # Cita en bloque (40 palabras o más, sangría izquierda 0.5 in en todo el bloque)
    block_text = (
        "El aprendizaje significativo ocurre cuando la información nueva se conecta con un concepto relevante preexistente en la "
        "estructura cognoscitiva del individuo. Esto implica que las nuevas ideas, conceptos y proposiciones pueden ser aprendidos en la medida "
        "en que otras ideas relevantes se encuentren adecuadamente claras y disponibles en el marco mental del estudiante. (Díaz-Barriga, 2010, p. 145)"
    )
    p_block = doc.add_paragraph(block_text)
    p_block.paragraph_format.left_indent = Inches(0.5)
    p_block.paragraph_format.first_line_indent = Inches(0.0)

    # Cita secundaria ("citado en")
    p_cs = doc.add_paragraph(
        "El condicionamiento operante original de Skinner (como se citó en Feldman, 2017) explica parcialmente las respuestas a estímulos positivos."
    )
    p_cs.paragraph_format.first_line_indent = Inches(0.5)

    # 6. TABLA APA 7 (Número en negrita, título en cursiva, sin bordes verticales)
    p_tnum = doc.add_paragraph("Tabla 1")
    p_tnum.runs[0].bold = True
    p_ttit = doc.add_paragraph("Distribución de la muestra por facultad")
    p_ttit.runs[0].italic = True

    table = doc.add_table(rows=3, cols=3)
    hdr_cells = table.rows[0].cells
    hdr_cells[0].text = "Facultad"
    hdr_cells[1].text = "Frecuencia"
    hdr_cells[2].text = "Porcentaje"

    row1 = table.rows[1].cells
    row1[0].text = "Educación"
    row1[1].text = "80"
    row1[2].text = "53.3 %"

    row2 = table.rows[2].cells
    row2[0].text = "Humanidades"
    row2[1].text = "70"
    row2[2].text = "46.7 %"

    p_tnote = doc.add_paragraph("Nota. Datos obtenidos mediante encuesta censal.")
    p_tnote.paragraph_format.space_before = Pt(4)

    # 7. FIGURA APA 7 (Número en negrita, título en cursiva, notas explicativas)
    p_fnum = doc.add_paragraph("Figura 1")
    p_fnum.runs[0].bold = True
    p_ftit = doc.add_paragraph("Diagrama de flujo del procesamiento cognitivo")
    p_ftit.runs[0].italic = True

    p_fbody = doc.add_paragraph("[Diagrama conceptual de procesamiento de memoria]")
    p_fbody.alignment = WD_ALIGN_PARAGRAPH.CENTER

    p_fnote = doc.add_paragraph("Nota. Adaptado del modelo de procesamiento multialmacén de Atkinson y Shiffrin (1968).")
    doc.add_page_break()

    # 8. REFERENCIAS BIBLIOGRÁFICAS (Sección al final con sangría francesa de 0.5 in)
    h_ref = doc.add_heading("Referencias", level=1)
    
    refs = [
        "Atkinson, R. C., & Shiffrin, R. M. (1968). Human memory: A proposed system and its control processes. Academic Press.",
        "Ausubel, D. P. (1968). Educational psychology: A cognitive view. Holt, Rinehart and Winston.",
        "Bruner, J. S. (1960). The process of education. Harvard University Press.",
        "Díaz-Barriga, F. (2010). Estrategias docentes para un aprendizaje significativo (3.ª ed.). McGraw-Hill.",
        "Feldman, R. S. (2017). Psicología con aplicaciones en países de habla hispana (12.ª ed.). McGraw-Hill.",
        "González, M., & Morales, E. (2020). Estrategias metacognitivas en universitarios. Revista de Educación, 45(2), 112-128. https://doi.org/10.15517/re.v45i2.4123",
        "Salazar, C., Gómez, R., & Torres, H. (2021). Retención de información a largo plazo. Anales de Psicología, 37(1), 45-56.",
    ]

    for r_text in refs:
        p_r = doc.add_paragraph(r_text)
        p_r.paragraph_format.left_indent = Inches(0.5)
        p_r.paragraph_format.first_line_indent = Inches(-0.5)

    doc.add_page_break()

    # 9. ANEXOS / APÉNDICE
    h_anx = doc.add_heading("Apéndice A: Cuestionario de Evaluación", level=1)
    p_anx = doc.add_paragraph(
        "A continuación se presenta el instrumento aplicado para medir la variable motivación intrínseca."
    )
    p_anx.paragraph_format.first_line_indent = Inches(0.5)

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


class TestCompleteThesisLifecycle(unittest.TestCase):
    """Verifica que el motor procese documentos completos de tesis sin pérdida estructural."""

    @classmethod
    def setUpClass(cls):
        cls.docx_bytes = create_full_thesis_docx()
        cls.parsed_doc = parse_docx(cls.docx_bytes, filename="tesis_completa.docx")
        cls.orchestrator = ApaTaskOrchestrator()

    def test_parser_extracts_all_structural_components(self):
        """Verifica que el parser detecte portada, resumen, índice, tablas, figuras y referencias."""
        doc = self.parsed_doc
        self.assertGreater(len(doc.paragraphs), 20, "Documento debe tener más de 20 párrafos")

        # 1. Secciones de encabezado (Nivel 1)
        headings_l1 = [p for p in doc.paragraphs if p.heading_level == 1]
        self.assertGreaterEqual(len(headings_l1), 5, "Debe haber al menos 5 encabezados de nivel 1")

        # 2. Tablas
        self.assertGreaterEqual(len(doc.tables), 1, "Debe extraer la tabla de muestra")
        t0 = doc.tables[0]
        self.assertEqual(t0.rows, 3)
        self.assertEqual(t0.cols, 3)

        # 3. Referencias bibliográficas
        self.assertIsNotNone(doc.references_start, "Debe localizar la sección de referencias")
        ref_paras = doc.reference_paragraphs()
        self.assertGreaterEqual(len(ref_paras), 5, "Debe extraer al menos 5 párrafos de referencia")

    def test_orchestration_executes_cleanly_on_full_document(self):
        """El orquestador procesa la tesis completa, asocia anclajes y genera reporte Word."""
        result = self.orchestrator.orchestrate(
            document=self.parsed_doc,
            document_id="tesis_completa_001",
            document_version="1.0",
            enable_ai=False,  # Prueba determinista
        )

        self.assertIsInstance(result.findings, list)
        self.assertIsInstance(result.anchors, list)
        self.assertGreater(len(result.metrics), 0)

        # Verificar anclajes íntegros
        for f in result.findings:
            if f.anchor:
                self.assertIn("start_offset", f.anchor)
                self.assertIn("end_offset", f.anchor)
                self.assertIn("fragment_hash", f.anchor)
                self.assertNotEqual(
                    f.anchor["fragment_hash"],
                    "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
                    "Ningún anclaje debe tener el hash de cadena vacía",
                )

        # Generación de informe Word oficial (.docx)
        from backend.app.services.analyzer import analyze
        from backend.app.services.report import build_report

        analysis_res = analyze(self.parsed_doc)
        report_payload = build_report(analysis_res)
        report_bytes = build_report_docx(report_payload)

        self.assertIsInstance(report_bytes, bytes)
        self.assertGreater(len(report_bytes), 5000, "El informe Word generado debe ser un binario válido")


if __name__ == "__main__":
    unittest.main()
