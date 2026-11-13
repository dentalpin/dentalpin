"""An invoice only references this clinic's series, VAT types and catalog items.

All three are plain FKs. An unknown id was a 500 (ForeignKeyViolation).
Another clinic's id was stored: its VAT type gave the line a silent 0 % rate,
and its series left a draft that failed at issue ("Series not found").
"""

from __future__ import annotations

from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic
from app.modules.billing.models import InvoiceSeries
from app.modules.catalog.models import TreatmentCatalogItem, TreatmentCategory, VatType

BASE = "/api/v1/billing/invoices"


@pytest_asyncio.fixture
async def foreign(db_session: AsyncSession) -> dict[str, str]:
    """A series, a 21 % VAT type and a catalog item owned by another clinic."""
    other = Clinic(id=uuid4(), name="Other", tax_id="B87654321")
    db_session.add(other)
    await db_session.flush()
    series = InvoiceSeries(clinic_id=other.id, prefix="OTH", series_type="invoice")
    vat = VatType(clinic_id=other.id, names={"es": "General"}, rate=21.0)
    category = TreatmentCategory(clinic_id=other.id, key="other", names={"es": "Otra"})
    db_session.add_all([series, vat, category])
    await db_session.flush()
    item = TreatmentCatalogItem(
        clinic_id=other.id, category_id=category.id, internal_code="OTH-1", names={"es": "X"}
    )
    db_session.add(item)
    await db_session.commit()
    return {"series": str(series.id), "vat": str(vat.id), "catalog": str(item.id)}


@pytest_asyncio.fixture
async def own_vat(db_session: AsyncSession, test_clinic: Clinic) -> str:
    vat = VatType(clinic_id=test_clinic.id, names={"es": "General"}, rate=21.0)
    db_session.add(vat)
    await db_session.commit()
    return str(vat.id)


async def _draft(client: AsyncClient, headers: dict, patient_id) -> str:
    r = await client.post(BASE, json={"patient_id": str(patient_id)}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()["data"]["id"]


@pytest.mark.asyncio
@pytest.mark.parametrize("which", ["unknown", "other_clinic"])
async def test_create_rejects_a_series_that_isnt_the_clinics(
    client: AsyncClient, auth_headers, test_patient, foreign, which
) -> None:
    series = str(uuid4()) if which == "unknown" else foreign["series"]
    r = await client.post(
        BASE, json={"patient_id": str(test_patient.id), "series_id": series}, headers=auth_headers
    )
    assert r.status_code == 400, r.text


@pytest.mark.asyncio
@pytest.mark.parametrize("field", ["vat_type_id", "catalog_item_id"])
@pytest.mark.parametrize("which", ["unknown", "other_clinic"])
async def test_line_rejects_ids_that_arent_the_clinics(
    client: AsyncClient, auth_headers, test_patient, foreign, field, which
) -> None:
    invoice_id = await _draft(client, auth_headers, test_patient.id)
    value = (
        str(uuid4())
        if which == "unknown"
        else foreign["vat" if field == "vat_type_id" else "catalog"]
    )
    r = await client.post(
        f"{BASE}/{invoice_id}/items",
        json={"description": "Scaling", "unit_price": "100", field: value},
        headers=auth_headers,
    )
    assert r.status_code == 400, r.text


@pytest.mark.asyncio
async def test_line_edit_rejects_another_clinics_vat_type_and_keeps_the_rate(
    client: AsyncClient, auth_headers, test_patient, foreign, own_vat
) -> None:
    invoice_id = await _draft(client, auth_headers, test_patient.id)
    created = await client.post(
        f"{BASE}/{invoice_id}/items",
        json={"description": "Scaling", "unit_price": "100", "vat_type_id": own_vat},
        headers=auth_headers,
    )
    assert created.status_code == 201, created.text
    assert created.json()["data"]["vat_rate"] == 21.0
    item_url = f"{BASE}/{invoice_id}/items/{created.json()['data']['id']}"

    r = await client.put(item_url, json={"vat_type_id": foreign["vat"]}, headers=auth_headers)
    assert r.status_code == 400, r.text

    invoice = await client.get(f"{BASE}/{invoice_id}", headers=auth_headers)
    line = invoice.json()["data"]["items"][0]
    assert line["vat_type_id"] == own_vat
    assert line["vat_rate"] == 21.0
