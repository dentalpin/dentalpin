"""0 is a payment term: due on the issue date (#1016)."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from tests.modules.billing.helpers import accepted_budget

B = "/api/v1/billing/invoices"


@pytest.mark.asyncio
@pytest.mark.parametrize(("sent", "stored"), [(0, 0), (7, 7), (None, 30)])
async def test_invoice_from_budget_keeps_the_term(
    client: AsyncClient, auth_headers: dict, budget_clinic_setup: dict, sent, stored
) -> None:
    h = auth_headers
    budget_id, item_id = await accepted_budget(client, h, budget_clinic_setup)
    body: dict = {"items": [{"budget_item_id": item_id}]}
    if sent is not None:
        body["payment_term_days"] = sent
    r = await client.post(f"{B}/from-budget/{budget_id}", json=body, headers=h)
    assert r.status_code == 201, r.text
    invoice = (await client.get(f"{B}/{r.json()['data']['id']}", headers=h)).json()["data"]
    assert invoice["payment_term_days"] == stored
