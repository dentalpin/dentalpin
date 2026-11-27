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
