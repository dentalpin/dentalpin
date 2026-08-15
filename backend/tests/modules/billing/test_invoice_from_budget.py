"""Invoices created from an accepted quote carry its discounts (issue #167).

The quote's line discount and its prorated global discount are folded into
each invoice line (ex-tax); Verifactu derives BaseImponible per line, so an
invoice-level discount is never an option.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from httpx import AsyncClient


async def _accepted_budget(
    client: AsyncClient,
    auth_headers: dict,
    setup: dict,
    *,
    quantity: int = 1,
    line_discount: dict | None = None,
    global_discount: dict | None = None,
) -> tuple[str, str]:
    """Create → add one 100 € line → accept. Returns (budget_id, item_id)."""
    r = await client.post(
        "/api/v1/budget/budgets",
        json={
            "patient_id": setup["patient_id"],
            "valid_from": "2024-01-01",
            **(global_discount or {}),
        },
        headers=auth_headers,
    )
    assert r.status_code == 201, r.text
    budget_id = r.json()["data"]["id"]
    r = await client.post(
        f"/api/v1/budget/budgets/{budget_id}/items",
        json={
            "catalog_item_id": setup["catalog_item_id"],
            "quantity": quantity,
            **(line_discount or {}),
        },
        headers=auth_headers,
    )
    assert r.status_code == 201, r.text
    item_id = r.json()["data"]["id"]
    r = await client.post(
        f"/api/v1/budget/budgets/{budget_id}/accept",
        headers=auth_headers,
        json={"signature": {"signed_by_name": "Test", "relationship_to_patient": "patient"}},
    )
    assert r.status_code == 200, r.text
    return budget_id, item_id


async def _invoice_from_budget(
    client: AsyncClient,
    auth_headers: dict,
    budget_id: str,
    item_id: str,
    quantity: int | None = None,
) -> dict:
    spec: dict = {"budget_item_id": item_id}
    if quantity is not None:
        spec["quantity"] = quantity
    r = await client.post(
        f"/api/v1/billing/invoices/from-budget/{budget_id}",
        json={"items": [spec]},
        headers=auth_headers,
    )
    assert r.status_code == 201, r.text
    invoice_id = r.json()["data"]["id"]
    r = await client.get(f"/api/v1/billing/invoices/{invoice_id}", headers=auth_headers)
    assert r.status_code == 200, r.text
    return r.json()["data"]


@pytest.mark.asyncio
async def test_line_and_global_discounts_reach_the_invoice(
    client: AsyncClient, auth_headers: dict, budget_clinic_setup: dict
) -> None:
    """100 → 80 (line 20%) → 72 (global 10%): stored as one absolute line discount of 28."""
    budget_id, item_id = await _accepted_budget(
        client,
        auth_headers,
        budget_clinic_setup,
        line_discount={"discount_type": "percentage", "discount_value": 20},
        global_discount={"global_discount_type": "percentage", "global_discount_value": 10},
    )
    invoice = await _invoice_from_budget(client, auth_headers, budget_id, item_id)
    line = invoice["items"][0]
    assert line["discount_type"] == "absolute"
    assert Decimal(line["discount_value"]) == Decimal("28.00")
    assert Decimal(line["line_discount"]) == Decimal("28.00")
    assert Decimal(line["line_total"]) == Decimal("72.00")
    assert Decimal(invoice["total"]) == Decimal("72.00")


@pytest.mark.asyncio
async def test_percentage_only_line_discount_is_kept_as_percentage(
    client: AsyncClient, auth_headers: dict, budget_clinic_setup: dict
) -> None:
    budget_id, item_id = await _accepted_budget(
        client,
        auth_headers,
        budget_clinic_setup,
        line_discount={"discount_type": "percentage", "discount_value": 20},
    )
    invoice = await _invoice_from_budget(client, auth_headers, budget_id, item_id)
    line = invoice["items"][0]
    assert line["discount_type"] == "percentage"
    assert Decimal(line["discount_value"]) == Decimal("20.00")
    assert Decimal(invoice["total"]) == Decimal("80.00")


@pytest.mark.asyncio
async def test_absolute_line_discount_prorated_on_partial_invoicing(
    client: AsyncClient, auth_headers: dict, budget_clinic_setup: dict
) -> None:
    """Qty 2 with 30 € absolute discount, invoiced 1 unit → 15 € on that invoice, not 30."""
    budget_id, item_id = await _accepted_budget(
        client,
        auth_headers,
        budget_clinic_setup,
        quantity=2,
        line_discount={"discount_type": "absolute", "discount_value": 30},
    )
    first = await _invoice_from_budget(client, auth_headers, budget_id, item_id, quantity=1)
    assert Decimal(first["items"][0]["discount_value"]) == Decimal("15.00")
    assert Decimal(first["total"]) == Decimal("85.00")
    second = await _invoice_from_budget(client, auth_headers, budget_id, item_id)
    assert Decimal(second["total"]) == Decimal("85.00")


@pytest.mark.asyncio
async def test_absolute_global_discount_is_prorated_and_never_negative(
    client: AsyncClient, auth_headers: dict, budget_clinic_setup: dict
) -> None:
    """A global absolute discount larger than the quote is clamped: the line ends at 0, not below."""
    budget_id, item_id = await _accepted_budget(
        client,
        auth_headers,
        budget_clinic_setup,
        global_discount={"global_discount_type": "absolute", "global_discount_value": 500},
    )
    invoice = await _invoice_from_budget(client, auth_headers, budget_id, item_id)
    line = invoice["items"][0]
    assert Decimal(line["line_discount"]) == Decimal("100.00")
    assert Decimal(line["line_total"]) == Decimal("0.00")
    assert Decimal(invoice["total"]) == Decimal("0.00")


@pytest.mark.asyncio
async def test_no_discount_round_trips_untouched(
    client: AsyncClient, auth_headers: dict, budget_clinic_setup: dict
) -> None:
    budget_id, item_id = await _accepted_budget(client, auth_headers, budget_clinic_setup)
    invoice = await _invoice_from_budget(client, auth_headers, budget_id, item_id)
    line = invoice["items"][0]
    assert line["discount_type"] is None
    assert Decimal(invoice["total"]) == Decimal("100.00")
