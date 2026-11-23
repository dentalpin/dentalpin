"""An invoice number outside latin-1 doesn't break the PDF download (#1015)."""

from __future__ import annotations

from urllib.parse import unquote

import pytest
from httpx import AsyncClient

from app.modules.billing.pdf import InvoicePDFService
from tests.modules.billing.helpers import accepted_budget, invoice_from_budget


@pytest.mark.asyncio
async def test_pdf_download_with_a_hungarian_series_prefix(
    client: AsyncClient, auth_headers: dict, budget_clinic_setup: dict, monkeypatch
) -> None:
    h = auth_headers
    setup = budget_clinic_setup
    budget_id, item_id = await accepted_budget(client, h, setup)
    r = await client.put(
        f"/api/v1/patients/{setup['patient_id']}", json={"billing_tax_id": "12345678Z"}, headers=h
    )
    assert r.status_code == 200, r.text
    r = await client.post(
        "/api/v1/billing/series",
        json={"prefix": "BŐV", "series_type": "invoice", "is_default": True},
        headers=h,
    )
    assert r.status_code == 201, r.text
    invoice = await invoice_from_budget(client, h, budget_id, item_id)
    url = f"/api/v1/billing/invoices/{invoice['id']}"
    r = await client.post(f"{url}/issue", json={}, headers=h)
    assert r.status_code == 200, r.text
    number = (await client.get(url, headers=h)).json()["data"]["invoice_number"]

    async def render(*args, **kwargs) -> bytes:
        return b"%PDF-1.4"

    monkeypatch.setattr(InvoicePDFService, "generate_pdf", render)
    got = await client.get(f"{url}/pdf", headers=h)
    assert got.status_code == 200
    header = got.headers["content-disposition"]
    assert unquote(header.split("filename*=UTF-8''")[1]) == f"factura_{number}.pdf"
