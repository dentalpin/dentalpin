"""sistema_ts API: settings gate, opposition, item types, documents."""

from datetime import date
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.modules.sistema_ts.models import SistemaTsDocument, SistemaTsSettings

SETTINGS = "/api/v1/sistema_ts/settings"


@pytest.mark.asyncio
async def test_settings_gate_and_write_only_secrets(client: AsyncClient, auth_headers, test_clinic):
    res = await client.get(SETTINGS, headers=auth_headers)
    assert res.status_code == 200
    body = res.json()["data"]
    assert body["enabled"] is False and body["deadline"] == f"{body['year'] + 1}-01-31"
    assert body["certificate_expires_at"].startswith("2027")  # vendored SanitelCF
    res = await client.put(SETTINGS, json={"enabled": True}, headers=auth_headers)
    assert res.status_code == 400  # credentials incomplete
    res = await client.put(
        SETTINGS, json={"cf_proprietario": "RSSMRA80A01H501X"}, headers=auth_headers
    )
    assert res.status_code == 400  # wrong check character
    res = await client.put(
        SETTINGS,
        json={
            "username": "PROVAX00X00X000Y",
            "password": "Salve123",
            "pincode": "1234567890",
            "cf_proprietario": "rssmra80a01h501u",
        },
        headers=auth_headers,
    )
    assert res.status_code == 200, res.text
    body = res.json()["data"]
    assert (
        body["has_password"]
        and body["has_pincode"]
        and body["cf_proprietario"] == "RSSMRA80A01H501U"
    )
    assert "password" not in body and "pincode" not in body
    res = await client.put(
        SETTINGS, json={"enabled": True, "environment": "prod"}, headers=auth_headers
    )
    assert res.status_code == 200 and res.json()["data"]["enabled"] is True
    res = await client.put(
        SETTINGS, json={"certificate_b64": "bm90IGEgY2VydA=="}, headers=auth_headers
    )
    assert res.status_code == 400


@pytest.mark.asyncio
async def test_opposition_roundtrip(client: AsyncClient, auth_headers, test_clinic, test_patient):
    url = f"/api/v1/sistema_ts/opposition/{test_patient.id}"
    res = await client.get(url, headers=auth_headers)
    assert res.status_code == 200 and res.json()["data"]["opposed"] is False
    res = await client.put(
        url, json={"opposed": True, "note": "richiesta verbale"}, headers=auth_headers
    )
    assert res.status_code == 200 and res.json()["data"]["opposed"] is True
    assert res.json()["data"]["opposed_since"] == date.today().isoformat()
    res = await client.put(url, json={"opposed": False}, headers=auth_headers)
    assert res.json()["data"]["opposed"] is False and res.json()["data"]["revoked_at"] is not None


@pytest.mark.asyncio
async def test_opposition_and_item_type_reject_foreign_ids(
    client: AsyncClient, auth_headers, test_clinic, db_session
):
    """A patient or catalog item of another clinic is a 404, never an oracle."""
    from ._fixtures import make_clinic, make_patient

    other_clinic, _user, _settings = await make_clinic(db_session)
    other_patient = await make_patient(db_session, other_clinic)
    await db_session.commit()

    url = f"/api/v1/sistema_ts/opposition/{other_patient.id}"
    assert (await client.get(url, headers=auth_headers)).status_code == 404
    assert (await client.put(url, json={"opposed": True}, headers=auth_headers)).status_code == 404
    res = await client.put(
        f"/api/v1/sistema_ts/item-types/{uuid4()}", json={"tipo_spesa": "IC"}, headers=auth_headers
    )
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_item_types_and_documents(
    client: AsyncClient, auth_headers, test_clinic, test_patient, db_session
):
    item_id = uuid4()
    from app.modules.catalog.models import TreatmentCatalogItem, TreatmentCategory

    cat = TreatmentCategory(
        id=uuid4(), clinic_id=test_clinic.id, key="est", names={"en": "Aesthetic"}
    )
    db_session.add(cat)
    await db_session.flush()
    db_session.add(
        TreatmentCatalogItem(
            id=item_id,
            clinic_id=test_clinic.id,
            category_id=cat.id,
            internal_code="WHT",
            names={"en": "Whitening"},
            default_price=100,
        )
    )
    await db_session.commit()
    res = await client.put(
        f"/api/v1/sistema_ts/item-types/{item_id}", json={"tipo_spesa": "IC"}, headers=auth_headers
    )
    assert res.status_code == 200, res.text
    res = await client.get("/api/v1/sistema_ts/item-types", headers=auth_headers)
    assert res.json()["data"][0]["tipo_spesa"] == "IC"
    res = await client.put(
        f"/api/v1/sistema_ts/item-types/{item_id}", json={"tipo_spesa": "XX"}, headers=auth_headers
    )
    assert res.status_code == 422

    db_session.add(SistemaTsSettings(clinic_id=test_clinic.id, enabled=False))
    doc = SistemaTsDocument(
        clinic_id=test_clinic.id,
        invoice_id=uuid4(),
        patient_id=test_patient.id,
        operation="inserimento",
        p_iva="01234567897",
        data_emissione=date(2026, 2, 1),
        dispositivo="1",
        num_documento="F/1",
        total_amount=10,
        voci=[],
        state="rejected",
        created_at=__import__("datetime").datetime.now(__import__("datetime").UTC),
        error_message="E01",
    )
    from app.core.auth.models import User
    from app.modules.billing.models import Invoice

    user_id = (await db_session.execute(select(User.id).limit(1))).scalar()
    inv = Invoice(
        id=doc.invoice_id,
        clinic_id=test_clinic.id,
        patient_id=test_patient.id,
        invoice_number="F/1",
        sequential_number=1,
        status="paid",
        issue_date=date(2026, 2, 1),
        billing_name="x",
        subtotal=10,
        total=10,
        created_by=user_id,
        issued_by=user_id,
    )
    db_session.add(inv)
    await db_session.flush()
    db_session.add(doc)
    await db_session.commit()
    res = await client.get("/api/v1/sistema_ts/documents?year=2026", headers=auth_headers)
    assert res.status_code == 200 and res.json()["total"] == 1
    res = await client.get(
        f"/api/v1/sistema_ts/documents/by-invoice/{doc.invoice_id}", headers=auth_headers
    )
    assert res.json()["data"][0]["state"] == "rejected"
    res = await client.post(f"/api/v1/sistema_ts/documents/{doc.id}/retry", headers=auth_headers)
    assert res.status_code == 200 and res.json()["data"]["state"] == "pending"
    res = await client.post(f"/api/v1/sistema_ts/documents/{doc.id}/retry", headers=auth_headers)
    assert res.status_code == 409
    res = await client.get(SETTINGS, headers=auth_headers)
    assert res.json()["data"]["unsent_count"] == 1
