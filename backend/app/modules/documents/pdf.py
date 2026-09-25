"""Branded PDF rendering for generated clinical documents.

Renders a prescription, medical certificate, referral letter or
radiology request as a clinic-branded PDF.  Mirrors billing's
``InvoicePDFService``: WeasyPrint is CPU-bound, so rendering is
offloaded to a worker thread via ``asyncio.to_thread``.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from html import escape
from io import BytesIO
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

if TYPE_CHECKING:
    from app.core.auth.models import Clinic
    from app.modules.patients.models import Patient

    from .models import GeneratedDocument

_LABELS = {
    "es": {
        "patient": "Paciente",
        "dob": "Fecha de nacimiento",
        "doc": "Documento",
        "issued": "Fecha de emisión",
        "issued_by": "Emitido por",
        "diagnosis": "Diagnóstico",
        "description": "Descripción",
        "recommendations": "Recomendaciones",
        "medications": "Medicación",
        "medName": "Medicamento",
        "dose": "Dosis",
        "frequency": "Frecuencia",
        "duration": "Duración",
        "referred_to": "Derivado a",
        "specialty": "Especialidad",
        "reason": "Motivo de la derivación",
        "clinical_summary": "Resumen clínico",
        "exam_type": "Tipo de exploración",
        "region": "Región",
        "clinical_question": "Pregunta clínica",
        "notes": "Observaciones",
        "generated_by": "Generado con DentalPin",
        "registration_number": "Nº colegiado",
        "prescription": "Receta",
        "medical_certificate": "Certificado médico",
        "referral": "Carta de derivación",
        "radiology_request": "Solicitud de radiología",
    },
    "en": {
        "patient": "Patient",
        "dob": "Date of birth",
        "doc": "Document",
        "issued": "Issue date",
        "issued_by": "Issued by",
        "diagnosis": "Diagnosis",
        "description": "Description",
        "recommendations": "Recommendations",
        "medications": "Medication",
        "medName": "Medication",
        "dose": "Dose",
        "frequency": "Frequency",
        "duration": "Duration",
        "referred_to": "Referred to",
        "specialty": "Specialty",
        "reason": "Reason for referral",
        "clinical_summary": "Clinical summary",
        "exam_type": "Exam type",
        "region": "Region",
        "clinical_question": "Clinical question",
        "notes": "Notes",
        "generated_by": "Generated with DentalPin",
        "registration_number": "License number",
        "prescription": "Prescription",
        "medical_certificate": "Medical certificate",
        "referral": "Referral letter",
        "radiology_request": "Radiology request",
    },
}


class DocumentPDFService:
    """Service for generating branded PDFs of clinical documents."""

    @staticmethod
    def async_generate_pdf(
        document: GeneratedDocument,
        clinic: Clinic,
        patient: Patient,
        locale: str = "es",
        issued_by: str = "",
    ) -> asyncio.Future[bytes]:
        """Render the document to PDF bytes off the event loop."""
        return asyncio.to_thread(
            DocumentPDFService._generate_pdf,
            document,
            clinic,
            patient,
            locale,
            issued_by,
        )

    @classmethod
    async def generate_pdf(
        cls,
        document: GeneratedDocument,
        clinic: Clinic,
        patient: Patient,
        locale: str = "es",
        issued_by: str = "",
    ) -> bytes:
        """Return the rendered PDF for a document."""
        return await cls.async_generate_pdf(document, clinic, patient, locale, issued_by)

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    @staticmethod
    def _generate_pdf(
        document: GeneratedDocument,
        clinic: Clinic,
        patient: Patient,
        locale: str,
        issued_by: str,
    ) -> bytes:
        html = DocumentPDFService._generate_html(document, clinic, patient, locale, issued_by)
        return DocumentPDFService._html_to_pdf(html)

    @staticmethod
    def _format_address(address: dict | None) -> str:
        """Format a clinic address dict as a readable string."""
        if not address:
            return ""
        parts = []
        if address.get("street"):
            parts.append(address["street"])
        city_line = " ".join(filter(None, [address.get("postal_code"), address.get("city")]))
        if city_line:
            parts.append(city_line)
        if address.get("country"):
            parts.append(address["country"])
        return ", ".join(parts)

    @staticmethod
    def _letterhead(clinic: Clinic) -> dict:
        """Resolve letterhead settings for a clinic.

        Per-clinic overrides live under ``clinic.settings["documents"]["letterhead"]``;
        every key falls back to the clinic's native profile.
        """
        raw = {}
        if clinic is not None and isinstance(clinic.settings, dict):
            raw = clinic.settings.get("documents") or {}
            raw = raw.get("letterhead") or {}
        if not clinic:
            return {"name": "", "address": "", "phone": "", "email": "", "registration_number": ""}

        def pick(key: str, native: str) -> str:
            if raw.get(key):
                return str(raw[key])
            return native or ""

        address = ""
        if clinic.address:
            address = DocumentPDFService._format_address(clinic.address)
        return {
            "name": pick("name", clinic.name or "Dental Clinic"),
            "address": pick("address", address),
            "phone": pick("phone", clinic.phone or ""),
            "email": pick("email", clinic.email or ""),
            "registration_number": pick(
                "registration_number",
                clinic.tax_id or "",
            ),
            "logo": raw.get("logo") or "",
        }

    @staticmethod
    def _patient_birth(patient: Patient) -> str:
        return (
            patient.date_of_birth.strftime("%d/%m/%Y")
            if getattr(patient, "date_of_birth", None)
            else "-"
        )

    @staticmethod
    def _generate_html(
        document: GeneratedDocument,
        clinic: Clinic,
        patient: Patient,
        locale: str,
        issued_by: str,
    ) -> str:
        labels = _LABELS.get(locale, _LABELS["en"])
        header = DocumentPDFService._letterhead(clinic)

        doc_title = labels.get(document.document_type, document.document_type)
        try:
            clinic_tz = ZoneInfo(clinic.timezone or "UTC")
        except (KeyError, ValueError):
            clinic_tz = UTC
        issued_at = datetime.now(clinic_tz).strftime("%d/%m/%Y %H:%M")

        patient_name = ""
        patient_id = ""
        if patient is not None:
            patient_name = f"{patient.first_name} {patient.last_name}"
            patient_id = str(patient.id)

        content = document.content or {}
        logo_html = ""
        if header.get("logo"):
            logo_html = (
                '<div class="clinic-logo">'
                f'<img src="{escape(str(header["logo"]))}" alt="logo" />'
                "</div>"
            )

        clinic_lines = [
            escape(header["address"]),
            escape(header["phone"]) if header["phone"] else "",
            escape(header["email"]) if header["email"] else "",
        ]
        if header.get("registration_number"):
            clinic_lines.append(
                f"{labels['registration_number']}: {escape(header['registration_number'])}"
            )
        clinic_details_html = "<br>".join(line for line in clinic_lines if line)

        issued_by_html = ""
        if issued_by:
            issued_by_html = (
                f'<div class="info-group"><div class="info-label">{labels["issued_by"]}</div>'
                f'<div class="info-value">{escape(issued_by)}</div></div>'
            )

        body_html = DocumentPDFService._render_body(document.document_type, content, labels)

        return f"""<!DOCTYPE html>
        <html lang="{locale}">
        <head>
            <meta charset="UTF-8">
            <title>{escape(doc_title)} — {escape(patient_name)}</title>
            <style>
                * {{ margin: 0; padding: 0; box-sizing: border-box; }}
                body {{
                    font-family: 'Helvetica Neue', Arial, sans-serif;
                    font-size: 11pt; line-height: 1.4; color: #333;
                    padding: 20mm;
                }}
                .header {{
                    display: flex; justify-content: space-between;
                    align-items: flex-start;
                    margin-bottom: 30px; padding-bottom: 20px;
                    border-bottom: 2px solid #2563eb;
                }}
                .clinic-info {{ max-width: 60%; }}
                .clinic-logo {{ margin-bottom: 8px; }}
                .clinic-logo img {{ max-height: 24mm; max-width: 50mm; }}
                .clinic-name {{ font-size: 18pt; font-weight: bold; color: #1e40af; margin-bottom: 5px; }}
                .clinic-details {{ font-size: 9pt; color: #666; }}
                .doc-title {{ font-size: 16pt; font-weight: bold; color: #1e40af; text-align: right; }}
                .section {{ margin-bottom: 25px; }}
                .section-title {{
                    font-size: 11pt; font-weight: bold; color: #1e40af;
                    margin-bottom: 10px; padding-bottom: 5px;
                    border-bottom: 1px solid #e5e7eb;
                }}
                .meta {{ display: flex; gap: 40px; }}
                .info-group {{ min-width: 180px; }}
                .info-label {{ font-size: 9pt; color: #666; margin-bottom: 2px; }}
                .info-value {{ font-weight: 500; }}
                table {{ width: 100%; border-collapse: collapse; margin-bottom: 20px; }}
                th {{
                    background: #f3f4f6; padding: 8px; text-align: left;
                    font-size: 9pt; font-weight: 600; color: #374151;
                    border-bottom: 2px solid #e5e7eb;
                }}
                td {{ padding: 8px; border-bottom: 1px solid #e5e7eb; vertical-align: top; }}
                tr:last-child td {{ border-bottom: none; }}
                .notes-content {{ background: #f9fafb; padding: 12px; border-radius: 8px; font-size: 10pt; }}
                .footer {{
                    position: fixed; bottom: 15mm; left: 20mm; right: 20mm;
                    font-size: 8pt; color: #9ca3af; text-align: center;
                    border-top: 1px solid #e5e7eb; padding-top: 10px;
                }}
                @media print {{ body {{ padding: 0; }} .footer {{ position: fixed; }} }}
            </style>
        </head>
        <body>
            <div class="header">
                <div class="clinic-info">
                    {logo_html}
                    <div class="clinic-name">{escape(header["name"])}</div>
                    <div class="clinic-details">
                        {clinic_details_html}
                    </div>
                </div>
                <div>
                    <div class="doc-title">{escape(doc_title)}</div>
                </div>
            </div>

            <div class="section">
                <div class="section-title">{labels["patient"]}</div>
                <div class="meta">
                    <div class="info-group">
                        <div class="info-label">{labels["patient"]}</div>
                        <div class="info-value">{escape(patient_name)}</div>
                    </div>
                    <div class="info-group">
                        <div class="info-label">{labels["dob"]}</div>
                        <div class="info-value">{DocumentPDFService._patient_birth(patient)}</div>
                    </div>
                    <div class="info-group">
                        <div class="info-label">{labels["issued"]}</div>
                        <div class="info-value">{issued_at}</div>
                    </div>
                    {issued_by_html}
                    <div class="info-group">
                        <div class="info-label">ID</div>
                        <div class="info-value">{patient_id}</div>
                    </div>
                </div>
            </div>

            {body_html}

            <div class="footer">
                {escape(labels["generated_by"])} | {escape(header["name"])}
            </div>
        </body>
        </html>
        """

    @staticmethod
    def _render_body(document_type: str, content: dict, labels: dict) -> str:
        """Render the type-specific content block.

        Content is user-entered free text (plus structured medication
        rows), so every value is escaped before it reaches the template.
        """

        def esc(value: object) -> str:
            return escape("" if value is None else str(value))

        if document_type == "prescription":
            rows = ""
            for med in content.get("medications") or []:
                if not isinstance(med, dict):
                    continue
                rows += (
                    "<tr>"
                    f"<td>{esc(med.get('name'))}</td>"
                    f"<td>{esc(med.get('dose'))}</td>"
                    f"<td>{esc(med.get('frequency'))}</td>"
                    f"<td>{esc(med.get('duration'))}</td>"
                    "</tr>"
                )
            meds_html = (
                f"<table><thead><tr>"
                f"<th>{labels['medName']}</th><th>{labels['dose']}</th>"
                f"<th>{labels['frequency']}</th><th>{labels['duration']}</th>"
                f"</tr></thead><tbody>{rows}</tbody></table>"
                if rows
                else '<div class="notes-content">-</div>'
            )
            return (
                f'<div class="section"><div class="section-title">{labels["diagnosis"]}</div>'
                f'<div class="notes-content">{esc(content.get("diagnosis"))}</div></div>'
                f'<div class="section"><div class="section-title">{labels["medications"]}</div>'
                f"{meds_html}</div>"
                + (
                    f'<div class="section"><div class="section-title">{labels["notes"]}</div>'
                    f'<div class="notes-content">{esc(content.get("notes"))}</div></div>'
                    if content.get("notes")
                    else ""
                )
            )

        if document_type == "medical_certificate":
            return (
                _block(labels["diagnosis"], content.get("diagnosis"))
                + _block(labels["description"], content.get("description"))
                + _block(labels["recommendations"], content.get("recommendations"))
            )

        if document_type == "referral":
            return (
                _block(labels["referred_to"], content.get("referred_to"))
                + _block(labels["specialty"], content.get("specialty"))
                + _block(labels["reason"], content.get("reason"))
                + _block(labels["clinical_summary"], content.get("clinical_summary"))
                + _block(labels["notes"], content.get("notes"))
            )

        if document_type == "radiology_request":
            return (
                _block(labels["exam_type"], content.get("exam_type"))
                + _block(labels["region"], content.get("region"))
                + _block(labels["clinical_question"], content.get("clinical_question"))
                + _block(labels["notes"], content.get("notes"))
            )

        return ""

    @staticmethod
    def _html_to_pdf(html_content: str) -> bytes:
        """Convert HTML to PDF with WeasyPrint; raw HTML fallback."""
        try:
            from weasyprint import HTML

            pdf_buffer = BytesIO()
            HTML(string=html_content).write_pdf(pdf_buffer)
            return pdf_buffer.getvalue()
        except ImportError:
            return html_content.encode("utf-8")


def _block(title: str, value: object) -> str:
    """Render a titled content block with an escaped value."""
    text = "" if value is None else str(value)
    if not text.strip():
        return ""
    return (
        f'<div class="section"><div class="section-title">{escape(title)}</div>'
        f'<div class="notes-content">{escape(text)}</div></div>'
    )
