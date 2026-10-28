"""PUT /india-gst/invoices/{id} — draft-only guard, SAC override audit note."""

from __future__ import annotations

from uuid import uuid4

from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.billing.models import Invoice
from app.modules.india_gst.models import IndiaGstInvoiceItem, IndiaGstSettings
from app.modules.patients.models import Patient


async def test_put_on_draft_merges_compliance_data(
    client: AsyncClient,
    auth_headers,
    db_session: AsyncSession,
    india_gst_settings: IndiaGstSettings,
    test_patient: Patient,
):
    r = await client.post(
        "/api/v1/billing/invoices", json={"patient_id": str(test_patient.id)}, headers=auth_headers
    )
    invoice_id = r.json()["data"]["id"]

    r = await client.put(
        f"/api/v1/india_gst/invoices/{invoice_id}",
        json={"place_of_supply": "27"},
        headers=auth_headers,
    )
    assert r.status_code == 200, r.text

    r = await client.get(f"/api/v1/billing/invoices/{invoice_id}", headers=auth_headers)
    assert r.json()["data"]["compliance_data"]["IN"]["place_of_supply"] == "27"


async def test_put_rejects_issued_invoice(
    client: AsyncClient,
    auth_headers,
    db_session: AsyncSession,
    india_gst_settings: IndiaGstSettings,
    test_patient: Patient,
):
    invoice = Invoice(
        id=uuid4(),
        clinic_id=india_gst_settings.clinic_id,
        patient_id=test_patient.id,
        status="issued",
        billing_name="Test Patient",
        created_by=(await client.get("/api/v1/auth/me", headers=auth_headers)).json()["data"][
            "user"
        ]["id"],
    )
    db_session.add(invoice)
    await db_session.commit()

    r = await client.put(
        f"/api/v1/india_gst/invoices/{invoice.id}",
        json={"place_of_supply": "27"},
        headers=auth_headers,
    )
    assert r.status_code == 409


async def test_delete_draft_line_with_sac_override(
    client: AsyncClient,
    auth_headers,
    db_session: AsyncSession,
    india_gst_settings: IndiaGstSettings,
    test_patient: Patient,
):
    """The override row references the line through a RESTRICT FK, so
    deleting the line used to answer 500 (#750)."""
    r = await client.post(
        "/api/v1/billing/invoices", json={"patient_id": str(test_patient.id)}, headers=auth_headers
    )
    invoice_id = r.json()["data"]["id"]
    r = await client.post(
        f"/api/v1/billing/invoices/{invoice_id}/items",
        json={"description": "Scaling", "unit_price": "1000"},
        headers=auth_headers,
    )
    assert r.status_code == 201, r.text
    item_id = r.json()["data"]["id"]
    r = await client.put(
        f"/api/v1/india_gst/invoices/{invoice_id}",
        json={"items": [{"invoice_item_id": item_id, "sac_code": "999311"}]},
        headers=auth_headers,
    )
    assert r.status_code == 200, r.text

    r = await client.delete(
        f"/api/v1/billing/invoices/{invoice_id}/items/{item_id}", headers=auth_headers
    )
    assert r.status_code == 204, r.text
    left = await db_session.scalar(
        select(func.count())
        .select_from(IndiaGstInvoiceItem)
        .where(IndiaGstInvoiceItem.invoice_item_id == item_id)
    )
    assert left == 0
