"""Pruebas basicas del motor de reglas. Ejecutar: python tests/run_checks.py

Cubre el motor de formato y el bloque de citas/referencias (Fase 1).
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tests.make_citas_sample import build_citas_sample  # noqa: E402
from tests.make_sample import build_sample  # noqa: E402
from backend.app.services.analyzer import analyze  # noqa: E402
from backend.app.services.docx_parser import parse_docx  # noqa: E402
from backend.app.services.report import build_report, render_html  # noqa: E402


def check_formato() -> None:
    document = parse_docx(build_sample(), "sample_tesis.docx")

    assert len(document.sections) >= 1, "Debe detectar al menos una seccion"
    assert document.references_start is not None, "Debe detectar la seccion de referencias"

    result = analyze(document)
    rule_ids = {f.rule_id for f in result.findings}

    expected = {
        "FORMAT-001", "FORMAT-002", "FORMAT-004", "FORMAT-005", "FORMAT-006",
        "HEAD-002", "HEAD-003", "CIT-001", "CIT-002", "CIT-004", "REF-003", "REF-005",
    }
    missing = expected - rule_ids
    assert not missing, f"No se dispararon reglas esperadas: {missing}"

    report = build_report(result)
    assert report["findings"], "El informe debe contener hallazgos"
    assert report["summary"]["total_findings"] == len(result.findings)
    assert "Informe de cumplimiento" in render_html(report)

    print(f"[formato]   {document.filename}")
    print(f"            {result.summary['total_findings']} hallazgos, "
          f"cumplimiento {result.summary['compliance_score']}%")
    print(f"            reglas: {', '.join(sorted(rule_ids))}")


def check_citas() -> None:
    document = parse_docx(build_citas_sample(), "sample_citas.docx")
    result = analyze(document)
    rule_ids = {f.rule_id for f in result.findings}

    # Cada caso del documento de prueba debe ser detectado por su regla.
    expected = {
        "CRUCE-001",  # cita sin referencia (Delgado, OMS)
        "CRUCE-002",  # referencia sin citar (Zapata, Alvarez, Autor1...)
        "CRUCE-003",  # ano inconsistente (Soto 2021 vs 2019)
        "REF-003",    # orden alfabetico
        "REF-006",    # cursivas faltantes
        "REF-007",    # mas de 20 autores
        "REF-008",    # autor corporativo sin sigla
        "CIT-004",    # cita textual sin pagina
        "CIT-005",    # 3+ autores sin 'et al.'
        "CIT-006",    # cita en bloque entrecomillada
    }
    missing = expected - rule_ids
    assert not missing, f"No se dispararon reglas de citas esperadas: {missing}"

    bib = document.bibliography
    assert bib.references_start is not None, "Debe detectar 'Referencias'"
    assert len(bib.references) >= 7, f"Se esperaban 7 referencias, hay {len(bib.references)}"
    assert len(bib.citations) >= 5, f"Se esperaban varias citas, hay {len(bib.citations)}"

    # cita sin referencia debe(listarse
    missing_refs = bib.missing_references()
    assert any("Delgado" in " ".join(c.surnames) for c in missing_refs), \
        "Debe detectar la cita de Delgado sin referencia"
    # referencia sin citar debe listarse
    uncited = bib.uncited_references()
    assert any("Zapata" in r.surnames for r in uncited), \
        "Debe detectar la referencia de Zapata sin citar"

    print(f"[citas]     {document.filename}")
    print(f"            {len(bib.citations)} citas, {len(bib.references)} referencias, "
          f"{result.summary['total_findings']} hallazgos")
    print(f"            reglas: {', '.join(sorted(rule_ids))}")


def check_score() -> None:
    """Un documento limpio debe puntuar alto."""
    from tests.check_score import main as score_main  # noqa: E402

    score_main()


def main() -> int:
    check_formato()
    print()
    check_citas()
    print()
    check_score()
    print()
    print("OK - todas las verificaciones pasaron")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())