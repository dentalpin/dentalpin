"""A percentage discount on an invoice line is capped at 100 % (#1241).

150 % gave a line total of -50.00, and such a draft could be issued with a
regular invoice number. A request carrying both the type and the value is
refused by the schema (422); a partial update that would leave the stored
line above 100 % is refused by the service (400).
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from httpx import AsyncClient

B = "/api/v1/billing/invoices"


@pytest.mark.asyncio
async def test_invoice_line_percentage_above_100_is_refused(
    client: AsyncClient, auth_headers, test_patient
) -> None:
    h = auth_headers
    invoice_id = (
        await client.post(B, json={"patient_id": str(test_patient.id)}, headers=h)
    ).json()["data"]["id"]
    line = {"description": "Scaling", "unit_price": "100"}

    r = await client.post(
        f"{B}/{invoice_id}/items",
        json={**line, "discount_type": "percentage", "discount_value": "150"},
        headers=h,
    )
    assert r.status_code == 422, r.text

    r = await client.post(
        f"{B}/{invoice_id}/items",
        json={**line, "discount_type": "percentage", "discount_value": "10"},
        headers=h,
    )
    assert r.status_code == 201, r.text
    pct_url = f"{B}/{invoice_id}/items/{r.json()['data']['id']}"

    r = await client.put(
        pct_url, json={"discount_type": "percentage", "discount_value": "100.01"}, headers=h
    )
    assert r.status_code == 422, r.text
    r = await client.put(pct_url, json={"discount_value": "150"}, headers=h)
    assert r.status_code == 400, r.text

    # Absolute above the subtotal: still accepted and capped at the subtotal.
    r = await client.post(
        f"{B}/{invoice_id}/items",
        json={**line, "discount_type": "absolute", "discount_value": "150"},
        headers=h,
    )
    assert r.status_code == 201, r.text
    assert Decimal(str(r.json()["data"]["line_total"])) == 0
    abs_url = f"{B}/{invoice_id}/items/{r.json()['data']['id']}"
    r = await client.put(abs_url, json={"discount_type": "percentage"}, headers=h)
    assert r.status_code == 400, r.text

    invoice = (await client.get(f"{B}/{invoice_id}", headers=h)).json()["data"]
    assert Decimal(str(invoice["total"])) >= 0


@pytest.mark.asyncio
async def test_invoice_line_stored_above_100_stays_editable(
    client: AsyncClient, auth_headers, test_patient, db_session
) -> None:
    from uuid import UUID

    from sqlalchemy import update

    from app.modules.billing.models import InvoiceItem

    h = auth_headers
    invoice_id = (
        await client.post(B, json={"patient_id": str(test_patient.id)}, headers=h)
    ).json()["data"]["id"]
    r = await client.post(
        f"{B}/{invoice_id}/items",
        json={
            "description": "Scaling",
            "unit_price": "100",
            "discount_type": "percentage",
            "discount_value": "10",
        },
        headers=h,
    )
    item_id = r.json()["data"]["id"]
    await db_session.execute(
        update(InvoiceItem)
        .where(InvoiceItem.id == UUID(item_id))
        .values(discount_value=Decimal("150"))
    )
    await db_session.flush()
    db_session.expire_all()

    item_url = f"{B}/{invoice_id}/items/{item_id}"
    r = await client.put(item_url, json={"description": "Scaling (full)"}, headers=h)
    assert r.status_code == 200, r.text
    r = await client.put(item_url, json={"discount_value": "120"}, headers=h)
    assert r.status_code == 400, r.text


@pytest.mark.asyncio
async def test_budget_stored_above_100_can_still_be_invoiced(
    client: AsyncClient, auth_headers: dict, budget_clinic_setup: dict, db_session
) -> None:
    """Invoicing copies the budget line's discount without re-checking it, so
    an accepted budget saved above 100 % before the cap still invoices."""
    from uuid import UUID

    from sqlalchemy import update

    from app.modules.budget.models import BudgetItem
    from tests.modules.billing.helpers import accepted_budget, invoice_from_budget

    s, h = budget_clinic_setup, auth_headers
    budget_id, item_id = await accepted_budget(
        client, h, s, line_discount={"discount_type": "percentage", "discount_value": 10}
    )
    await db_session.execute(
        update(BudgetItem)
        .where(BudgetItem.id == UUID(item_id))
        .values(discount_value=Decimal("150"))
    )
    await db_session.flush()
    db_session.expire_all()

    draft = await invoice_from_budget(client, h, budget_id, item_id)
    line = draft["items"][0]
    assert line["discount_type"] == "percentage"
    assert Decimal(str(line["discount_value"])) == 150
