"""Pruebas unitarias completas del sistema de anclaje (Fase 10 - Pruebas de anclaje).

Escenarios cubiertos:
1. Dos párrafos con el mismo texto.
2. Dos fragmentos iguales dentro de un párrafo (desambiguación o marcado como ambiguo).
3. Fragmento al inicio del párrafo.
4. Fragmento al final del párrafo.
5. Párrafo dividido en múltiples runs.
6. Modificación de palabras en el párrafo.
7. Eliminación del fragmento (detección de obsolescencia).
8. Inserción de nuevos párrafos / reordenamiento.
9. Integridad del hash SHA-256 y normalización.
"""
from __future__ import annotations

import unittest
from backend.app.services.comment_anchor_manager import (
    CommentAnchorManager,
    normalize_text,
    sha256_hash,
)
from backend.app.services.docx_parser import ParagraphInfo, ParsedDocument, RunInfo


def _make_dummy_doc(paragraphs_text: list[str]) -> ParsedDocument:
    """Crea un ParsedDocument sintético para pruebas posicionales."""
    paras = []
    for i, t in enumerate(paragraphs_text):
        h = sha256_hash(t)[:12]
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
                paragraph_hash=sha256_hash(t),
                runs=[RunInfo(text=t, font_name="Times New Roman", font_size_pt=12.0, bold=False, italic=False, underline=False, start_offset=0, end_offset=len(t))],
            )
        )
    return ParsedDocument(
        filename="test.docx",
        paragraphs=paras,
        sections=[],
        default_font="Times New Roman",
        default_font_size_pt=12.0,
        section_titles=[""] * len(paras),
    )


class TestCommentAnchorManager(unittest.TestCase):

    def test_hash_normalization(self):
        """El hash SHA-256 debe ser idéntico independientemente de espacios redundantes."""
        t1 = "El   método científico  es riguroso."
        t2 = "El método científico es riguroso."
        self.assertEqual(sha256_hash(t1), sha256_hash(t2))
        self.assertEqual(len(sha256_hash(t1)), 64)

    def test_fragment_at_start(self):
        """Fragmento ubicado exactamente al inicio del párrafo (offset 0)."""
        mgr = CommentAnchorManager()
        doc = _make_dummy_doc(["Introducción general al estudio de campo."])
        p = doc.paragraphs[0]
        anc = mgr.create_anchor(p, matched_text="Introducción general")
        self.assertEqual(anc.start_offset, 0)
        self.assertEqual(anc.end_offset, len("Introducción general"))
        self.assertEqual(anc.matched_text, "Introducción general")

        # Resolución contra el mismo documento
        res = mgr.resolve_anchor(anc, doc)
        self.assertTrue(res.is_valid)
        self.assertEqual(res.start_offset, 0)
        self.assertEqual(res.end_offset, len("Introducción general"))

    def test_fragment_at_end(self):
        """Fragmento ubicado exactamente al final del párrafo."""
        mgr = CommentAnchorManager()
        doc = _make_dummy_doc(["La investigación concluye en el año 2026."])
        p = doc.paragraphs[0]
        anc = mgr.create_anchor(p, matched_text="año 2026.")
        self.assertEqual(anc.matched_text, "año 2026.")
        self.assertEqual(anc.end_offset, len(p.text))

        res = mgr.resolve_anchor(anc, doc)
        self.assertTrue(res.is_valid)
        self.assertEqual(res.end_offset, len(p.text))

    def test_two_identical_paragraphs(self):
        """Dos párrafos con texto idéntico deben diferenciarse por su paragraph_id e índice."""
        mgr = CommentAnchorManager()
        doc = _make_dummy_doc([
            "Este es un párrafo repetido exactamente.",
            "Este es un párrafo repetido exactamente.",
        ])
        p0 = doc.paragraphs[0]
        p1 = doc.paragraphs[1]
        self.assertEqual(p0.index, 0)
        self.assertEqual(p1.index, 1)

        anc0 = mgr.create_anchor(p0, matched_text="párrafo repetido")
        anc1 = mgr.create_anchor(p1, matched_text="párrafo repetido")

        res0 = mgr.resolve_anchor(anc0, doc)
        res1 = mgr.resolve_anchor(anc1, doc)

        self.assertEqual(res0.paragraph_index, 0)
        self.assertEqual(res1.paragraph_index, 1)

    def test_two_identical_fragments_in_same_paragraph(self):
        """Dos fragmentos iguales en el mismo párrafo se desambiguan por contexto."""
        mgr = CommentAnchorManager()
        text = "El modelo lineal y el modelo cuadrático fueron comparados."
        doc = _make_dummy_doc([text])
        p = doc.paragraphs[0]

        # Primer 'modelo' (índice 3)
        anc1 = mgr.create_anchor(p, matched_text="modelo", start_offset=3, end_offset=9)
        # Segundo 'modelo' (índice 22)
        anc2 = mgr.create_anchor(p, matched_text="modelo", start_offset=22, end_offset=28)

        res1 = mgr.resolve_anchor(anc1, doc)
        res2 = mgr.resolve_anchor(anc2, doc)

        self.assertTrue(res1.is_valid)
        self.assertEqual(res1.start_offset, 3)
        self.assertTrue(res2.is_valid)
        self.assertEqual(res2.start_offset, 22)

    def test_multiple_runs_mapping(self):
        """Un fragmento que abarca múltiples runs de Word debe mapear todos los índices."""
        mgr = CommentAnchorManager()
        p = ParagraphInfo(
            index=0,
            text="Texto en negrita y cursiva",
            style_name="Normal",
            alignment="left",
            line_spacing=2.0,
            space_before_pt=0.0,
            space_after_pt=0.0,
            first_line_indent_in=0.5,
            left_indent_in=0.0,
            runs=[
                RunInfo(text="Texto en ", font_name="Times", font_size_pt=12.0, bold=False, italic=False, underline=False),
                RunInfo(text="negrita", font_name="Times", font_size_pt=12.0, bold=True, italic=False, underline=False),
                RunInfo(text=" y cursiva", font_name="Times", font_size_pt=12.0, bold=False, italic=True, underline=False),
            ],
        )
        # Anclaje sobre "en negrita y"
        anc = mgr.create_anchor(p, matched_text="en negrita y")
        # Abarca run 0 ("Texto en "), run 1 ("negrita") y run 2 (" y cursiva")
        self.assertEqual(anc.run_indices, [0, 1, 2])

    def test_word_modification_recovery(self):
        """Si se insertan palabras antes del fragmento en el párrafo, se recalculan los offsets."""
        mgr = CommentAnchorManager()
        doc_v1 = _make_dummy_doc(["Según García (2020), la educación es clave."])
        p1 = doc_v1.paragraphs[0]
        anc = mgr.create_anchor(p1, matched_text="García (2020)")

        # En versión 2 se añade texto antes: "Por tanto, según García (2020)..."
        doc_v2 = _make_dummy_doc(["Por tanto, según García (2020), la educación es clave."])
        res = mgr.resolve_anchor(anc, doc_v2)

        self.assertTrue(res.is_valid)
        self.assertEqual(res.matched_text, "García (2020)")
        self.assertGreater(res.start_offset, anc.start_offset)

    def test_fragment_deletion_marked_obsolete(self):
        """Si el usuario elimina el fragmento señalado, el anclaje debe marcarse como obsoleto."""
        mgr = CommentAnchorManager()
        doc_v1 = _make_dummy_doc(["Cita a eliminar (López, 2018) en el texto."])
        p1 = doc_v1.paragraphs[0]
        anc = mgr.create_anchor(p1, matched_text="(López, 2018)")

        # Versión 2 sin la cita
        doc_v2 = _make_dummy_doc(["Cita a eliminar en el texto sin autor."])
        res = mgr.resolve_anchor(anc, doc_v2)

        self.assertFalse(res.is_valid)
        self.assertTrue(res.is_obsolete)

    def test_paragraph_insertion_reordering(self):
        """Si se insertan párrafos al inicio, el anclaje sigue al párrafo reubicado."""
        mgr = CommentAnchorManager()
        doc_v1 = _make_dummy_doc(["Párrafo uno.", "Párrafo dos con (Pérez, 2021)."])
        p_target = doc_v1.paragraphs[1]
        anc = mgr.create_anchor(p_target, matched_text="(Pérez, 2021)")
        self.assertEqual(anc.paragraph_index, 1)

        # Versión 2 con 2 párrafos nuevos antes
        doc_v2 = _make_dummy_doc([
            "Nuevo título preliminar.",
            "Nueva dedicatoria.",
            "Párrafo uno.",
            "Párrafo dos con (Pérez, 2021).",
        ])
        res = mgr.resolve_anchor(anc, doc_v2)
        self.assertTrue(res.is_valid)
        self.assertEqual(res.paragraph_index, 3)
        self.assertEqual(res.matched_text, "(Pérez, 2021)")


if __name__ == "__main__":
    unittest.main()
