"""Budget PDF generation service."""

import asyncio
import hashlib
from datetime import date
from decimal import Decimal
from io import BytesIO
from typing import TYPE_CHECKING

from app.core.pdf_locales import LOCALE_BY_LANG as _LOCALE_BY_LANG
from app.core.utils.currency import format_currency as _fmt_currency

if TYPE_CHECKING:
    from app.core.auth.models import Clinic

from .models import Budget, BudgetSignature
from .pricing import allocate_global_discount, net_line_total

# Every UI locale renders (#441): labels are es/en with English as the
# fallback, but amounts and dates follow the viewer's own locale.


class BudgetPDFService:
    """Service for generating budget PDFs.

    MVP: Generates simple HTML-based PDF.
    Future: Integration with professional PDF templates.
    """

    @staticmethod
    def _format_address(address: dict | None) -> str:
        """Format address dict as a readable string."""
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
    async def generate_pdf(
        budget: Budget,
        clinic: "Clinic",
        is_preview: bool = False,
        locale: str = "es",
        signature: "BudgetSignature | None" = None,
    ) -> bytes:
        """Generate PDF for a budget.

        Args:
            budget: The budget to generate PDF for
            clinic: The clinic for branding
            is_preview: If True, adds DRAFT watermark
            locale: UI language; labels are es/en (English fallback)
            signature: Optional accepted signature. When set, the PDF
                replaces the empty patient signature line with the
                captured PNG (for ``signature_method='drawn'``) and
                appends an audit footer with signer name, date,
                channel and document hash. ``generate_pdf_hash`` should
                be called on the resulting bytes by the caller and
                persisted on ``BudgetSignature.document_hash`` for
                tamper detection.

        Returns:
            PDF content as bytes
        """
        # Generate HTML content
        html_content = BudgetPDFService._generate_html(
            budget, clinic, is_preview, locale, signature
        )

        # WeasyPrint is CPU-bound; offload to a thread so the event
        # loop keeps serving other requests while it renders.
        return await asyncio.to_thread(BudgetPDFService._html_to_pdf, html_content)

    @staticmethod
    def generate_pdf_hash(pdf_bytes: bytes) -> str:
        """Generate SHA-256 hash of PDF content for signature verification."""
        return hashlib.sha256(pdf_bytes).hexdigest()

    @staticmethod
    def _render_signature_section(
        signature: "BudgetSignature | None",
        labels: dict,
        locale: str,
    ) -> str:
        """Render the signature block — empty when no signature, with
        the captured PNG + audit footer otherwise."""
        if signature is None:
            return f"""
            <div class="signature-section">
                <div class="signature-box">
                    <div class="signature-line"></div>
                    <div class="signature-label">{labels["patient_signature"]}</div>
                </div>
                <div class="signature-box">
                    <div class="signature-line"></div>
                    <div class="signature-label">{labels["clinic_signature"]}</div>
                </div>
            </div>
            """

        # Resolve signature image. ``signature_method='drawn'`` carries
        # the PNG as a data URI under ``signature_data.png``. Other
        # methods (click_accept, external) just render the typed name
        # under the line.
        png_data = None
        if isinstance(signature.signature_data, dict):
            raw_png = signature.signature_data.get("png")
            if isinstance(raw_png, str) and raw_png.startswith("data:image"):
                png_data = raw_png

        signed_at_str = (
            signature.signed_at.strftime("%d/%m/%Y %H:%M") if signature.signed_at else "—"
        )
        method_key = signature.signature_method or "click_accept"
        method_label = labels.get(
            f"signature_method_{method_key}",
            labels.get("signature_method_click_accept", method_key),
        )
        signature_visual = (
            f'<img src="{png_data}" alt="" style="max-width: 100%; max-height: 80px;" />'
            if png_data
            else f'<div style="font-family: cursive; font-size: 14pt; '
            f'padding: 18px 0 4px; border-bottom: 1px solid #333;">'
            f"{signature.signed_by_name}</div>"
        )
        # Document hash is set by accept_budget after rendering once.
        # Render placeholder when missing (first-pass render).
        doc_hash_short = (signature.document_hash[:16] + "…") if signature.document_hash else "—"

        return f"""
        <div class="signature-section">
            <div class="signature-box signature-box-signed">
                <div class="signature-line">{signature_visual}</div>
                <div class="signature-label">{labels["patient_signature"]}</div>
                <div class="signature-meta">
                    <div><strong>{labels["signed_by"]}:</strong> {signature.signed_by_name}</div>
                    <div><strong>{labels["signed_at"]}:</strong> {signed_at_str}</div>
                    <div><strong>{labels["signature_method"]}:</strong> {method_label}</div>
                    <div class="signature-hash">
                        <strong>{labels["document_hash"]}:</strong> <code>{doc_hash_short}</code>
                    </div>
                </div>
            </div>
            <div class="signature-box">
                <div class="signature-line"></div>
                <div class="signature-label">{labels["clinic_signature"]}</div>
            </div>
        </div>
        """

    @staticmethod
    def _generate_html(
        budget: Budget,
        clinic: "Clinic",
        is_preview: bool,
        locale: str,
        signature: "BudgetSignature | None" = None,
    ) -> str:
        """Generate HTML content for the budget."""
        # Localized labels
        labels = BudgetPDFService._get_labels(locale)

        # Format currency from clinic.currency, locale derived from language.
        money_locale = _LOCALE_BY_LANG.get(locale, "es_ES")

        def format_currency(amount: Decimal) -> str:
            return _fmt_currency(amount, clinic.currency, locale=money_locale)

        # Build items table rows. Discount column = line + prorated global
        # share; total column = what the patient pays (issue #181).
        shares = allocate_global_discount(
            budget.global_discount_type, budget.global_discount_value, budget.items
        )
        items_html = ""
        for i, (item, share) in enumerate(zip(budget.items, shares, strict=True), 1):
            line_discount = (Decimal(str(item.line_discount)) + share).quantize(Decimal("0.01"))
            net_total = net_line_total(item, share)
            # Get item name from catalog
            item_name = ""
            if item.catalog_item:
                item_name = item.catalog_item.names.get(locale, "")
                if not item_name:
                    # Fallback to first available name
                    item_name = next(iter(item.catalog_item.names.values()), "")

            tooth_info = ""
            if item.tooth_number:
                tooth_info = f"#{item.tooth_number}"
                if item.surfaces:
                    tooth_info += f" ({', '.join(item.surfaces)})"

            items_html += f"""
            <tr>
                <td class="number">{i}</td>
                <td class="description">
                    {item_name}
                    {f'<br><small class="tooth">{tooth_info}</small>' if tooth_info else ""}
                    {f'<br><small class="notes">{item.notes}</small>' if item.notes else ""}
                </td>
                <td class="quantity">{item.quantity}</td>
                <td class="price">{format_currency(item.unit_price)}</td>
                {f'<td class="discount">{format_currency(line_discount)}</td>' if line_discount else '<td class="discount">-</td>'}
                <td class="total">{f"<small><s>{format_currency(item.line_total)}</s></small> " if line_discount else ""}{format_currency(net_total)}</td>
            </tr>
            """

        # Status badge
        status_label = labels["status"].get(budget.status, budget.status)

        # Watermark for preview
        watermark_style = ""
        watermark_html = ""
        if is_preview or budget.status == "draft":
            watermark_style = """
            .watermark {
                position: fixed;
                top: 50%;
                left: 50%;
                transform: translate(-50%, -50%) rotate(-45deg);
                font-size: 120px;
                color: rgba(200, 200, 200, 0.3);
                z-index: 1000;
                pointer-events: none;
            }
            """
            watermark_html = f'<div class="watermark">{labels["draft"]}</div>'

        # Patient info
        patient_name = ""
        if budget.patient:
            patient_name = f"{budget.patient.first_name} {budget.patient.last_name}"

        # Professional info
        professional_name = ""
        if budget.assigned_professional:
            professional_name = f"{budget.assigned_professional.first_name} {budget.assigned_professional.last_name}"

        # Validity period
        valid_from = budget.valid_from.strftime("%d/%m/%Y") if budget.valid_from else "-"
        valid_until = (
            budget.valid_until.strftime("%d/%m/%Y") if budget.valid_until else labels["no_expiry"]
        )

        # Build HTML
        rtl_attr = ' dir="rtl"' if locale == "ar" else ""
        html = f"""
        <!DOCTYPE html>
        <html lang="{locale}"{rtl_attr}>
        <head>
            <meta charset="UTF-8">
            <title>{labels["budget"]} {budget.budget_number}</title>
            <style>
                * {{
                    margin: 0;
                    padding: 0;
                    box-sizing: border-box;
                }}
                body {{
                    font-family: 'Helvetica Neue', Arial, sans-serif;
                    font-size: 11pt;
                    line-height: 1.4;
                    color: #333;
                    padding: 20mm;
                }}
                {watermark_style}
                .header {{
                    display: flex;
                    justify-content: space-between;
                    margin-bottom: 30px;
                    padding-bottom: 20px;
                    border-bottom: 2px solid #2563eb;
                }}
                .clinic-info {{
                    max-width: 60%;
                }}
                .clinic-name {{
                    font-size: 18pt;
                    font-weight: bold;
                    color: #1e40af;
                    margin-bottom: 5px;
                }}
                .clinic-details {{
                    font-size: 9pt;
                    color: #666;
                }}
                .budget-info {{
                    text-align: right;
                }}
                .budget-number {{
                    font-size: 14pt;
                    font-weight: bold;
                    color: #1e40af;
                }}
                .budget-meta {{
                    font-size: 9pt;
                    color: #666;
                    margin-top: 5px;
                }}
                .status-badge {{
                    display: inline-block;
                    padding: 3px 10px;
                    border-radius: 12px;
                    font-size: 9pt;
                    font-weight: bold;
                    text-transform: uppercase;
                    margin-top: 8px;
                }}
                .status-draft {{ background: #e5e7eb; color: #374151; }}
                .status-sent {{ background: #dbeafe; color: #1e40af; }}
                .status-accepted {{ background: #d1fae5; color: #065f46; }}
                .status-rejected {{ background: #fee2e2; color: #991b1b; }}
                .status-expired {{ background: #fef3c7; color: #92400e; }}

                .section {{
                    margin-bottom: 25px;
                }}
                .section-title {{
                    font-size: 11pt;
                    font-weight: bold;
                    color: #1e40af;
                    margin-bottom: 10px;
                    padding-bottom: 5px;
                    border-bottom: 1px solid #e5e7eb;
                }}
                .patient-info {{
                    display: flex;
                    gap: 40px;
                }}
                .info-group {{
                    min-width: 200px;
                }}
                .info-label {{
                    font-size: 9pt;
                    color: #666;
                    margin-bottom: 2px;
                }}
                .info-value {{
                    font-weight: 500;
                }}

                table {{
                    width: 100%;
                    border-collapse: collapse;
                    margin-bottom: 20px;
                }}
                th {{
                    background: #f3f4f6;
                    padding: 10px 8px;
                    text-align: start;
                    font-size: 9pt;
                    font-weight: 600;
                    color: #374151;
                    border-bottom: 2px solid #e5e7eb;
                }}
                td {{
                    padding: 10px 8px;
                    border-bottom: 1px solid #e5e7eb;
                    vertical-align: top;
                }}
                tr:last-child td {{
                    border-bottom: none;
                }}
                .number {{ width: 30px; text-align: center; }}
                .description {{ width: auto; }}
                .quantity {{ width: 60px; text-align: center; }}
                .price {{ width: 100px; text-align: end; }}
                .discount {{ width: 100px; text-align: end; color: #059669; }}
                .vat {{ width: 50px; text-align: center; }}
                .total {{ width: 100px; text-align: end; font-weight: 500; }}
                .tooth {{ color: #6b7280; }}
                .notes {{ color: #9ca3af; font-style: italic; }}

                .totals {{
                    float: right;
                    width: 300px;
                    margin-top: 20px;
                }}
                .totals table {{
                    margin-bottom: 0;
                }}
                .totals td {{
                    padding: 6px 8px;
                    border-bottom: none;
                }}
                .totals .label {{
                    text-align: start;
                    color: #666;
                }}
                .totals .value {{
                    text-align: end;
                    font-weight: 500;
                }}
                .totals .grand-total {{
                    font-size: 14pt;
                    font-weight: bold;
                    color: #1e40af;
                    border-top: 2px solid #1e40af;
                    padding-top: 10px;
                }}

                .notes-section {{
                    clear: both;
                    padding-top: 30px;
                    margin-top: 30px;
                    border-top: 1px solid #e5e7eb;
                }}
                .notes-content {{
                    background: #f9fafb;
                    padding: 15px;
                    border-radius: 8px;
                    font-size: 10pt;
                    color: #4b5563;
                }}

                .validity {{
                    margin-top: 20px;
                    padding: 15px;
                    background: #eff6ff;
                    border-radius: 8px;
                    font-size: 10pt;
                }}
                .validity strong {{
                    color: #1e40af;
                }}

                .signature-section {{
                    margin-top: 40px;
                    padding-top: 20px;
                }}
                .signature-box {{
                    display: inline-block;
                    width: 45%;
                    margin-right: 5%;
                    vertical-align: top;
                }}
                .signature-line {{
                    border-bottom: 1px solid #333;
                    height: 80px;
                    margin-bottom: 5px;
                    display: flex;
                    align-items: flex-end;
                    justify-content: center;
                }}
                .signature-label {{
                    font-size: 9pt;
                    color: #666;
                }}
                .signature-meta {{
                    margin-top: 10px;
                    font-size: 8pt;
                    color: #475569;
                    line-height: 1.5;
                }}
                .signature-meta strong {{
                    color: #0f172a;
                }}
                .signature-hash code {{
                    font-family: ui-monospace, Menlo, Consolas, monospace;
                    font-size: 7pt;
                    color: #64748b;
                }}

                .footer {{
                    position: fixed;
                    bottom: 15mm;
                    left: 20mm;
                    right: 20mm;
                    font-size: 8pt;
                    color: #9ca3af;
                    text-align: center;
                    border-top: 1px solid #e5e7eb;
                    padding-top: 10px;
                }}

                @media print {{
                    body {{ padding: 0; }}
                    .footer {{ position: fixed; }}
                }}
            </style>
        </head>
        <body>
            {watermark_html}

            <div class="header">
                <div class="clinic-info">
                    <div class="clinic-name">{clinic.name if clinic else "Dental Clinic"}</div>
                    <div class="clinic-details">
                        {
            BudgetPDFService._format_address(clinic.address)
            if hasattr(clinic, "address") and clinic.address
            else ""
        }<br>
                        {clinic.phone if hasattr(clinic, "phone") and clinic.phone else ""}
                        {f" | {clinic.email}" if hasattr(clinic, "email") and clinic.email else ""}
                    </div>
                </div>
                <div class="budget-info">
                    <div class="budget-number">{labels["budget"]} {budget.budget_number}</div>
                    <div class="budget-meta">
                        {labels["version"]}: {budget.version}<br>
                        {labels["date"]}: {budget.created_at.strftime("%d/%m/%Y")}
                    </div>
                    <span class="status-badge status-{budget.status}">{status_label}</span>
                </div>
            </div>

            <div class="section">
                <div class="section-title">{labels["patient_info"]}</div>
                <div class="patient-info">
                    <div class="info-group">
                        <div class="info-label">{labels["patient"]}</div>
                        <div class="info-value">{patient_name}</div>
                    </div>
                    {
            f'''
                    <div class="info-group">
                        <div class="info-label">{labels["professional"]}</div>
                        <div class="info-value">{professional_name}</div>
                    </div>
                    '''
            if professional_name
            else ""
        }
                </div>
            </div>

            <div class="section">
                <div class="section-title">{labels["treatments"]}</div>
                <table>
                    <thead>
                        <tr>
                            <th class="number">#</th>
                            <th class="description">{labels["description"]}</th>
                            <th class="quantity">{labels["qty"]}</th>
                            <th class="price">{labels["unit_price"]}</th>
                            <th class="discount">{labels["discount"]}</th>
                            <th class="total">{labels["total"]}</th>
                        </tr>
                    </thead>
                    <tbody>
                        {items_html}
                    </tbody>
                </table>

                <div class="totals">
                    <table>
                        <tr>
                            <td class="label">{labels["subtotal"]}:</td>
                            <td class="value">{format_currency(budget.subtotal)}</td>
                        </tr>
                        {
            f'''
                        <tr>
                            <td class="label">{labels["total_discount"]}:</td>
                            <td class="value discount">-{format_currency(budget.total_discount)}</td>
                        </tr>
                        '''
            if budget.total_discount
            else ""
        }
                        {
            f'''
                        <tr>
                            <td class="label">{labels["tax"]}:</td>
                            <td class="value">{format_currency(budget.total_tax)}</td>
                        </tr>
                        '''
            if budget.total_tax
            else ""
        }
                        <tr>
                            <td class="label grand-total">{labels["grand_total"]}:</td>
                            <td class="value grand-total">{format_currency(budget.total)}</td>
                        </tr>
                    </table>
                </div>
            </div>

            <div class="validity">
                <strong>{labels["validity"]}:</strong>
                {labels["from"]} {valid_from} {labels["until"]} {valid_until}
            </div>

            {
            f'''
            <div class="notes-section">
                <div class="section-title">{labels["notes"]}</div>
                <div class="notes-content">{budget.patient_notes}</div>
            </div>
            '''
            if budget.patient_notes
            else ""
        }

            {BudgetPDFService._render_signature_section(signature, labels, locale)}

            <div class="footer">
                {labels["generated_by"]} DentalPin | {date.today().strftime("%d/%m/%Y %H:%M")}
            </div>
        </body>
        </html>
        """

        return html

    @staticmethod
    def _html_to_pdf(html_content: str) -> bytes:
        """Convert HTML to PDF.

        Uses WeasyPrint if available, otherwise returns HTML as fallback.
        """
        try:
            from weasyprint import HTML

            pdf_buffer = BytesIO()
            HTML(string=html_content).write_pdf(pdf_buffer)
            return pdf_buffer.getvalue()
        except ImportError:
            # WeasyPrint not installed, return HTML content
            # In production, WeasyPrint should be installed
            return html_content.encode("utf-8")

    @staticmethod
    def _get_labels(locale: str) -> dict:
        """Get localized labels for PDF."""
        labels_es = {
            "budget": "Presupuesto",
            "version": "Versión",
            "date": "Fecha",
            "draft": "BORRADOR",
            "patient_info": "Información del Paciente",
            "patient": "Paciente",
            "professional": "Profesional",
            "treatments": "Tratamientos",
            "description": "Descripción",
            "qty": "Cant.",
            "unit_price": "Precio Unit.",
            "discount": "Descuento",
            "total": "Total",
            "subtotal": "Subtotal",
            "total_discount": "Descuento total",
            "tax": "IVA",
            "grand_total": "TOTAL",
            "validity": "Validez",
            "from": "desde",
            "until": "hasta",
            "no_expiry": "sin fecha de caducidad",
            "notes": "Observaciones",
            "patient_signature": "Firma del Paciente",
            "clinic_signature": "Firma de la Clínica",
            "signed_by": "Firmado por",
            "signed_at": "Fecha de firma",
            "signature_method": "Canal",
            "signature_method_drawn": "Firma manuscrita",
            "signature_method_click_accept": "Aceptación digital",
            "signature_method_external": "Firma externa",
            "document_hash": "Hash del documento",
            "generated_by": "Generado por",
            "status": {
                "draft": "Borrador",
                "sent": "Enviado",
                "accepted": "Aceptado",
                "in_progress": "En Progreso",
                "completed": "Completado",
                "invoiced": "Facturado",
                "rejected": "Rechazado",
                "expired": "Caducado",
                "cancelled": "Cancelado",
            },
        }

        labels_en = {
            "budget": "Quote",
            "version": "Version",
            "date": "Date",
            "draft": "DRAFT",
            "patient_info": "Patient Information",
            "patient": "Patient",
            "professional": "Professional",
            "treatments": "Treatments",
            "description": "Description",
            "qty": "Qty",
            "unit_price": "Unit Price",
            "discount": "Discount",
            "total": "Total",
            "subtotal": "Subtotal",
            "total_discount": "Total discount",
            "tax": "VAT",
            "grand_total": "TOTAL",
            "validity": "Validity",
            "from": "from",
            "until": "until",
            "no_expiry": "no expiry date",
            "notes": "Notes",
            "patient_signature": "Patient Signature",
            "clinic_signature": "Clinic Signature",
            "signed_by": "Signed by",
            "signed_at": "Signed on",
            "signature_method": "Channel",
            "signature_method_drawn": "Handwritten signature",
            "signature_method_click_accept": "Digital acceptance",
            "signature_method_external": "External signature",
            "document_hash": "Document hash",
            "generated_by": "Generated by",
            "status": {
                "draft": "Draft",
                "sent": "Sent",
                "accepted": "Accepted",
                "in_progress": "In Progress",
                "completed": "Completed",
                "invoiced": "Invoiced",
                "rejected": "Rejected",
                "expired": "Expired",
                "cancelled": "Cancelled",
            },
        }

        labels_fr = {
            "budget": "Devis",
            "version": "Version",
            "date": "Date",
            "draft": "Brouillon",
            "patient_info": "Informations du patient",
            "patient": "Patient",
            "professional": "Professionnel",
            "treatments": "Traitements",
            "description": "Description",
            "qty": "Quantité",
            "unit_price": "Prix unitaire",
            "discount": "Remise",
            "total": "Total",
            "subtotal": "Sous-total",
            "total_discount": "Remise totale",
            "tax": "TVA",
            "grand_total": "TOTAL",
            "validity": "Validité",
            "from": "Du",
            "until": "Au",
            "no_expiry": "Aucune date d'expiration",
            "notes": "Notes",
            "patient_signature": "Signature du patient",
            "clinic_signature": "Signature de la clinique",
            "signed_by": "Signé par",
            "signed_at": "Signé le",
            "signature_method": "Méthode",
            "signature_method_drawn": "Signature manuscrite",
            "signature_method_click_accept": "Clic pour accepter",
            "signature_method_external": "Fournisseur externe",
            "document_hash": "Hash du document (SHA-256)",
            "generated_by": "Créé par",
            "status": {
                "draft": "Brouillon",
                "sent": "Envoyé",
                "accepted": "Accepté",
                "in_progress": "En cours",
                "completed": "Terminé",
                "invoiced": "Facturé",
                "rejected": "Refusé",
                "expired": "Expiré",
                "cancelled": "Annulé",
            },
        }

        labels_pt = {
            "budget": "Orçamento",
            "version": "Versão",
            "date": "Data",
            "draft": "Rascunho",
            "patient_info": "Informações do paciente",
            "patient": "Paciente",
            "professional": "Profissional",
            "treatments": "Tratamentos",
            "description": "Descrição",
            "qty": "Quantidade",
            "unit_price": "Preço unitário",
            "discount": "Desconto",
            "total": "Total",
            "subtotal": "Subtotal",
            "total_discount": "Desconto total",
            "tax": "IVA",
            "grand_total": "TOTAL",
            "validity": "Validade",
            "from": "De",
            "until": "Até",
            "no_expiry": "Sem data de validade",
            "notes": "Notas",
            "patient_signature": "Assinatura do paciente",
            "clinic_signature": "Assinatura da clínica",
            "signed_by": "Assinado por",
            "signed_at": "Assinado a",
            "signature_method": "Método",
            "signature_method_drawn": "Assinatura manuscrita",
            "signature_method_click_accept": "Aceitação por clique",
            "signature_method_external": "Fornecedor externo",
            "document_hash": "Hash do documento (SHA-256)",
            "generated_by": "Criada por",
            "status": {
                "draft": "Rascunho",
                "sent": "Enviado",
                "accepted": "Aceite",
                "in_progress": "Em curso",
                "completed": "Concluído",
                "invoiced": "Faturado",
                "rejected": "Recusado",
                "expired": "Expirado",
                "cancelled": "Anulado",
            },
        }

        labels_de = {
            "budget": "Kostenvoranschlag",
            "version": "Version",
            "date": "Datum",
            "draft": "Entwurf",
            "patient_info": "Patienteninformationen",
            "patient": "Patient",
            "professional": "Behandler",
            "treatments": "Behandlungen",
            "description": "Beschreibung",
            "qty": "Menge",
            "unit_price": "Einzelpreis",
            "discount": "Rabatt",
            "total": "Gesamt",
            "subtotal": "Zwischensumme",
            "total_discount": "Gesamtrabatt",
            "tax": "MwSt.",
            "grand_total": "GESAMTBETRAG",
            "validity": "Gültigkeit",
            "from": "Von",
            "until": "Bis",
            "no_expiry": "Kein Ablaufdatum",
            "notes": "Notizen",
            "patient_signature": "Patientenunterschrift",
            "clinic_signature": "Klinikunterschrift",
            "signed_by": "Unterschrieben von",
            "signed_at": "Unterschrieben am",
            "signature_method": "Methode",
            "signature_method_drawn": "Handschriftliche Unterschrift",
            "signature_method_click_accept": "Annahme per Klick",
            "signature_method_external": "Externer Anbieter",
            "document_hash": "Dokument-Hash (SHA-256)",
            "generated_by": "Erstellt von",
            "status": {
                "draft": "Entwurf",
                "sent": "Gesendet",
                "accepted": "Angenommen",
                "in_progress": "In Behandlung",
                "completed": "Abgeschlossen",
                "invoiced": "In Rechnung gestellt",
                "rejected": "Abgelehnt",
                "expired": "Abgelaufen",
                "cancelled": "Storniert",
            },
        }

        labels_hu = {
            "budget": "Árajánlat",
            "version": "Verzió",
            "date": "Dátum",
            "draft": "Piszkozat",
            "patient_info": "Páciens adatok",
            "patient": "Páciens",
            "professional": "Kezelőorvos",
            "treatments": "Kezelések",
            "description": "Leírás",
            "qty": "Mennyiség",
            "unit_price": "Egységár",
            "discount": "Kedvezmény",
            "total": "Összesen",
            "subtotal": "Részösszeg",
            "total_discount": "Összes kedvezmény",
            "tax": "Áfa",
            "grand_total": "VÉGÖSSZEG",
            "validity": "Érvényesség",
            "from": "Ettől",
            "until": "Eddig",
            "no_expiry": "Nincs lejárati dátum",
            "notes": "Megjegyzések",
            "patient_signature": "Páciens aláírása",
            "clinic_signature": "Klinika aláírása",
            "signed_by": "Aláírta",
            "signed_at": "Aláírás dátuma",
            "signature_method": "Mód",
            "signature_method_drawn": "Kézzel rajzolt aláírás",
            "signature_method_click_accept": "Elfogadás kattintással",
            "signature_method_external": "Külső szolgáltató",
            "document_hash": "Dokumentum-hash (SHA-256)",
            "generated_by": "Létrehozta",
            "status": {
                "draft": "Piszkozat",
                "sent": "Elküldve",
                "accepted": "Elfogadva",
                "in_progress": "Folyamatban",
                "completed": "Befejezve",
                "invoiced": "Számlázva",
                "rejected": "Elutasítva",
                "expired": "Lejárt",
                "cancelled": "Törölve",
            },
        }

        labels_pl = {
            "budget": "Kosztorys",
            "version": "Wersja",
            "date": "Data",
            "draft": "Wersja robocza",
            "patient_info": "Dane pacjenta",
            "patient": "Pacjent",
            "professional": "Lekarz",
            "treatments": "Zabiegi",
            "description": "Opis",
            "qty": "Ilość",
            "unit_price": "Cena jednostkowa",
            "discount": "Rabat",
            "total": "Razem",
            "subtotal": "Suma częściowa",
            "total_discount": "Suma rabatów",
            "tax": "VAT",
            "grand_total": "RAZEM DO ZAPŁATY",
            "validity": "Ważność",
            "from": "Od",
            "until": "Do",
            "no_expiry": "Bez terminu ważności",
            "notes": "Notatki",
            "patient_signature": "Podpis pacjenta",
            "clinic_signature": "Podpis kliniki",
            "signed_by": "Podpisano przez",
            "signed_at": "Data podpisu",
            "signature_method": "Metoda",
            "signature_method_drawn": "Podpis odręczny",
            "signature_method_click_accept": "Akceptacja kliknięciem",
            "signature_method_external": "Dostawca zewnętrzny",
            "document_hash": "Skrót dokumentu (SHA-256)",
            "generated_by": "Utworzone przez",
            "status": {
                "draft": "Wersja robocza",
                "sent": "Wysłany",
                "accepted": "Zaakceptowany",
                "in_progress": "W trakcie",
                "completed": "Ukończony",
                "invoiced": "Zafakturowany",
                "rejected": "Odrzucony",
                "expired": "Wygasły",
                "cancelled": "Anulowany",
            },
        }

        labels_it = {
            "budget": "Preventivo",
            "version": "Versione",
            "date": "Data",
            "draft": "Bozza",
            "patient_info": "Informazioni sul paziente",
            "patient": "Paziente",
            "professional": "Professionista",
            "treatments": "Trattamenti",
            "description": "Descrizione",
            "qty": "Quantità",
            "unit_price": "Prezzo unitario",
            "discount": "Sconto",
            "total": "Totale",
            "subtotal": "Subtotale",
            "total_discount": "Sconto totale",
            "tax": "IVA",
            "grand_total": "TOTALE",
            "validity": "Validità",
            "from": "Dal",
            "until": "Al",
            "no_expiry": "Senza scadenza",
            "notes": "Note",
            "patient_signature": "Firma del paziente",
            "clinic_signature": "Firma della clinica",
            "signed_by": "Firmato da",
            "signed_at": "Firmato il",
            "signature_method": "Metodo",
            "signature_method_drawn": "Firma autografa",
            "signature_method_click_accept": "Accettazione con clic",
            "signature_method_external": "Fornitore esterno",
            "document_hash": "Hash del documento (SHA-256)",
            "generated_by": "Creata da",
            "status": {
                "draft": "Bozza",
                "sent": "Inviato",
                "accepted": "Accettato",
                "in_progress": "In corso",
                "completed": "Completato",
                "invoiced": "Fatturato",
                "rejected": "Rifiutato",
                "expired": "Scaduto",
                "cancelled": "Annullato",
            },
        }

        labels_ar = {
            "budget": "عرض السعر",
            "version": "النسخة",
            "date": "التاريخ",
            "draft": "مسودة",
            "patient_info": "معلومات المريض",
            "patient": "المريض",
            "professional": "الطبيب",
            "treatments": "العلاجات",
            "description": "الوصف",
            "qty": "الكمية",
            "unit_price": "سعر الوحدة",
            "discount": "الخصم",
            "total": "الإجمالي",
            "subtotal": "المجموع الفرعي",
            "total_discount": "إجمالي الخصم",
            "tax": "ضريبة القيمة المضافة",
            "grand_total": "المجموع الإجمالي",
            "validity": "الصلاحية",
            "from": "من",
            "until": "إلى",
            "no_expiry": "بدون تاريخ انتهاء",
            "notes": "ملاحظات",
            "patient_signature": "توقيع المريض",
            "clinic_signature": "توقيع العيادة",
            "signed_by": "وقّع",
            "signed_at": "بتاريخ",
            "signature_method": "الطريقة",
            "signature_method_drawn": "توقيع يدوي",
            "signature_method_click_accept": "قبول بالنقر",
            "signature_method_external": "مزود خارجي",
            "document_hash": "بصمة المستند (SHA-256)",
            "generated_by": "أنشأها",
            "status": {
                "draft": "مسودة",
                "sent": "مُرسل",
                "accepted": "مقبول",
                "in_progress": "جارٍ التنفيذ",
                "completed": "منجز",
                "invoiced": "مفوتر",
                "rejected": "مرفوض",
                "expired": "منتهي الصلاحية",
                "cancelled": "ملغى",
            },
        }

        labels_ta = {
            "budget": "மதிப்பீடு",
            "version": "பதிப்பு",
            "date": "தேதி",
            "draft": "வரைவு",
            "patient_info": "நோயாளி தகவல்",
            "patient": "நோயாளி",
            "professional": "நிபுணர்",
            "treatments": "சிகிச்சைகள்",
            "description": "விளக்கம்",
            "qty": "அளவு",
            "unit_price": "அலகு விலை",
            "discount": "தள்ளுபடி",
            "total": "மொத்தம்",
            "subtotal": "துணைத்தொகை",
            "total_discount": "மொத்த தள்ளுபடி",
            "tax": "வரி",
            "grand_total": "மொத்தம்",
            "validity": "செல்லுபடியாகும் தன்மை",
            "from": "இதிலிருந்து",
            "until": "இதுவரை",
            "no_expiry": "காலாவதி தேதி இல்லை",
            "notes": "குறிப்புகள்",
            "patient_signature": "நோயாளி கையொப்பம்",
            "clinic_signature": "கிளினிக் கையொப்பம்",
            "signed_by": "கையொப்பமிட்டவர்",
            "signed_at": "கையொப்பமிட்ட தேதி",
            "signature_method": "முறை",
            "signature_method_drawn": "கையால் வரையப்பட்ட கையொப்பம்",
            "signature_method_click_accept": "கிளிக் செய்து ஏற்கவும்",
            "signature_method_external": "வெளிப்புற வழங்குநர்",
            "document_hash": "ஆவண ஹாஷ் (SHA-256)",
            "generated_by": "உருவாக்கியது",
            "status": {
                "draft": "வரைவு",
                "sent": "அனுப்பப்பட்டது",
                "accepted": "ஏற்கப்பட்டது",
                "in_progress": "செயலில் உள்ளது",
                "completed": "நிறைவடைந்தது",
                "invoiced": "விலைப்பட்டியல் செய்யப்பட்டது",
                "rejected": "நிராகரிக்கப்பட்டது",
                "expired": "காலாவதியானது",
                "cancelled": "ரத்து செய்யப்பட்டது",
            },
        }

        if locale == "es":
            return labels_es
        if locale == "fr":
            return labels_fr
        if locale == "pt":
            return labels_pt
        if locale == "de":
            return labels_de
        if locale == "hu":
            return labels_hu
        if locale == "pl":
            return labels_pl
        if locale == "it":
            return labels_it
        if locale == "ar":
            return labels_ar
        if locale == "ta":
            return labels_ta
        return labels_en
