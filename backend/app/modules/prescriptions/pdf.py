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


def _format_address(address: Any) -> str:
    """Full address line for the letterhead (billing _format_address mirror:
    street + postal/city + country)."""
    if not isinstance(address, dict):
        return _e(address) if address else ""
    parts = []
    if address.get("street"):
        parts.append(address["street"])
    city_line = " ".join(filter(None, [address.get("postal_code"), address.get("city")]))
    if city_line:
        parts.append(city_line)
    if address.get("country"):
        parts.append(address["country"])
    return _e(", ".join(parts))


def _get_labels(locale: str) -> dict[str, str]:
    """Localized captions for the PDF (billing _get_labels approach:
    es + en sets, English fallback until translated)."""
    labels_es = {
        "date": "Fecha",
        "patient": "Paciente",
        "prescriber": "Prescriptor",
        "license": "Licencia n.º",
        "medication": "Medicamento",
        "dose": "Dosis",
        "route": "Vía",
        "frequency": "Frecuencia",
        "duration": "Duración",
        "instructions": "Instrucciones",
        "notes": "Notas",
        "draft": "BORRADOR",
        "cancelled": "CANCELADA",
    }
    labels_en = {
        "date": "Date",
        "patient": "Patient",
        "prescriber": "Prescriber",
        "license": "License no.",
        "medication": "Medication",
        "dose": "Dose",
        "route": "Route",
        "frequency": "Frequency",
        "duration": "Duration",
        "instructions": "Instructions",
        "notes": "Notes",
        "draft": "DRAFT",
        "cancelled": "CANCELLED",
    }
    if locale == "es":
        return labels_es
    # fr/pt/de/hu/pl/it/ar/ta: English labels until translated.
    return labels_en


def build_pdf_data(
    prescription: Any,
    items: list[Any],
    patient_name: str,
    clinic: dict[str, Any],
    hook_data: dict[str, Any] | None = None,
    label_overrides: dict[str, str] | None = None,
    locale: str = "es",
) -> dict[str, Any]:
    """Structured, already-escaped PDF payload for the renderer.

    Captions follow ``prescription.locale`` (hook ``label_overrides``
    win over the built-in sets). Non-issued rows carry a visible
    status mark instead of being refused — a cancelled copy stays
    printable for the record.
    """
    labels = _get_labels(locale)
    labels = {**labels, **(label_overrides or {})}
    status = getattr(prescription, "status", "issued")
    return {
        "clinic_name": _e(clinic.get("name")),
        "clinic_address": _format_address(clinic.get("address")),
        "labels": {key: _e(value) for key, value in labels.items()},
        "status": status,
        "status_mark": _e(labels.get("draft" if status == "draft" else "cancelled", "")),
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
    labels = data["labels"]
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
    mark = f"<p class='mark'>{data['status_mark']}</p>" if data["status"] != "issued" else ""
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
body {{ font-family: sans-serif; margin: 2cm; }}
h1 {{ font-size: 20px; }}
table {{ width: 100%; border-collapse: collapse; margin-top: 1em; }}
td, th {{ border: 1px solid #999; padding: 6px; font-size: 12px; }}
.notice {{ font-size: 11px; color: #444; }}
.mark {{ font-size: 18px; font-weight: bold; border: 2px solid #000; padding: 6px; text-align: center; }}
.signature {{ margin-top: 3em; }}
</style></head><body>
<h1>{data["clinic_name"]}</h1>
<p>{data["clinic_address"]}</p>
{mark}
<p>{labels["date"]}: {data["date"]} — {labels["patient"]}: {data["patient_name"]}</p>
<p>{labels["prescriber"]}: {data["prescriber_name"]} ({data["license_label"]}: {data["license_number"]})</p>
<table><tr><th>{labels["medication"]}</th><th>{labels["dose"]}</th><th>{labels["route"]}</th>
<th>{labels["frequency"]}</th><th>{labels["duration"]}</th><th>{labels["instructions"]}</th></tr>{rows}</table>
<p>{labels["notes"]}: {data["notes"]}</p>
{compliance}{notices}
</body></html>"""


def render_pdf_bytes(data: dict[str, Any]) -> bytes:
    """HTML → PDF via WeasyPrint (same thread-offload posture as billing:
    callers run this in a worker thread; here the route does)."""
    from weasyprint import HTML

    return HTML(string=render_html(data)).write_pdf()
