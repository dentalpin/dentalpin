"""An issued credit note is never overdue (#1090).

A credit note is issued with a 0-day term (``due_date = issue_date``) and
stays ``issued`` with a negative total, so the ``issued/partial`` +
``due_date < today`` predicate caught it from the next day on, in the
invoice list filter and in the reports' overdue count and list.
"""

from __future__ import annotations

from datetime import timedelta
from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.utils.dates import clinic_today_for
from app.modules.billing.models import Invoice
from app.modules.reports.services.billing import BillingReportService
from tests.modules.billing.test_credit_note_cap import _issued_invoice

B = "/api/v1/billing/invoices"


@pytest.mark.asyncio
async def test_issued_credit_note_is_not_overdue(
    client: AsyncClient,
    db_session: AsyncSession,
    auth_headers: dict,
    budget_clinic_setup: dict,
) -> None:
    h = auth_headers
    inv = await _issued_invoice(client, h, budget_clinic_setup)
    r = await client.post(f"{B}/{inv['id']}/credit-note", json={"reason": "error"}, headers=h)
    assert r.status_code == 201, r.text
    note_id = r.json()["data"]["id"]
    r = await client.post(f"{B}/{note_id}/issue", json={}, headers=h)
    assert r.status_code == 200, r.text

    # Both documents fell due three days ago; the invoice is still unpaid.
    clinic_id = UUID(budget_clinic_setup["clinic_id"])
    past = await clinic_today_for(db_session, clinic_id) - timedelta(days=3)
    await db_session.execute(
        update(Invoice)
        .where(Invoice.id.in_([UUID(inv["id"]), UUID(note_id)]))
        .values(issue_date=past, due_date=past)
    )
    await db_session.commit()

    r = await client.get(B, params={"overdue": "true"}, headers=h)
    assert r.status_code == 200, r.text
    assert [row["id"] for row in r.json()["data"]] == [inv["id"]]

    # The list rows carry the link the UI's overdue marker reads.
    r = await client.get(B, headers=h)
    links = {row["id"]: row["credit_note_for_id"] for row in r.json()["data"]}
    assert links == {inv["id"]: None, note_id: inv["id"]}

    summary = await BillingReportService.get_summary(db_session, clinic_id, past, past)
    assert summary["overdue_count"] == 1
    overdue = await BillingReportService.get_overdue_invoices(db_session, clinic_id)
    assert [str(row["id"]) for row in overdue] == [inv["id"]]
