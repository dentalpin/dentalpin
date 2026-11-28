"""A percentage discount on a budget is capped at 100 % (#1241).

150 % on a line gave a line total of -50; 250 % as the global discount took
the whole budget negative. A request carrying both the type and the value is
refused by the schema (422); a partial update that would leave a stored line
or budget above 100 % is refused by the service (400). An absolute discount
above the line subtotal is still accepted and capped, as before.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from httpx import AsyncClient

B = "/api/v1/budget/budgets"


async def _draft(client: AsyncClient, h: dict, setup: dict, **body) -> str:
    r = await client.post(
        B, json={"patient_id": setup["patient_id"], "valid_from": "2024-01-01", **body}, headers=h
    )
    assert r.status_code == 201, r.text
    return r.json()["data"]["id"]


async def _item(client: AsyncClient, h: dict, setup: dict, budget_id: str, **discount):
    return await client.post(
        f"{B}/{budget_id}/items",
        json={"catalog_item_id": setup["catalog_item_id"], "quantity": 1, **discount},
        headers=h,
    )


@pytest.mark.asyncio
async def test_line_percentage_above_100_is_refused(
    client: AsyncClient, auth_headers: dict, budget_clinic_setup: dict
) -> None:
    s, h = budget_clinic_setup, auth_headers
    budget_id = await _draft(client, h, s)

    r = await _item(client, h, s, budget_id, discount_type="percentage", discount_value=150)
    assert r.status_code == 422, r.text

    r = await _item(client, h, s, budget_id, discount_type="percentage", discount_value=100)
    assert r.status_code == 201, r.text
    assert Decimal(r.json()["data"]["line_total"]) == 0
    item_id = r.json()["data"]["id"]

    r = await client.put(
        f"{B}/{budget_id}/items/{item_id}",
        json={"discount_type": "percentage", "discount_value": 101},
        headers=h,
    )
    assert r.status_code == 422, r.text

    # An absolute discount above the subtotal is still capped, not refused.
    r = await _item(client, h, s, budget_id, discount_type="absolute", discount_value=100000)
    assert r.status_code == 201, r.text
    assert Decimal(r.json()["data"]["line_total"]) == 0


@pytest.mark.asyncio
async def test_line_partial_update_cannot_leave_percentage_above_100(
    client: AsyncClient, auth_headers: dict, budget_clinic_setup: dict
) -> None:
    s, h = budget_clinic_setup, auth_headers
    budget_id = await _draft(client, h, s)

    r = await _item(client, h, s, budget_id, discount_type="percentage", discount_value=10)
    pct_url = f"{B}/{budget_id}/items/{r.json()['data']['id']}"
    r = await client.put(pct_url, json={"discount_value": 150}, headers=h)
    assert r.status_code == 400, r.text

    r = await _item(client, h, s, budget_id, discount_type="absolute", discount_value=150)
    abs_url = f"{B}/{budget_id}/items/{r.json()['data']['id']}"
    r = await client.put(abs_url, json={"discount_type": "percentage"}, headers=h)
    assert r.status_code == 400, r.text

    detail = (await client.get(f"{B}/{budget_id}", headers=h)).json()["data"]
    assert Decimal(detail["total"]) >= 0
    assert {i["discount_type"] for i in detail["items"]} == {"percentage", "absolute"}


@pytest.mark.asyncio
async def test_global_percentage_above_100_is_refused(
    client: AsyncClient, auth_headers: dict, budget_clinic_setup: dict
) -> None:
    s, h = budget_clinic_setup, auth_headers

    r = await client.post(
        B,
        json={
            "patient_id": s["patient_id"],
            "global_discount_type": "percentage",
            "global_discount_value": 250,
        },
        headers=h,
    )
    assert r.status_code == 422, r.text

    budget_id = await _draft(client, h, s)
    await _item(client, h, s, budget_id)
    r = await client.put(
        f"{B}/{budget_id}",
        json={"global_discount_type": "percentage", "global_discount_value": 250},
        headers=h,
    )
    assert r.status_code == 422, r.text

    r = await client.put(
        f"{B}/{budget_id}",
        json={"global_discount_type": "percentage", "global_discount_value": 10},
        headers=h,
    )
    assert r.status_code == 200, r.text
    r = await client.put(f"{B}/{budget_id}", json={"global_discount_value": 250}, headers=h)
    assert r.status_code == 400, r.text

    detail = (await client.get(f"{B}/{budget_id}", headers=h)).json()["data"]
    assert Decimal(detail["global_discount_value"]) == 10
    assert Decimal(detail["total"]) >= 0


@pytest.mark.asyncio
async def test_row_stored_above_100_stays_editable(
    client: AsyncClient, auth_headers: dict, budget_clinic_setup: dict, db_session
) -> None:
    """A row saved above 100 % before the cap can still take updates that
    leave the discount alone; touching the discount is still checked."""
    from uuid import UUID

    from sqlalchemy import update

    from app.modules.budget.models import Budget, BudgetItem

    s, h = budget_clinic_setup, auth_headers
    budget_id = await _draft(client, h, s)
    r = await _item(client, h, s, budget_id, discount_type="percentage", discount_value=10)
    item_id = r.json()["data"]["id"]
    # The API refuses these values now, so write them the way old rows look.
    await db_session.execute(
        update(BudgetItem)
        .where(BudgetItem.id == UUID(item_id))
        .values(discount_value=Decimal("150"))
    )
    await db_session.execute(
        update(Budget)
        .where(Budget.id == UUID(budget_id))
        .values(global_discount_type="percentage", global_discount_value=Decimal("250"))
    )
    await db_session.flush()
    db_session.expire_all()

    item_url = f"{B}/{budget_id}/items/{item_id}"
    r = await client.put(item_url, json={"notes": "only notes"}, headers=h)
    assert r.status_code == 200, r.text
    r = await client.put(f"{B}/{budget_id}", json={"internal_notes": "x"}, headers=h)
    assert r.status_code == 200, r.text

    r = await client.put(item_url, json={"discount_value": 120}, headers=h)
    assert r.status_code == 400, r.text
    r = await client.put(f"{B}/{budget_id}", json={"global_discount_value": 120}, headers=h)
    assert r.status_code == 400, r.text
    # Bringing it back under the cap is allowed.
    r = await client.put(item_url, json={"discount_value": 50}, headers=h)
    assert r.status_code == 200, r.text
