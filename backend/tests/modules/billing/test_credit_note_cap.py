"""A credit note cannot credit more than its invoice's total (#769).

Credit notes counted against the cap are every other live one of the same
invoice, drafts included; voided and deleted ones are not.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from tests.modules.billing.helpers import accepted_budget, invoice_from_budget

B = "/api/v1/billing/invoices"


async def _issued_invoice(client: AsyncClient, h: dict, setup: dict) -> dict:
    """An issued invoice of one line, quantity 2."""
    budget_id, item_id = await accepted_budget(client, h, setup, quantity=2)
    r = await client.put(
        f"/api/v1/patients/{setup['patient_id']}", json={"billing_tax_id": "12345678Z"}, headers=h
    )
    assert r.status_code == 200, r.text
    for prefix, series_type in (("FAC", "invoice"), ("RECT", "credit_note")):
        r = await client.post(
            "/api/v1/billing/series",
            json={"prefix": prefix, "series_type": series_type, "is_default": True},
            headers=h,
        )
        assert r.status_code == 201, r.text
    inv = await invoice_from_budget(client, h, budget_id, item_id)
    r = await client.post(f"{B}/{inv['id']}/issue", json={}, headers=h)
    assert r.status_code == 200, r.text
    return (await client.get(f"{B}/{inv['id']}", headers=h)).json()["data"]


def _one_unit(inv: dict) -> dict:
    return {
        "reason": "partial",
        "items": [{"invoice_item_id": inv["items"][0]["id"], "quantity": 1}],
    }


@pytest.mark.asyncio
async def test_second_full_credit_note_is_refused(
    client: AsyncClient, auth_headers: dict, budget_clinic_setup: dict
) -> None:
    h = auth_headers
    inv = await _issued_invoice(client, h, budget_clinic_setup)

    r = await client.post(f"{B}/{inv['id']}/credit-note", json={"reason": "error"}, headers=h)
    assert r.status_code == 201, r.text
    first = r.json()["data"]["id"]
    r = await client.post(f"{B}/{first}/issue", json={}, headers=h)
    assert r.status_code == 200, r.text

    r = await client.post(f"{B}/{inv['id']}/credit-note", json={"reason": "again"}, headers=h)
    assert r.status_code == 400
    assert "creditable" in r.json()["message"]


@pytest.mark.asyncio
async def test_partial_credit_notes_add_up_to_the_total_and_no_further(
    client: AsyncClient, auth_headers: dict, budget_clinic_setup: dict
) -> None:
    h = auth_headers
    inv = await _issued_invoice(client, h, budget_clinic_setup)

    for _ in range(2):
        r = await client.post(f"{B}/{inv['id']}/credit-note", json=_one_unit(inv), headers=h)
        assert r.status_code == 201, r.text
    # Two drafts already cover the whole invoice.
    r = await client.post(f"{B}/{inv['id']}/credit-note", json=_one_unit(inv), headers=h)
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_a_deleted_draft_frees_its_amount(
    client: AsyncClient, auth_headers: dict, budget_clinic_setup: dict
) -> None:
    h = auth_headers
    inv = await _issued_invoice(client, h, budget_clinic_setup)

    r = await client.post(f"{B}/{inv['id']}/credit-note", json={"reason": "error"}, headers=h)
    assert r.status_code == 201, r.text
    r = await client.delete(f"{B}/{r.json()['data']['id']}", headers=h)
    assert r.status_code == 204, r.text

    r = await client.post(f"{B}/{inv['id']}/credit-note", json={"reason": "redo"}, headers=h)
    assert r.status_code == 201, r.text


@pytest.mark.asyncio
async def test_issue_refuses_a_draft_grown_past_the_remaining_amount(
    client: AsyncClient, auth_headers: dict, budget_clinic_setup: dict
) -> None:
    h = auth_headers
    inv = await _issued_invoice(client, h, budget_clinic_setup)

    drafts = []
    for _ in range(2):
        r = await client.post(f"{B}/{inv['id']}/credit-note", json=_one_unit(inv), headers=h)
        assert r.status_code == 201, r.text
        draft_id = r.json()["data"]["id"]
        drafts.append((await client.get(f"{B}/{draft_id}", headers=h)).json()["data"])
    grown = drafts[0]
    r = await client.put(
        f"{B}/{grown['id']}/items/{grown['items'][0]['id']}", json={"quantity": 2}, headers=h
    )
    assert r.status_code == 200, r.text

    r = await client.post(f"{B}/{grown['id']}/issue", json={}, headers=h)
    assert r.status_code == 400
    # Back within the remaining amount, it issues.
    r = await client.put(
        f"{B}/{grown['id']}/items/{grown['items'][0]['id']}", json={"quantity": 1}, headers=h
    )
    assert r.status_code == 200, r.text
    r = await client.post(f"{B}/{grown['id']}/issue", json={}, headers=h)
    assert r.status_code == 200, r.text
