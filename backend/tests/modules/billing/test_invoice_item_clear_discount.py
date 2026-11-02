"""Clearing a draft line's discount on edit (#743).

The edit modal used to send ``discount_type: undefined`` for the "-" option,
which drops the key, so the backend kept the old discount. It now sends
``null``; this pins the backend half of that contract.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_null_discount_clears_it_and_an_omitted_key_keeps_it(
    client: AsyncClient, auth_headers, test_patient
):
    base = "/api/v1/billing/invoices"
    invoice_id = (
        await client.post(base, json={"patient_id": str(test_patient.id)}, headers=auth_headers)
    ).json()["data"]["id"]
    created = await client.post(
        f"{base}/{invoice_id}/items",
        json={
            "description": "Scaling",
            "unit_price": "100",
            "discount_type": "absolute",
            "discount_value": "10",
        },
        headers=auth_headers,
    )
    assert created.status_code == 201, created.text
    item_url = f"{base}/{invoice_id}/items/{created.json()['data']['id']}"

    kept = await client.put(item_url, json={"description": "Scaling (full)"}, headers=auth_headers)
    assert kept.status_code == 200, kept.text
    assert kept.json()["data"]["discount_type"] == "absolute"

    cleared = await client.put(
        item_url, json={"discount_type": None, "discount_value": None}, headers=auth_headers
    )
    assert cleared.status_code == 200, cleared.text
    line = cleared.json()["data"]
    assert line["discount_type"] is None
    assert line["discount_value"] is None
    assert Decimal(str(line["line_discount"])) == 0
