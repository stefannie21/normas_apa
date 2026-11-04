from __future__ import annotations

import unittest
from backend.app.services.docx_parser import (
    ParsedDocument,
    ParagraphInfo,
    SectionInfo,
    RunInfo,
    TableInfo,
)
from backend.app.services.bibliography import (
    Bibliography,
    CitationRecord,
    ReferenceRecord,
)
from backend.app.rules.status import ValidationStatus
from backend.app.rules.formatting import (
    MarginRule,
    AlignmentRule,
    FirstLineIndentRule,
)
from backend.app.rules.headings import (
    StructureRule,
    HeadingLevelFormatRule,
    NumberedHeadingRule,
)
from backend.app.rules.citations import QuotePageRule
from backend.app.rules.cite_format import (
    EtAlThresholdRule,
    BlockQuoteRule,
    CitationPeriodRule,
)
from backend.app.rules.references import (
    AlphabeticalOrderRule,
    DoiFormatRule,
)
from backend.app.rules.tables import TableBordersRule


def make_para(
    index: int = 0,
    text: str = "",
    style_name: str = "Normal",
    alignment: str | None = "left",
    line_spacing: float | None = 2.0,
    space_before_pt: float | None = 0.0,
    space_after_pt: float | None = 0.0,
    first_line_indent_in: float | None = 0.5,
    left_indent_in: float | None = 0.0,
    heading_level: int | None = None,
    section_title: str = "",
    is_block_quote: bool = False,
    bold: bool = False,
    italic: bool = False,
) -> ParagraphInfo:
    p = ParagraphInfo(
        index=index,
        text=text,
        style_name=style_name,
        alignment=alignment,
        line_spacing=line_spacing,
        space_before_pt=space_before_pt,
        space_after_pt=space_after_pt,
        first_line_indent_in=first_line_indent_in,
        left_indent_in=left_indent_in,
        runs=[
            RunInfo(
                text=text,
                font_name="Times New Roman",
                font_size_pt=12.0,
                bold=bold,
                italic=italic,
                underline=False,
                start_offset=0,
                end_offset=len(text),
            )
        ] if text else [],
        heading_level=heading_level,
    )
    p.section_title = section_title
    p.is_block_quote = is_block_quote
    return p


def make_sec(
    index: int = 0,
    top: float | None = 1.0,
    bottom: float | None = 1.0,
    left: float | None = 1.0,
    right: float | None = 1.0,
    width: float | None = 8.5,
    height: float | None = 11.0,
) -> SectionInfo:
    return SectionInfo(
        index=index,
        top_margin_in=top,
        bottom_margin_in=bottom,
        left_margin_in=left,
        right_margin_in=right,
        page_width_in=width,
        page_height_in=height,
    )


def make_doc(
    paragraphs: list[ParagraphInfo] | None = None,
    sections: list[SectionInfo] | None = None,
    tables: list[TableInfo] | None = None,
    references_start: int | None = None,
    bibliography: Bibliography | None = None,
) -> ParsedDocument:
    paras = paragraphs or []
    secs = sections or [make_sec()]
    doc = ParsedDocument(
        filename="test.docx",
        paragraphs=paras,
        sections=secs,
        default_font="Times New Roman",
        default_font_size_pt=12.0,
        references_start=references_start,
        tables=tables or [],
        bibliography=bibliography,
        section_titles=[""] * len(paras),
    )
    return doc


class TestNormativePrecisionAudit(unittest.TestCase):
    """Matriz exhaustiva de 5 casos obligatorios para cada regla revisada:
    1. Correcto
    2. Incorrecto
    3. Excepción válida
    4. Ambiguo (UNCERTAIN)
    5. Propenso a Falso Positivo
    """

    # -------------------------------------------------------------------------
    # FORMAT-001: Márgenes (1 pulgada / 2.54 cm)
    # -------------------------------------------------------------------------
    def test_format_001_1_correcto(self):
        rule = MarginRule()
        sec = make_sec(index=0, top=1.0, bottom=1.0, left=1.0, right=1.0)
        doc = make_doc(sections=[sec])
        findings = rule.check(doc)
        self.assertEqual(len(findings), 0)

    def test_format_001_2_incorrecto(self):
        rule = MarginRule()
        sec = make_sec(index=0, top=0.7, bottom=1.0, left=1.0, right=1.0)
        doc = make_doc(sections=[sec])
        findings = rule.check(doc)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].rule_id, "FORMAT-001")

    def test_format_001_3_excepcion_valida_encuadernacion(self):
        rule = MarginRule()
        sec = make_sec(index=0, top=1.0, bottom=1.0, left=1.5, right=1.0)
        doc = make_doc(sections=[sec])
        findings = rule.check(doc)
        self.assertEqual(len(findings), 0)

    def test_format_001_4_tolerancia_tecnica(self):
        rule = MarginRule()
        sec = make_sec(index=0, top=1.02, bottom=0.98, left=1.01, right=0.99)
        doc = make_doc(sections=[sec])
        findings = rule.check(doc)
        self.assertEqual(len(findings), 0)

    def test_format_001_5_propenso_fp_paisaje(self):
        rule = MarginRule()
        sec = make_sec(index=0, top=0.5, bottom=0.5, left=0.5, right=0.5, width=11.0, height=8.5)
        doc = make_doc(sections=[sec])
        findings = rule.check(doc)
        self.assertEqual(len(findings), 0)

    # -------------------------------------------------------------------------
    # FORMAT-005: Alineación a la izquierda
    # -------------------------------------------------------------------------
    def test_format_005_1_correcto(self):
        rule = AlignmentRule()
        p = make_para(0, "Texto alineado a la izquierda según APA.", alignment="left")
        doc = make_doc([p])
        self.assertEqual(len(rule.check(doc)), 0)

    def test_format_005_2_incorrecto(self):
        rule = AlignmentRule()
        p = make_para(0, "Texto justificado que incumple la alineación recomendada por APA 7.", alignment="justify")
        doc = make_doc([p])
        findings = rule.check(doc)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].rule_id, "FORMAT-005")

    def test_format_005_3_excepcion_institucional(self):
        rule = AlignmentRule()
        p = make_para(0, "Texto justificado con permiso de la institución.", alignment="justify")
        doc = make_doc([p])
        doc.allow_justified = True
        self.assertEqual(len(rule.check(doc)), 0)

    def test_format_005_4_ambiguo(self):
        rule = AlignmentRule()
        p = make_para(0, "Texto con alineación no especificada.", alignment=None)
        doc = make_doc([p])
        self.assertEqual(len(rule.check(doc)), 0)

    def test_format_005_5_propenso_fp_titulo(self):
        rule = AlignmentRule()
        p = make_para(0, "Capítulo 1: Introducción", heading_level=1, alignment="center")
        doc = make_doc([p])
        self.assertEqual(len(rule.check(doc)), 0)

    # -------------------------------------------------------------------------
    # FORMAT-006: Sangría de primera línea
    # -------------------------------------------------------------------------
    def test_format_006_1_correcto(self):
        rule = FirstLineIndentRule()
        p = make_para(
            0,
            "Este es un párrafo normal del cuerpo del documento que cuenta con la longitud mínima de ochenta caracteres requerida.",
            first_line_indent_in=0.5
        )
        doc = make_doc([p])
        self.assertEqual(len(rule.check(doc)), 0)

    def test_format_006_2_incorrecto(self):
        rule = FirstLineIndentRule()
        p = make_para(
            0,
            "Este es un párrafo normal del cuerpo del documento que cuenta con la longitud mínima de ochenta caracteres pero sin sangría.",
            first_line_indent_in=0.0
        )
        doc = make_doc([p])
        findings = rule.check(doc)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].rule_id, "FORMAT-006")

    def test_format_006_3_excepcion_resumen(self):
        rule = FirstLineIndentRule()
        p = make_para(
            0,
            "El presente resumen describe de forma precisa los hallazgos principales de la investigación sobre evaluación normativa.",
            first_line_indent_in=0.0,
            section_title="Resumen"
        )
        doc = make_doc([p])
        self.assertEqual(len(rule.check(doc)), 0)

    def test_format_006_4_sangria_manual(self):
        rule = FirstLineIndentRule()
        p = make_para(
            0,
            "\tEste párrafo tiene una sangría manual creada con carácter tabulador en vez de sangría de formato de estilo en Word.",
            first_line_indent_in=0.0
        )
        doc = make_doc([p])
        findings = rule.check(doc)
        self.assertEqual(len(findings), 1)
        self.assertTrue(findings[0].extra.get("manual_indent"))

    def test_format_006_5_propenso_fp_bloque(self):
        rule = FirstLineIndentRule()
        p = make_para(
            0,
            "Fragmento correspondiente a una cita en bloque de más de cuarenta palabras con sangría izquierda de bloque completa.",
            first_line_indent_in=0.0,
            left_indent_in=0.5,
            is_block_quote=True
        )
        doc = make_doc([p])
        self.assertEqual(len(rule.check(doc)), 0)

    # -------------------------------------------------------------------------
    # HEAD-001, HEAD-005: Títulos
    # -------------------------------------------------------------------------
    def test_head_001_opcionalidad(self):
        rule = StructureRule()
        doc = make_doc([])
        self.assertEqual(len(rule.check(doc)), 0)

    def test_head_005_1_correcto(self):
        rule = NumberedHeadingRule()
        p = make_para(0, "Marco Teórico", heading_level=1)
        doc = make_doc([p])
        self.assertEqual(len(rule.check(doc)), 0)

    def test_head_005_2_incorrecto(self):
        rule = NumberedHeadingRule()
        p = make_para(0, "1.1. Marco Teórico", heading_level=2)
        doc = make_doc([p])
        findings = rule.check(doc)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].rule_id, "HEAD-005")

    def test_head_005_3_excepcion_institucional(self):
        rule = NumberedHeadingRule()
        p = make_para(0, "1.1. Marco Teórico", heading_level=2)
        doc = make_doc([p])
        doc.allow_numbered_headings = True
        self.assertEqual(len(rule.check(doc)), 0)

    # -------------------------------------------------------------------------
    # CIT-004: Citas textuales directas vs comillas de concepto
    # -------------------------------------------------------------------------
    def test_cit_004_1_correcto(self):
        rule = QuotePageRule()
        p = make_para(0, 'La educación debe concebirse como "un proceso de transformación integral de la persona" (García, 2020, p. 45).')
        doc = make_doc([p])
        self.assertEqual(len(rule.check(doc)), 0)

    def test_cit_004_2_incorrecto(self):
        rule = QuotePageRule()
        p = make_para(0, 'La educación debe concebirse como "un proceso de transformación integral de la persona y de la sociedad" (García, 2020).')
        doc = make_doc([p])
        findings = rule.check(doc)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].rule_id, "CIT-004")
        self.assertEqual(findings[0].validation_status, ValidationStatus.FAIL)

    def test_cit_004_3_excepcion_termino_corto(self):
        rule = QuotePageRule()
        p = make_para(0, 'Se busca lograr un "aprendizaje significativo" (Ausubel, 1968).')
        doc = make_doc([p])
        self.assertEqual(len(rule.check(doc)), 0)

    def test_cit_004_4_ambiguo_uncertain(self):
        rule = QuotePageRule()
        p = make_para(0, 'El equipo aplicó una "metodología cualitativa de diseño mixto" (Hernández, 2018).')
        doc = make_doc([p])
        findings = rule.check(doc)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].validation_status, ValidationStatus.UNCERTAIN)

    # -------------------------------------------------------------------------
    # CIT-005: Umbral de 'et al.' y excepción de desambiguación APA 8.18
    # -------------------------------------------------------------------------
    def test_cit_005_1_correcto(self):
        rule = EtAlThresholdRule()
        ref = ReferenceRecord(paragraph_index=10, page=1, raw="Pérez, A., Gómez, B., & Ruiz, C. (2020). Libro.", surnames=["Pérez", "Gómez", "Ruiz"], year=2020, author_count=3, initials_count=3)
        c = CitationRecord(paragraph_index=0, page=1, form="parentetica", raw="(Pérez et al., 2020)", surnames=["Pérez"], year=2020, has_et_al=True)
        p = make_para(0, "Como afirman (Pérez et al., 2020) en su estudio.")
        doc = make_doc([p], bibliography=Bibliography(references=[ref], citations=[c]))
        self.assertEqual(len(rule.check(doc)), 0)

    def test_cit_005_2_incorrecto(self):
        rule = EtAlThresholdRule()
        ref = ReferenceRecord(paragraph_index=10, page=1, raw="Pérez, A., Gómez, B., & Ruiz, C. (2020). Libro.", surnames=["Pérez", "Gómez", "Ruiz"], year=2020, author_count=3, initials_count=3)
        c = CitationRecord(paragraph_index=0, page=1, form="parentetica", raw="(Pérez, Gómez, & Ruiz, 2020)", surnames=["Pérez", "Gómez", "Ruiz"], year=2020, has_et_al=False)
        p = make_para(0, "Según (Pérez, Gómez, & Ruiz, 2020).")
        doc = make_doc([p], bibliography=Bibliography(references=[ref], citations=[c]))
        findings = rule.check(doc)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].rule_id, "CIT-005")

    def test_cit_005_3_excepcion_desambiguacion_apa_8_18(self):
        rule = EtAlThresholdRule()
        ref1 = ReferenceRecord(paragraph_index=10, page=1, raw="Kapoor, S., Bloom, T., & Zucker, M. (2017). Alpha.", surnames=["Kapoor", "Bloom", "Zucker"], year=2017, author_count=3, initials_count=3)
        ref2 = ReferenceRecord(paragraph_index=11, page=1, raw="Kapoor, S., Zucker, M., & Brown, L. (2017). Beta.", surnames=["Kapoor", "Zucker", "Brown"], year=2017, author_count=3, initials_count=3)
        c = CitationRecord(paragraph_index=0, page=1, form="parentetica", raw="(Kapoor, Bloom, et al., 2017)", surnames=["Kapoor", "Bloom"], year=2017, has_et_al=False)
        p = make_para(0, "Citando a (Kapoor, Bloom, et al., 2017).")
        doc = make_doc([p], bibliography=Bibliography(references=[ref1, ref2], citations=[c]))
        self.assertEqual(len(rule.check(doc)), 0)

    # -------------------------------------------------------------------------
    # CIT-007: Punto final en cita corta y cita en bloque
    # -------------------------------------------------------------------------
    def test_cit_007_1_corta_correcta(self):
        rule = CitationPeriodRule()
        c = CitationRecord(paragraph_index=0, page=1, form="parentetica", raw="(Díaz, 2020)", surnames=["Díaz"], year=2020, block_quote=False)
        p = make_para(0, "Este es el texto previo (Díaz, 2020).")
        doc = make_doc([p], bibliography=Bibliography(references=[], citations=[c]))
        self.assertEqual(len(rule.check(doc)), 0)

    def test_cit_007_2_corta_incorrecta_punto_antes(self):
        rule = CitationPeriodRule()
        c = CitationRecord(paragraph_index=0, page=1, form="parentetica", raw="(Díaz, 2020)", surnames=["Díaz"], year=2020, block_quote=False)
        p = make_para(0, "Este es el texto previo. (Díaz, 2020)")
        doc = make_doc([p], bibliography=Bibliography(references=[], citations=[c]))
        findings = rule.check(doc)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].rule_id, "CIT-007")

    def test_cit_007_3_bloque_correcto_punto_antes(self):
        rule = CitationPeriodRule()
        c = CitationRecord(paragraph_index=0, page=1, form="bloque", raw="(Díaz, 2020, p. 15)", surnames=["Díaz"], year=2020, block_quote=True)
        p = make_para(0, "Texto extenso de la cita en bloque que culmina aquí. (Díaz, 2020, p. 15)")
        doc = make_doc([p], bibliography=Bibliography(references=[], citations=[c]))
        self.assertEqual(len(rule.check(doc)), 0)

    def test_cit_007_4_bloque_incorrecto_punto_despues(self):
        rule = CitationPeriodRule()
        c = CitationRecord(paragraph_index=0, page=1, form="bloque", raw="(Díaz, 2020, p. 15)", surnames=["Díaz"], year=2020, block_quote=True)
        p = make_para(0, "Texto extenso de la cita en bloque que culmina aquí. (Díaz, 2020, p. 15).")
        doc = make_doc([p], bibliography=Bibliography(references=[], citations=[c]))
        findings = rule.check(doc)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].rule_id, "CIT-007")

    # -------------------------------------------------------------------------
    # REF-003, REF-005: Referencias
    # -------------------------------------------------------------------------
    def test_ref_003_orden_alfabetico(self):
        rule = AlphabeticalOrderRule()
        p0 = make_para(0, "Referencias", heading_level=1)
        p1 = make_para(1, "Álvarez, C. (2020). Tesis.")
        p2 = make_para(2, "Bernal, R. (2019). Libro.")
        doc = make_doc([p0, p1, p2], references_start=0)
        self.assertEqual(len(rule.check(doc)), 0)

    def test_ref_005_doi_valido_y_sin_doi(self):
        rule = DoiFormatRule()
        p0 = make_para(0, "Referencias", heading_level=1)
        p1 = make_para(1, "García, M. (2020). Libro impreso sin DOI.")
        p2 = make_para(2, "López, J. (2021). Artículo. https://doi.org/10.1234/567")
        doc = make_doc([p0, p1, p2], references_start=0)
        self.assertEqual(len(rule.check(doc)), 0)

    def test_ref_005_doi_formato_antiguo_incorrecto(self):
        rule = DoiFormatRule()
        p0 = make_para(0, "Referencias", heading_level=1)
        p1 = make_para(1, "López, J. (2021). Artículo. doi: 10.1234/567")
        doc = make_doc([p0, p1], references_start=0)
        findings = rule.check(doc)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].rule_id, "REF-005")

    # -------------------------------------------------------------------------
    # TABLE-003: Tablas
    # -------------------------------------------------------------------------
    def test_table_003_bordes_horizontales_vs_verticales(self):
        rule = TableBordersRule()
        t_ok = TableInfo(index=1, has_vertical_borders=False, caption_text="Tabla 1. Datos")
        t_bad = TableInfo(index=2, has_vertical_borders=True, caption_text="Tabla 2. Datos")
        doc_ok = make_doc(tables=[t_ok])
        doc_bad = make_doc(tables=[t_bad])
        self.assertEqual(len(rule.check(doc_ok)), 0)
        self.assertEqual(len(rule.check(doc_bad)), 1)


if __name__ == "__main__":
    unittest.main()
