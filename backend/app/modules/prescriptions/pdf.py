"""Prescription PDF rendering (WeasyPrint, download/print only).

Follows the billing escaped-structured contract: the base renderer
builds HTML from escaped values only; country hooks contribute
structured rows (``compliance_section``), notices, label overrides and
optional QR data — never HTML (PR #210 rule). No email delivery in v1
(MX pharmacies reject emailed prescriptions).
"""

from __future__ import annotations

import html
from datetime import datetime
from typing import Any


def _e(value: Any) -> str:
    return html.escape("" if value is None else str(value))


def build_pdf_data(
    prescription: Any,
    items: list[Any],
    patient_name: str,
    clinic: dict[str, Any],
    hook_data: dict[str, Any] | None = None,
    label_overrides: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Structured, already-escaped PDF payload for the renderer."""
    labels = {"license": "License no.", **(label_overrides or {})}
    return {
        "clinic_name": _e(clinic.get("name")),
        "clinic_address": _e(clinic.get("address")),
        "date": _e(
            prescription.issued_at.strftime("%Y-%m-%d")
            if prescription.issued_at
            else datetime.now().strftime("%Y-%m-%d")
        ),
        "patient_name": _e(patient_name),
        "prescriber_name": _e(prescription.prescriber_name),
        "license_label": _e(labels["license"]),
        "license_number": _e(prescription.license_number),
        "notes": _e(prescription.notes),
        "items": [
            {
                "name": _e(item.medication_name),
                "dosage": _e(item.dosage),
                "unit": _e(item.unit),
                "route": _e(item.route),
                "frequency": _e(item.frequency),
                "duration": _e(item.duration),
                "instructions": _e(item.instructions),
            }
            for item in items
        ],
        "compliance_section": [
            {"label": _e(row.get("label")), "value": _e(row.get("value"))}
            for row in (hook_data or {}).get("compliance_section", [])
        ],
        "legal_notices": [_e(n) for n in (hook_data or {}).get("legal_notices", [])],
    }


def render_html(data: dict[str, Any]) -> str:
    """Render the escaped payload to HTML (WeasyPrint input)."""
    rows = "".join(
        "<tr><td>{name}</td><td>{dosage} {unit}</td><td>{route}</td>"
        "<td>{frequency}</td><td>{duration}</td><td>{instructions}</td></tr>".format(**item)
        for item in data["items"]
    )
    compliance = "".join(
        f"<p><strong>{row['label']}:</strong> {row['value']}</p>"
        for row in data["compliance_section"]
    )
    notices = "".join(f"<p class='notice'>{notice}</p>" for notice in data["legal_notices"])
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
body {{ font-family: sans-serif; margin: 2cm; }}
h1 {{ font-size: 20px; }}
table {{ width: 100%; border-collapse: collapse; margin-top: 1em; }}
td, th {{ border: 1px solid #999; padding: 6px; font-size: 12px; }}
.notice {{ font-size: 11px; color: #444; }}
.signature {{ margin-top: 3em; }}
</style></head><body>
<h1>{data["clinic_name"]}</h1>
<p>{data["clinic_address"]}</p>
<p>Date: {data["date"]} — Patient: {data["patient_name"]}</p>
<p>Prescriber: {data["prescriber_name"]} ({data["license_label"]}: {data["license_number"]})</p>
<table><tr><th>Medication</th><th>Dose</th><th>Route</th>
<th>Frequency</th><th>Duration</th><th>Instructions</th></tr>{rows}</table>
<p>{data["notes"]}</p>
{compliance}{notices}
</body></html>"""


def render_pdf_bytes(data: dict[str, Any]) -> bytes:
    """HTML → PDF via WeasyPrint (same thread-offload posture as billing:
    callers run this in a worker thread; here the route does)."""
    from weasyprint import HTML

    return HTML(string=render_html(data)).write_pdf()
