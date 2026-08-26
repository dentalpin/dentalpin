"""Multi-tenant isolation: clinic A must never see clinic B's GST data.

These endpoints looked rows up by foreign id alone before the fix-up —
every test here fails against that code.
"""

from __future__ import annotations

from uuid import uuid4

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic
from app.modules.billing.models import Invoice, InvoiceItem
from app.modules.catalog.models import TreatmentCatalogItem, TreatmentCategory
from app.modules.india_gst.models import (
    IndiaGstCatalogItem,
    IndiaGstInvoiceItem,
    IndiaGstSettings,
)
from app.modules.patients.models import Patient

FOREIGN_GSTIN = "29ZZZZZ9999Z9ZW"


async def _foreign_clinic_with_gst_data(db: AsyncSession, user_id) -> Clinic:
    """A second clinic with settings, a SAC default and an issued GST invoice."""
    other = Clinic(id=uuid4(), name="Foreign Clinic", tax_id="B99999999", address={}, settings={})
    db.add(other)
    await db.flush()

    db.add(
        IndiaGstSettings(
            clinic_id=other.id,
            trade_name="Foreign Dental",
            gstin=FOREIGN_GSTIN,
            registration_type="regular",
            clinic_state="29",
        )
    )
    category = TreatmentCategory(clinic_id=other.id, key="foreign", names={"en": "Foreign"})
    db.add(category)
    await db.flush()
    catalog_item = TreatmentCatalogItem(
        id=uuid4(),
        clinic_id=other.id,
        category_id=category.id,
        internal_code="FOREIGN-1",
        names={"en": "Foreign treatment"},
    )
    db.add(catalog_item)
    await db.flush()
    db.add(
        IndiaGstCatalogItem(clinic_id=other.id, catalog_item_id=catalog_item.id, sac_code="999999")
    )

    patient = Patient(id=uuid4(), clinic_id=other.id, first_name="F", last_name="P")
    db.add(patient)
    await db.flush()
    invoice = Invoice(
        id=uuid4(),
        clinic_id=other.id,
        patient_id=patient.id,
        status="issued",
        billing_name="F P",
        created_by=user_id,
        compliance_data={"IN": {"gst_document_number": "GST/FY26-27/0042"}},
    )
    db.add(invoice)
    await db.flush()
    item = InvoiceItem(
        id=uuid4(),
        clinic_id=other.id,
        invoice_id=invoice.id,
        description="Foreign crown",
        unit_price="1000.00",
        quantity=1,
    )
    db.add(item)
    await db.flush()
    db.add(
        IndiaGstInvoiceItem(
            clinic_id=other.id,
            invoice_item_id=item.id,
            tax_type="intra",
            cgst_amount="90.00",
            sgst_amount="90.00",
        )
    )
    await db.commit()
    return other


async def _user_id(client: AsyncClient, auth_headers: dict) -> str:
    r = await client.get("/api/v1/auth/me", headers=auth_headers)
    return r.json()["data"]["user"]["id"]


async def test_settings_are_own_clinic_only(
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    india_gst_settings: IndiaGstSettings,
):
    await _foreign_clinic_with_gst_data(db_session, await _user_id(client, auth_headers))
    r = await client.get("/api/v1/india_gst/settings", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["data"]["gstin"] == india_gst_settings.gstin
    assert r.json()["data"]["gstin"] != FOREIGN_GSTIN


async def test_catalog_defaults_exclude_foreign_clinic(
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    india_gst_settings: IndiaGstSettings,
):
    await _foreign_clinic_with_gst_data(db_session, await _user_id(client, auth_headers))
    r = await client.get("/api/v1/india_gst/catalog-defaults", headers=auth_headers)
    assert r.status_code == 200
    data = r.json()["data"]
    assert all(c["sac_code"] != "999999" for c in data["configured"])
    assert all(m["internal_code"] != "FOREIGN-1" for m in data["missing"])


async def test_reports_and_export_exclude_foreign_clinic(
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    india_gst_settings: IndiaGstSettings,
):
    await _foreign_clinic_with_gst_data(db_session, await _user_id(client, auth_headers))
    r = await client.get("/api/v1/india_gst/reports/summary", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["data"]["invoice_count"] == 0

    r = await client.get("/api/v1/india_gst/reports/transactions", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["data"] == []

    r = await client.get("/api/v1/india_gst/reports/export", headers=auth_headers)
    assert r.status_code == 200
    assert b"GST/FY26-27/0042" not in r.content


async def test_draft_update_on_foreign_invoice_is_404(
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    india_gst_settings: IndiaGstSettings,
):
    other = await _foreign_clinic_with_gst_data(db_session, await _user_id(client, auth_headers))
    from sqlalchemy import select

    inv_q = await db_session.execute(select(Invoice.id).where(Invoice.clinic_id == other.id))
    foreign_invoice_id = inv_q.scalar_one()

    r = await client.put(
        f"/api/v1/india_gst/invoices/{foreign_invoice_id}",
        json={"place_of_supply": "33"},
        headers=auth_headers,
    )
    assert r.status_code == 404


async def test_autoconfigure_does_not_create_vat_type_in_foreign_clinic(
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    india_gst_settings: IndiaGstSettings,
):
    """Auto-configuring clinic A must not create a GST 18% VAT type in
    clinic B — the VAT type is tenant-scoped."""
    from sqlalchemy import func

    from app.modules.catalog.models import VatType

    other = await _foreign_clinic_with_gst_data(db_session, await _user_id(client, auth_headers))

    r = await client.post("/api/v1/india_gst/catalog-defaults/autoconfigure", headers=auth_headers)
    assert r.status_code == 200, r.text

    foreign_vat_q = await db_session.execute(
        select(func.count())
        .select_from(VatType)
        .where(VatType.clinic_id == other.id, VatType.names.op("->>")("en") == "GST 18%")
    )
    assert foreign_vat_q.scalar() == 0
