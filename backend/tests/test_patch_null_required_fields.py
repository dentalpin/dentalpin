"""An explicit ``null`` on a required field in a PATCH is a 422 (#976).

The update schemas type every field ``X | None = None`` so a client can
omit it, and the services copy ``model_dump(exclude_unset=True)`` onto
the row. A ``null`` that was *sent* therefore reached a NOT NULL column
and surfaced as an unhandled ``IntegrityError``: a 500, not a validation
error naming the field. Omitting the field keeps working.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

API = "/api/v1"


async def _post(client: AsyncClient, headers: dict, path: str, body: dict) -> dict:
    res = await client.post(f"{API}{path}", json=body, headers=headers)
    assert res.status_code == 201, (path, res.text)
    return res.json()["data"]


async def _lab(client, headers):
    return await _post(client, headers, "/contacts/", {"name": "Lab Uno", "contact_type": "lab"})


async def _supplier(client, headers):
    return await _post(client, headers, "/suppliers", {"name": "Acme"})


async def _expense(client, headers, patient):
    body = {"category": "rent", "amount": "100", "expense_date": "2026-08-01"}
    return await _post(client, headers, "/expenses/", body)


async def _contact(client, headers, patient):
    return await _lab(client, headers)


async def _medication(client, headers, patient):
    return await _post(client, headers, "/medication_catalog/", {"name": "Amoxicilina"})


async def _supplier_row(client, headers, patient):
    return await _supplier(client, headers)


async def _lab_order(client, headers, patient):
    lab = await _lab(client, headers)
    body = {
        "patient_id": str(patient.id),
        "lab_contact_id": lab["id"],
        "work_type": "crown",
        "sent_date": "2026-08-01",
    }
    return await _post(client, headers, "/lab_orders/", body)


async def _review(client, headers, patient):
    supplier = await _supplier(client, headers)
    body = {"supplier_id": supplier["id"], "score": 4}
    return await _post(client, headers, "/supplier_ratings/reviews", body)


CASES = [
    ("/expenses/{id}", _expense, "category"),
    ("/expenses/{id}", _expense, "amount"),
    ("/expenses/{id}", _expense, "expense_date"),
    ("/contacts/{id}", _contact, "name"),
    ("/contacts/{id}", _contact, "contact_type"),
    ("/contacts/{id}", _contact, "is_active"),
    ("/medication_catalog/{id}", _medication, "name"),
    ("/medication_catalog/{id}", _medication, "form"),
    ("/medication_catalog/{id}", _medication, "requires_prescription"),
    ("/medication_catalog/{id}", _medication, "is_active"),
    ("/suppliers/{id}", _supplier_row, "name"),
    ("/suppliers/{id}", _supplier_row, "is_active"),
    ("/suppliers/{id}", _supplier_row, "is_preferred"),
    ("/lab_orders/{id}", _lab_order, "lab_contact_id"),
    ("/lab_orders/{id}", _lab_order, "work_type"),
    ("/lab_orders/{id}", _lab_order, "status"),
    ("/supplier_ratings/reviews/{id}", _review, "score"),
]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("path", "create", "field"), CASES, ids=lambda v: getattr(v, "__name__", v)
)
async def test_null_on_a_required_field_is_422(
    client: AsyncClient, auth_headers: dict, test_patient, path, create, field
):
    row = await create(client, auth_headers, test_patient)
    url = f"{API}{path.format(id=row['id'])}"
    res = await client.patch(url, json={field: None}, headers=auth_headers)
    assert res.status_code == 422, res.text
    assert field in res.text

    # Omitting the field is still "leave it alone".
    res = await client.patch(url, json={}, headers=auth_headers)
    assert res.status_code == 200, res.text
