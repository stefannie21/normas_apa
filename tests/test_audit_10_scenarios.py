"""Auditoría técnica de los 10 escenarios reales de anclaje, hashes y persistencia.

Escenarios auditados rigurosamente:
1. Insertar un párrafo antes de uno que contiene una observación.
2. Eliminar un párrafo anterior.
3. Modificar el texto antes del fragmento observado.
4. Modificar el fragmento observado (debe marcarse obsoleto, sin saltos arbitrarios).
5. Eliminar el fragmento observado (marcado obsoleto).
6. Repetir exactamente el mismo fragmento en varios párrafos (desambiguación o ambiguo).
7. Repetir el fragmento dentro del mismo párrafo.
8. Dividir el texto entre varios runs de Word.
9. Cambiar formato sin cambiar el contenido.
10. Guardar, cerrar y volver a abrir el documento (serialización y recarga).
11. Rechazo de hash SHA-256 de cadena vacía (e3b0c442...).
12. Persistencia en SQLite tras reinicio del servidor (memoria en blanco).
"""
from __future__ import annotations

import os
import tempfile
import unittest
from pydantic import ValidationError

from backend.app.models.apa_models import AnchorModel, EMPTY_SHA256
from backend.app.services.comment_anchor_manager import (
    CommentAnchorManager,
    normalize_text,
    sha256_hash,
)
from backend.app.services.docx_parser import ParagraphInfo, ParsedDocument, RunInfo


def _build_doc(texts: list[str], runs_per_p: list[list[str]] | None = None) -> ParsedDocument:
    paras = []
    for i, t in enumerate(texts):
        h = sha256_hash(t or "[vacio]")[:12]
        r_list = []
        if runs_per_p and i < len(runs_per_p) and runs_per_p[i]:
            cur = 0
            for r_text in runs_per_p[i]:
                r_list.append(
                    RunInfo(
                        text=r_text,
                        font_name="Times New Roman",
                        font_size_pt=12.0,
                        bold=False,
                        italic=False,
                        underline=False,
                        start_offset=cur,
                        end_offset=cur + len(r_text),
                    )
                )
                cur += len(r_text)
        else:
            r_list = [
                RunInfo(
                    text=t,
                    font_name="Times New Roman",
                    font_size_pt=12.0,
                    bold=False,
                    italic=False,
                    underline=False,
                    start_offset=0,
                    end_offset=len(t),
                )
            ]

        paras.append(
            ParagraphInfo(
                index=i,
                text=t,
                style_name="Normal",
                alignment="left",
                line_spacing=2.0,
                space_before_pt=0.0,
                space_after_pt=0.0,
                first_line_indent_in=0.5,
                left_indent_in=0.0,
                paragraph_id=f"p_{i}_{h}",
                paragraph_hash=sha256_hash(t or "[vacio]"),
                runs=r_list,
            )
        )
    return ParsedDocument(
        filename="audit_doc.docx",
        paragraphs=paras,
        sections=[],
        default_font="Times New Roman",
        default_font_size_pt=12.0,
        section_titles=[""] * len(paras),
    )


class TestAudit10Scenarios(unittest.TestCase):

    def setUp(self):
        self.mgr = CommentAnchorManager(db_path=":memory:")

    def test_scenario_1_insert_paragraph_before(self):
        """1. Insertar un párrafo antes de uno que contiene una observación."""
        doc_v1 = _build_doc([
            "Título inicial.",
            "Según García (2020), la teoría es válida.",
        ])
        anc = self.mgr.create_anchor(doc_v1.paragraphs[1], matched_text="García (2020)")
        self.assertEqual(anc.paragraph_index, 1)

        # Inserción de un nuevo párrafo en medio
        doc_v2 = _build_doc([
            "Título inicial.",
            "Nueva dedicatoria introductoria.",
            "Según García (2020), la teoría es válida.",
        ])
        res = self.mgr.resolve_anchor(anc, doc_v2)
        self.assertTrue(res.is_valid)
        self.assertEqual(res.paragraph_index, 2)
        self.assertEqual(res.matched_text, "García (2020)")

    def test_scenario_2_delete_previous_paragraph(self):
        """2. Eliminar un párrafo anterior desplaza el índice hacia arriba pero mantiene el anclaje."""
        doc_v1 = _build_doc([
            "Párrafo que será eliminado.",
            "Párrafo con observación (López, 2019).",
        ])
        anc = self.mgr.create_anchor(doc_v1.paragraphs[1], matched_text="(López, 2019)")
        self.assertEqual(anc.paragraph_index, 1)

        # Eliminamos el primer párrafo
        doc_v2 = _build_doc([
            "Párrafo con observación (López, 2019).",
        ])
        res = self.mgr.resolve_anchor(anc, doc_v2)
        self.assertTrue(res.is_valid)
        self.assertEqual(res.paragraph_index, 0)
        self.assertEqual(res.matched_text, "(López, 2019)")

    def test_scenario_3_modify_text_before_fragment(self):
        """3. Modificar el texto antes del fragmento recalculando los nuevos offsets."""
        doc_v1 = _build_doc(["El estudio realizado por Rodríguez (2021) confirmó el efecto."])
        anc = self.mgr.create_anchor(doc_v1.paragraphs[0], matched_text="Rodríguez (2021)")
        old_start = anc.start_offset

        # Se agregan 30 caracteres al inicio del párrafo
        doc_v2 = _build_doc(["En tiempos recientes y tras varias pruebas, el estudio realizado por Rodríguez (2021) confirmó el efecto."])
        res = self.mgr.resolve_anchor(anc, doc_v2)
        self.assertTrue(res.is_valid)
        self.assertEqual(res.matched_text, "Rodríguez (2021)")
        self.assertGreater(res.start_offset, old_start)

    def test_scenario_4_modify_observed_fragment(self):
        """4. Modificar el fragmento observado (el usuario editó la cita, debe marcarse obsoleto, jamás reasignar)."""
        doc_v1 = _build_doc(["Evidencia según (Martínez, 2018) en la investigación."])
        anc = self.mgr.create_anchor(doc_v1.paragraphs[0], matched_text="(Martínez, 2018)")

        # El usuario corrigió a (Martínez & Gómez, 2018)
        doc_v2 = _build_doc(["Evidencia según (Martínez & Gómez, 2018) en la investigación."])
        res = self.mgr.resolve_anchor(anc, doc_v2)
        self.assertFalse(res.is_valid)
        self.assertTrue(res.is_obsolete)

    def test_scenario_5_delete_observed_fragment(self):
        """5. Eliminar el fragmento observado completamente del párrafo."""
        doc_v1 = _build_doc(["Cita parentética (Pérez, 2015) eliminada posteriormente."])
        anc = self.mgr.create_anchor(doc_v1.paragraphs[0], matched_text="(Pérez, 2015)")

        doc_v2 = _build_doc(["Cita parentética eliminada posteriormente."])
        res = self.mgr.resolve_anchor(anc, doc_v2)
        self.assertFalse(res.is_valid)
        self.assertTrue(res.is_obsolete)

    def test_scenario_6_repeat_exact_fragment_across_multiple_paragraphs(self):
        """6. Repetir exactamente el mismo fragmento en varios párrafos."""
        doc_v1 = _build_doc([
            "En el primer caso, el autor destaca el resultado experimental.",
            "En el segundo caso, el autor destaca el resultado experimental pero con matices.",
            "En el tercer caso, el autor destaca el resultado teórico exclusivamente.",
        ])
        # Anclar específicamente al párrafo 1
        anc_p1 = self.mgr.create_anchor(doc_v1.paragraphs[1], matched_text="el autor destaca")
        self.assertEqual(anc_p1.paragraph_index, 1)

        res = self.mgr.resolve_anchor(anc_p1, doc_v1)
        self.assertTrue(res.is_valid)
        self.assertEqual(res.paragraph_index, 1)

        # Si no hay contexto unívoco posible (fragmentos idénticos sin contexto diferenciable)
        ambiguous_doc = _build_doc([
            "el autor destaca",
            "el autor destaca",
        ])
        anc_amb = AnchorModel(
            document_id="doc",
            document_version="1",
            paragraph_id="unknown_p",
            paragraph_index=99,
            start_offset=0,
            end_offset=len("el autor destaca"),
            matched_text="el autor destaca",
            fragment_hash=sha256_hash("el autor destaca"),
            context_before="",
            context_after="",
        )
        res_amb = self.mgr.resolve_anchor(anc_amb, ambiguous_doc)
        self.assertFalse(res_amb.is_valid)
        self.assertTrue(res_amb.is_ambiguous)

    def test_scenario_7_repeat_fragment_inside_same_paragraph(self):
        """7. Repetir el fragmento dentro del mismo párrafo (desambiguación por contexto)."""
        doc = _build_doc([
            "Al inicio se cita a Torres (2020) y luego se vuelve a citar a Torres (2020) al final."
        ])
        p = doc.paragraphs[0]
        # Primer Torres (2020)
        anc1 = self.mgr.create_anchor(p, matched_text="Torres (2020)", start_offset=18, end_offset=31)
        # Segundo Torres (2020)
        anc2 = self.mgr.create_anchor(p, matched_text="Torres (2020)", start_offset=62, end_offset=75)

        res1 = self.mgr.resolve_anchor(anc1, doc)
        res2 = self.mgr.resolve_anchor(anc2, doc)
        self.assertTrue(res1.is_valid)
        self.assertEqual(res1.start_offset, 18)
        self.assertTrue(res2.is_valid)
        self.assertEqual(res2.start_offset, 62)

    def test_scenario_8_split_text_across_multiple_runs(self):
        """8. Dividir el texto entre varios runs de Word."""
        runs_split = [["Según ", "Vygotsky", " (1978), la zona de desarrollo próximal."]]
        doc = _build_doc(["Según Vygotsky (1978), la zona de desarrollo próximal."], runs_per_p=runs_split)
        p = doc.paragraphs[0]
        anc = self.mgr.create_anchor(p, matched_text="Vygotsky (1978)")
        # Abarca run 1 ("Vygotsky") y run 2 (" (1978), la zona...")
        self.assertIn(1, anc.run_indices)
        self.assertIn(2, anc.run_indices)

    def test_scenario_9_change_formatting_without_changing_content(self):
        """9. Cambiar formato de run (negrita, tamaño) sin cambiar contenido."""
        doc_plain = _build_doc(["Texto con cita (Hernández, 2022)."])
        anc = self.mgr.create_anchor(doc_plain.paragraphs[0], matched_text="(Hernández, 2022)")

        # En la versión 2, la cita se puso en cursiva
        doc_formatted = _build_doc(["Texto con cita (Hernández, 2022)."])
        doc_formatted.paragraphs[0].runs[0].italic = True
        res = self.mgr.resolve_anchor(anc, doc_formatted)
        self.assertTrue(res.is_valid)
        self.assertEqual(res.matched_text, "(Hernández, 2022)")

    def test_scenario_10_save_close_reopen_lifecycle(self):
        """10. Guardar, cerrar y volver a abrir el documento (serialización JSON y recarga)."""
        doc = _build_doc(["Texto persistente con (Castillo, 2023)."])
        anc = self.mgr.create_anchor(doc.paragraphs[0], matched_text="(Castillo, 2023)")
        
        # Simular guardado a JSON
        dumped_json = anc.model_dump_json()

        # Simular re-apertura desde JSON en una sesión limpia
        reloaded_anc = AnchorModel.model_validate_json(dumped_json)
        self.assertEqual(reloaded_anc.matched_text, "(Castillo, 2023)")
        self.assertEqual(reloaded_anc.fragment_hash, anc.fragment_hash)

        # Resolver contra documento re-abierto
        res = self.mgr.resolve_anchor(reloaded_anc, doc)
        self.assertTrue(res.is_valid)
        self.assertEqual(res.matched_text, "(Castillo, 2023)")

    def test_empty_string_hash_rejection(self):
        """11. Rechazo estricto del hash SHA-256 de cadena vacía (e3b0c442...)."""
        with self.assertRaises(ValidationError) as ctx:
            AnchorModel(
                document_id="doc_test",
                document_version="1.0",
                paragraph_id="p_1",
                paragraph_index=0,
                start_offset=0,
                end_offset=5,
                matched_text="texto",
                fragment_hash=EMPTY_SHA256,
            )
        self.assertIn("e3b0c442", str(ctx.exception))

    def test_sqlite_persistence_across_server_restarts(self):
        """12. Simulación de reinicio del servidor: recuperación del historial desde SQLite."""
        tf = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        db_path = tf.name
        tf.close()

        try:
            # Sesión 1 del servidor
            mgr1 = CommentAnchorManager(db_path=db_path)
            doc = _build_doc(["Párrafo histórico para auditoría."])
            anc = mgr1.create_anchor(doc.paragraphs[0], matched_text="Párrafo histórico")
            record = mgr1.record_analysis_version("doc_tesis_456", "v1.0", doc, [anc])
            self.assertEqual(record.document_id, "doc_tesis_456")

            # Simular reinicio del servidor (destrucción de memoria y nueva instancia conectada al archivo)
            del mgr1
            mgr2 = CommentAnchorManager(db_path=db_path)
            # En mgr2, self._history está completamente vacío en memoria
            self.assertEqual(len(mgr2._history), 0)

            # Recuperación del historial persistido
            history = mgr2.get_version_history("doc_tesis_456")
            self.assertEqual(len(history), 1)
            self.assertEqual(history[0].document_id, "doc_tesis_456")
            self.assertEqual(history[0].document_version, "v1.0")
            self.assertEqual(len(history[0].anchors), 1)
            self.assertEqual(history[0].anchors[0]["matched_text"], "Párrafo histórico")
        finally:
            try:
                if os.path.exists(db_path):
                    os.remove(db_path)
            except OSError:
                pass


if __name__ == "__main__":
    unittest.main()
