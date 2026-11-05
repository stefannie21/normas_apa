"""Pruebas de Rendimiento, Estrés, Concurrencia y Persistencia (Secciones 5 y 7).

Mide empíricamente:
- Tiempos de extracción y análisis para 20, 50, 80 y 150 páginas.
- Consumo de memoria (tracemalloc peak RAM).
- Concurrencia en SQLite con múltiples hilos simultáneos (threads).
- Manejo de fallos y respaldo en base de datos.
"""
from __future__ import annotations

import concurrent.futures
import io
import os
import tempfile
import time
import tracemalloc
import unittest

from docx import Document
from docx.shared import Inches, Pt

from backend.app.services.analyzer import analyze
from backend.app.services.comment_anchor_manager import CommentAnchorManager, sha256_hash
from backend.app.services.docx_parser import parse_docx


def generate_doc_with_pages(target_pages: int) -> bytes:
    """Genera un DOCX con la cantidad aproximada de páginas indicada (2.5 párrafos/pág)."""
    doc = Document()
    for s in doc.sections:
        s.top_margin = Inches(1)
        s.bottom_margin = Inches(1)
        s.left_margin = Inches(1)
        s.right_margin = Inches(1)

    normal = doc.styles["Normal"]
    normal.font.name = "Times New Roman"
    normal.font.size = Pt(12)
    normal.paragraph_format.line_spacing = 2.0

    doc.add_heading(f"Documento de Prueba de Rendimiento ({target_pages} páginas)", level=1)
    doc.add_paragraph("Introducción al análisis de carga y volumen del motor APA 7.")

    paragraphs_needed = target_pages * 3  # ~3 párrafos dobles por página

    for i in range(paragraphs_needed):
        if i % 15 == 0:
            doc.add_heading(f"Sección de Análisis {i // 15 + 1}", level=2)
        p = doc.add_paragraph(
            f"Párrafo de prueba número {i + 1}. El análisis metodológico riguroso requiere validación "
            f"continua de la literatura científica (García, 2020). La evidencia empírica corrobora la "
            f"hipótesis planteada en el diseño experimental inicial."
        )
        p.paragraph_format.first_line_indent = Inches(0.5)

    # Sección de referencias
    doc.add_heading("Referencias", level=1)
    ref = doc.add_paragraph("García, A. (2020). Metodología de la investigación. Editorial Universitaria.")
    ref.paragraph_format.left_indent = Inches(0.5)
    ref.paragraph_format.first_line_indent = Inches(-0.5)

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


class TestPerformanceAndStress(unittest.TestCase):

    def test_performance_scaling_by_page_size(self):
        """Mide tiempos reales de extracción, reglas deterministas y memoria en 20, 50, 80 y 150 páginas."""
        page_sizes = [20, 50, 80, 150]
        results = []

        print("\n--- BENCHMARK DE RENDIMIENTO POR TAMAÑO DE DOCUMENTO ---")
        print(f"{'Páginas':<10} | {'Párrafos':<10} | {'Extracción':<12} | {'Reglas Python':<14} | {'Total':<10} | {'RAM Pico (MB)':<12}")
        print("-" * 75)

        for pages in page_sizes:
            tracemalloc.start()
            t0 = time.time()
            docx_data = generate_doc_with_pages(pages)

            # 1. Extracción
            t_extract_start = time.time()
            parsed_doc = parse_docx(docx_data, filename=f"doc_{pages}p.docx")
            t_extract = round(time.time() - t_extract_start, 3)

            # 2. Análisis Determinista Python
            t_rules_start = time.time()
            rule_res = analyze(parsed_doc)
            t_rules = round(time.time() - t_rules_start, 3)

            t_total = round(time.time() - t0, 3)
            current_mem, peak_mem = tracemalloc.get_traced_memory()
            tracemalloc.stop()

            peak_mb = round(peak_mem / (1024 * 1024), 2)
            para_count = len(parsed_doc.paragraphs)

            results.append({
                "pages": pages,
                "paras": para_count,
                "extract_sec": t_extract,
                "rules_sec": t_rules,
                "total_sec": t_total,
                "peak_mb": peak_mb,
                "findings": len(rule_res.findings),
            })

            print(f"{pages:<10} | {para_count:<10} | {t_extract:<10.3f} s | {t_rules:<12.3f} s | {t_total:<8.3f} s | {peak_mb:<12.2f}")

        # Comprobaciones de calidad de rendimiento
        for r in results:
            self.assertLess(r["rules_sec"], 3.0, f"Las reglas de Python no deben demorar más de 3s en {r['pages']} páginas")
            self.assertLess(r["peak_mb"], 100.0, f"El consumo de RAM no debe superar 100MB en {r['pages']} páginas")

    def test_sqlite_concurrency_and_data_integrity(self):
        """Prueba de concurrencia en SQLite con 10 hilos simultáneos escribiendo registros."""
        tf = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        db_path = tf.name
        tf.close()

        try:
            mgr = CommentAnchorManager(db_path=db_path)
            num_workers = 10
            docs_per_worker = 5

            def worker_task(worker_id: int):
                local_mgr = CommentAnchorManager(db_path=db_path)
                docx_bytes = generate_doc_with_pages(2)
                parsed = parse_docx(docx_bytes, filename=f"doc_w{worker_id}.docx")
                for d_idx in range(docs_per_worker):
                    doc_id = f"worker_{worker_id}_doc_{d_idx}"
                    anc = local_mgr.create_anchor(parsed.paragraphs[0], matched_text="Documento")
                    local_mgr.record_analysis_version(
                        document_id=doc_id,
                        document_version="1.0",
                        document=parsed,
                        anchors=[anc],
                    )
                return worker_id

            with concurrent.futures.ThreadPoolExecutor(max_workers=num_workers) as executor:
                futures = [executor.submit(worker_task, w) for w in range(num_workers)]
                completed = [f.result() for f in concurrent.futures.as_completed(futures)]

            self.assertEqual(len(completed), num_workers)

            # Verificar integridad tras concurrencia
            verify_mgr = CommentAnchorManager(db_path=db_path)
            total_records_found = 0
            for w in range(num_workers):
                for d in range(docs_per_worker):
                    h = verify_mgr.get_version_history(f"worker_{w}_doc_{d}")
                    if h:
                        total_records_found += len(h)

            expected_records = num_workers * docs_per_worker
            self.assertEqual(total_records_found, expected_records, f"Se esperaban {expected_records} registros íntegros en SQLite")
            print(f"\n[OK] Concurrencia SQLite validada: {expected_records} registros escritos y leídos concurrentemente sin bloqueos.")
        finally:
            try:
                if os.path.exists(db_path):
                    os.remove(db_path)
            except OSError:
                pass


if __name__ == "__main__":
    unittest.main()
