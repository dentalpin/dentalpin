"""A credit note carries no hard-coded Spanish public note (#1179).

Every credit note was created with ``public_notes="Rectificación de factura
{n}"``, and the PDF prints public notes, so an English or Hungarian clinic got
a Spanish sentence next to the localized "Corrects: {n}" reference line.
"""

from __future__ import annotations

from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic
from app.modules.billing.pdf import InvoicePDFService
from app.modules.billing.service import InvoiceService
from tests.modules.billing.test_credit_note_cap import _issued_invoice

B = "/api/v1/billing/invoices"


@pytest.mark.asyncio
async def test_credit_note_has_no_spanish_public_note(
    client: AsyncClient,
    db_session: AsyncSession,
    auth_headers: dict,
    budget_clinic_setup: dict,
) -> None:
    h = auth_headers
    inv = await _issued_invoice(client, h, budget_clinic_setup)
    r = await client.post(f"{B}/{inv['id']}/credit-note", json={"reason": "error"}, headers=h)
    assert r.status_code == 201, r.text
    note = r.json()["data"]
    assert not note["public_notes"]

    clinic_id = UUID(budget_clinic_setup["clinic_id"])
    credit_note = await InvoiceService.get_invoice(db_session, clinic_id, UUID(note["id"]))
    clinic = (await db_session.execute(select(Clinic).where(Clinic.id == clinic_id))).scalar_one()
    html = InvoicePDFService._generate_html(credit_note, clinic, is_preview=True, locale="en")

    assert "Rectificación" not in html
    # The localized reference line still names the corrected invoice.
    assert f"Corrects:</strong> {inv['invoice_number']}" in html
