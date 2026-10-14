from __future__ import annotations

import html
from datetime import datetime

from backend.app.services.analyzer import AnalysisResult

SEVERITY_LABEL = {
    "error": "Error",
    "warning": "Advertencia",
    "info": "Observacion",
}

SEVERITY_COLOR = {
    "error": "#c0392b",
    "warning": "#d68910",
    "info": "#2471a3",
}


def build_report(result: AnalysisResult, ai_findings: list | None = None) -> dict:
    findings = list(result.findings)
    if ai_findings:
        findings.extend(ai_findings)
    # el resumen se recalcula DESPUES de fusionar los hallazgos de la IA: si no,
    # el JSON y el HTML se contradicen (findings=3 pero total_findings=1)
    summary = dict(result.summary)
    by_severity = {sev: 0 for sev in ("error", "warning", "info")}
    by_category: dict[str, int] = {}
    for f in findings:
        sev = f.severity.value if hasattr(f.severity, "value") else str(f.severity)
        by_severity[sev] = by_severity.get(sev, 0) + 1
        cat = f.category.value if hasattr(f.category, "value") else str(f.category)
        by_category[cat] = by_category.get(cat, 0) + 1
    summary["total_findings"] = len(findings)
    summary["by_severity"] = by_severity
    summary["by_category"] = by_category

    payload = {
        "filename": result.filename,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "summary": summary,
        "findings": [f.to_dict() for f in findings],
    }
    if ai_findings:
        payload["ai_review"] = {
            "used": True,
            "notes": getattr(result, "ai_notes", []) or [],
        }
    return payload


def render_html(report: dict) -> str:
    summary = report.get("summary", {})
    rows = []
    for f in report.get("findings", []):
        sev = f.get("severity", "info")
        extra = f.get("extra") or {}
        detail = html.escape(f.get("message", ""))
        if f.get("suggestion"):
            detail += f"<br><em>{html.escape(f['suggestion'])}</em>"
        if extra.get("bib_kind") or extra.get("ai_missing"):
            detail += (
                f'<br><small>Tipo: {html.escape(str(extra.get("ai_source_type") or extra.get("bib_kind")))}'
            )
            if extra.get("ai_confidence") is not None:
                detail += f" · confianza {round(float(extra['ai_confidence']) * 100)}%"
            detail += "</small>"
        if f.get("excerpt"):
            detail += f'<br><small>{html.escape(f["excerpt"][:160])}</small>'
        badge = (
            f'<span class="badge" style="background:#6b4fbb">IA</span> '
            if str(f.get("rule_id", "")).startswith("AI-")
            else ""
        )
        rows.append(
            "<tr>"
            f'<td><span class="badge" style="background:{SEVERITY_COLOR.get(sev, "#555")}">'
            f'{html.escape(SEVERITY_LABEL.get(sev, sev))}</span></td>'
            f'<td>{html.escape(f.get("category", ""))}</td>'
            f'<td>{badge}{html.escape(f.get("rule_id", ""))}</td>'
            f'<td>{html.escape(f.get("location", ""))}</td>'
            f"<td>{detail}</td>"
            "</tr>"
        )

    by_sev = summary.get("by_severity", {})
    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<title>Informe APA - {html.escape(report.get("filename", ""))}</title>
<style>
 body {{ font-family: Segoe UI, Arial, sans-serif; margin: 2rem; color: #1b2631; }}
 h1 {{ font-size: 1.4rem; }}
 .meta {{ color: #566573; margin-bottom: 1rem; }}
 .cards {{ display: flex; gap: 1rem; flex-wrap: wrap; margin: 1rem 0 2rem; }}
 .card {{ border: 1px solid #d5d8dc; border-radius: 8px; padding: 1rem; min-width: 140px; }}
 .card .num {{ font-size: 1.8rem; font-weight: 700; }}
 .score {{ color: #1e8449; }}
 table {{ border-collapse: collapse; width: 100%; }}
 th, td {{ border: 1px solid #d5d8dc; padding: 8px; text-align: left; vertical-align: top; font-size: 0.9rem; }}
 th {{ background: #f4f6f7; }}
 .badge {{ color: #fff; padding: 2px 8px; border-radius: 10px; font-size: 0.75rem; }}
</style>
</head>
<body>
 <h1>Informe de cumplimiento de normas APA</h1>
 <p class="meta">Documento: <strong>{html.escape(report.get("filename", ""))}</strong><br>
 Generado: {html.escape(report.get("generated_at", ""))}</p>
 <div class="cards">
   <div class="card"><div class="num score">{summary.get("compliance_score", 0)}%</div><div>Nivel de cumplimiento</div></div>
   <div class="card"><div class="num">{summary.get("total_findings", 0)}</div><div>Hallazgos</div></div>
   <div class="card"><div class="num" style="color:{SEVERITY_COLOR['error']}">{by_sev.get("error", 0)}</div><div>Errores</div></div>
   <div class="card"><div class="num" style="color:{SEVERITY_COLOR['warning']}">{by_sev.get("warning", 0)}</div><div>Advertencias</div></div>
   <div class="card"><div class="num" style="color:{SEVERITY_COLOR['info']}">{by_sev.get("info", 0)}</div><div>Observaciones</div></div>
 </div>
 <table>
   <thead><tr><th>Gravedad</th><th>Categoria</th><th>Regla</th><th>Ubicacion</th><th>Detalle</th></tr></thead>
   <tbody>
     {''.join(rows) if rows else '<tr><td colspan="5">Sin hallazgos. El documento cumple los criterios verificados.</td></tr>'}
   </tbody>
 </table>
 <p class="meta" style="margin-top:2rem">Informe automatico de apoyo. No sustituye la revision de un asesor humano.</p>
</body>
</html>"""
