"""The invoice's patient brief carries the phone (#1160).

The Send dialog offers WhatsApp only when ``invoice.patient.phone`` is set;
the brief dropped it, so WhatsApp was always disabled as "no phone".
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic

from .test_issue_billing_snapshot import _draft, _patient


@pytest.mark.asyncio
async def test_invoice_detail_and_list_include_patient_phone(
    client: AsyncClient, auth_headers: dict, test_clinic: Clinic, db_session: AsyncSession
) -> None:
    patient = await _patient(db_session, test_clinic, phone="+34600111222")
    inv = await _draft(db_session, test_clinic, patient)

    detail = await client.get(f"/api/v1/billing/invoices/{inv.id}", headers=auth_headers)
    assert detail.status_code == 200, detail.text
    assert detail.json()["data"]["patient"]["phone"] == "+34600111222"

    listing = await client.get("/api/v1/billing/invoices", headers=auth_headers)
    assert listing.status_code == 200, listing.text
    row = next(r for r in listing.json()["data"] if r["id"] == str(inv.id))
    assert row["patient"]["phone"] == "+34600111222"
