"""A credit note of a line with an absolute discount credits what was billed (#1013)."""

from __future__ import annotations

from decimal import Decimal

import pytest
from httpx import AsyncClient

from tests.modules.billing.helpers import accepted_budget, invoice_from_budget

B = "/api/v1/billing/invoices"


async def _discounted_invoice(client: AsyncClient, h: dict, setup: dict, discount: str) -> dict:
    """An issued invoice of one line, quantity 3, less an absolute discount."""
    budget_id, item_id = await accepted_budget(client, h, setup, quantity=3)
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
    draft = await invoice_from_budget(client, h, budget_id, item_id)
    r = await client.put(
        f"{B}/{draft['id']}/items/{draft['items'][0]['id']}",
        json={"discount_type": "absolute", "discount_value": discount},
        headers=h,
    )
    assert r.status_code == 200, r.text
    r = await client.post(f"{B}/{draft['id']}/issue", json={}, headers=h)
    assert r.status_code == 200, r.text
    return (await client.get(f"{B}/{draft['id']}", headers=h)).json()["data"]


async def _credit(client: AsyncClient, h: dict, inv: dict, body: dict) -> dict:
    r = await client.post(f"{B}/{inv['id']}/credit-note", json=body, headers=h)
    assert r.status_code == 201, r.text
    return (await client.get(f"{B}/{r.json()['data']['id']}", headers=h)).json()["data"]


@pytest.mark.asyncio
async def test_full_credit_note_mirrors_the_invoice(
    client: AsyncClient, auth_headers: dict, budget_clinic_setup: dict
) -> None:
    inv = await _discounted_invoice(client, auth_headers, budget_clinic_setup, "28.00")
    note = await _credit(client, auth_headers, inv, {"reason": "error"})

    for field in ("subtotal", "total_discount", "total_tax", "total"):
        assert Decimal(note[field]) == -Decimal(inv[field]), field

    again = await client.post(
        f"{B}/{inv['id']}/credit-note", json={"reason": "x"}, headers=auth_headers
    )
    assert again.status_code == 400


@pytest.mark.asyncio
async def test_partial_credit_notes_share_the_discount(
    client: AsyncClient, auth_headers: dict, budget_clinic_setup: dict
) -> None:
    inv = await _discounted_invoice(client, auth_headers, budget_clinic_setup, "10.00")
    one = {"reason": "unit", "items": [{"invoice_item_id": inv["items"][0]["id"], "quantity": 1}]}
    notes = [await _credit(client, auth_headers, inv, one) for _ in range(3)]

    # 10.00 / 3 rounds up per note, so three notes never exceed the invoice.
    assert [Decimal(n["total_discount"]) for n in notes] == [Decimal("-3.34")] * 3
    assert -sum(Decimal(n["total"]) for n in notes) <= Decimal(inv["total"])


@pytest.mark.asyncio
async def test_full_credit_note_of_a_total_that_rounded_down(
    client: AsyncClient, auth_headers: dict, budget_clinic_setup: dict, db_session
) -> None:
    """The stored total is in cents, the note's fresh one is not yet (#1013).

    100 less 9.99 at 21% is 108.9121, stored as 108.91: comparing the two
    refused the full note as more than the amount creditable.
    """
    from sqlalchemy import update

    from app.modules.billing.models import InvoiceItem

    h, setup = auth_headers, budget_clinic_setup
    budget_id, item_id = await accepted_budget(client, h, setup)
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
    draft = await invoice_from_budget(client, h, budget_id, item_id)
    line = draft["items"][0]["id"]
    await db_session.execute(update(InvoiceItem).where(InvoiceItem.id == line).values(vat_rate=21))
    await db_session.commit()
    db_session.expire_all()
    r = await client.put(
        f"{B}/{draft['id']}/items/{line}",
        json={"discount_type": "absolute", "discount_value": "9.99"},
        headers=h,
    )
    assert r.status_code == 200, r.text
    r = await client.post(f"{B}/{draft['id']}/issue", json={}, headers=h)
    assert r.status_code == 200, r.text
    inv = (await client.get(f"{B}/{draft['id']}", headers=h)).json()["data"]
    assert Decimal(inv["total"]) == Decimal("108.91")

    note = await _credit(client, h, inv, {"reason": "error"})
    assert Decimal(note["total"]) == Decimal("-108.91")
