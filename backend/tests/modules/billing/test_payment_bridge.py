"""Budget ↔ invoice bridge (issue #178).

One collection for a piece of work must show up on every surface that
shows that work: invoice ``total_paid``/status, the patient Billing
summary, the payments ledger, and the quote's "Budget payments" card.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic, User
from app.modules.billing.models import Invoice, InvoiceItem, InvoicePayment, InvoiceSeries
from app.modules.budget.models import Budget
from app.modules.patients.models import Patient

TODAY = date.today().isoformat()


async def _user_id(db: AsyncSession):
    return (await db.execute(select(User))).scalars().first().id


async def _budget(db: AsyncSession, clinic: Clinic, patient: Patient, total: str) -> Budget:
    budget = Budget(
        id=uuid4(),
        clinic_id=clinic.id,
        patient_id=patient.id,
        budget_number=f"PRES-{uuid4().hex[:6]}",
        status="accepted",
        valid_from=date.today(),
        created_by=await _user_id(db),
        total=Decimal(total),
    )
    db.add(budget)
    await db.commit()
    return budget


async def _draft_invoice(
    db: AsyncSession, clinic: Clinic, patient: Patient, total: str, budget: Budget | None
) -> Invoice:
    if not (
        await db.execute(select(InvoiceSeries.id).where(InvoiceSeries.clinic_id == clinic.id))
    ).first():
        db.add(
            InvoiceSeries(
                id=uuid4(),
                clinic_id=clinic.id,
                prefix="FAC",
                series_type="invoice",
                is_default=True,
            )
        )
    inv = Invoice(
        id=uuid4(),
        clinic_id=clinic.id,
        patient_id=patient.id,
        status="draft",
        billing_name="Cliente Test",
        billing_tax_id="B12345678",
        subtotal=Decimal(total),
        total=Decimal(total),
        created_by=await _user_id(db),
        budget_id=budget.id if budget else None,
    )
    db.add(inv)
    await db.flush()
    db.add(
        InvoiceItem(
            id=uuid4(),
            clinic_id=clinic.id,
            invoice_id=inv.id,
            description="Servicio",
            unit_price=Decimal(total),
            quantity=1,
            vat_rate=0.0,
            line_subtotal=Decimal(total),
            line_tax=Decimal("0.00"),
            line_total=Decimal(total),
            display_order=0,
        )
    )
    await db.commit()
    return inv


async def _issue(client: AsyncClient, headers: dict, invoice_id) -> None:
    r = await client.post(f"/api/v1/billing/invoices/{invoice_id}/issue", json={}, headers=headers)
    assert r.status_code == 200, r.text


async def _pay_invoice(client: AsyncClient, headers: dict, invoice_id, amount: str) -> dict:
    r = await client.post(
        f"/api/v1/billing/invoices/{invoice_id}/payments",
        json={"amount": amount, "method": "cash", "payment_date": TODAY},
        headers=headers,
    )
    assert r.status_code == 201, r.text
    return r.json()["data"]


async def _pay(client: AsyncClient, headers: dict, patient_id, allocations: list[dict]) -> dict:
    amount = sum(Decimal(a["amount"]) for a in allocations)
    r = await client.post(
        "/api/v1/payments",
        json={
            "patient_id": str(patient_id),
            "amount": str(amount),
            "method": "cash",
            "payment_date": TODAY,
            "allocations": allocations,
        },
        headers=headers,
    )
    assert r.status_code == 201, r.text
    return r.json()["data"]


async def _surfaces(client: AsyncClient, headers: dict, invoice_id, patient_id, budget_id) -> dict:
    inv = (await client.get(f"/api/v1/billing/invoices/{invoice_id}", headers=headers)).json()[
        "data"
    ]
    billing = (
        await client.get(f"/api/v1/billing/patients/{patient_id}/summary", headers=headers)
    ).json()["data"]
    ledger = (
        await client.get(f"/api/v1/payments/patients/{patient_id}/ledger", headers=headers)
    ).json()["data"]
    allocs = (
        await client.get(f"/api/v1/payments/budgets/{budget_id}/allocations", headers=headers)
    ).json()["data"]
    return {
        "status": inv["status"],
        "invoice_paid": Decimal(str(inv["total_paid"])),
        "billing_paid": Decimal(str(billing["total_paid"])),
        "ledger_paid": Decimal(str(ledger["total_paid"])),
        "on_account": Decimal(str(ledger["on_account_balance"])),
        "quote_collected": sum((Decimal(str(a["amount"])) for a in allocs), Decimal("0")),
    }


@pytest.mark.asyncio
async def test_three_collect_surfaces_converge(
    client: AsyncClient,
    auth_headers: dict,
    test_clinic: Clinic,
    test_patient: Patient,
    db_session: AsyncSession,
) -> None:
    """The exact reproduction from #178, now asserting convergence."""
    budget = await _budget(db_session, test_clinic, test_patient, "300.00")
    inv = await _draft_invoice(db_session, test_clinic, test_patient, "300.00", budget)
    await _issue(client, auth_headers, inv.id)
    pid, bid = test_patient.id, budget.id

    # 1) Collect on the invoice → also visible on the quote.
    await _pay_invoice(client, auth_headers, inv.id, "100.00")
    s = await _surfaces(client, auth_headers, inv.id, pid, bid)
    assert s == {
        "status": "partial",
        "invoice_paid": Decimal("100.00"),
        "billing_paid": Decimal("100.00"),
        "ledger_paid": Decimal("100.00"),
        "on_account": Decimal("0"),
        "quote_collected": Decimal("100.00"),
    }

    # 2) Anticipo on account from /payments → patient credit only (by design).
    await _pay(client, auth_headers, pid, [{"target_type": "on_account", "amount": "100.00"}])
    s = await _surfaces(client, auth_headers, inv.id, pid, bid)
    assert (s["invoice_paid"], s["ledger_paid"], s["on_account"], s["quote_collected"]) == (
        Decimal("100.00"),
        Decimal("200.00"),
        Decimal("100.00"),
        Decimal("100.00"),
    )

    # 3) Collect on the quote → lands on the invoice too.
    quote_payment = await _pay(
        client,
        auth_headers,
        pid,
        [{"target_type": "budget", "target_id": str(bid), "amount": "100.00"}],
    )
    s = await _surfaces(client, auth_headers, inv.id, pid, bid)
    assert s == {
        "status": "partial",
        "invoice_paid": Decimal("200.00"),
        "billing_paid": Decimal("200.00"),
        "ledger_paid": Decimal("300.00"),
        "on_account": Decimal("100.00"),
        "quote_collected": Decimal("200.00"),
    }

    # 4) Refund the quote payment fully → invoice + billing tab follow, in-tx.
    r = await client.post(
        f"/api/v1/payments/{quote_payment['id']}/refunds",
        json={"amount": "100.00", "method": "cash", "reason_code": "other"},
        headers=auth_headers,
    )
    assert r.status_code == 201, r.text
    s = await _surfaces(client, auth_headers, inv.id, pid, bid)
    assert (s["status"], s["invoice_paid"], s["billing_paid"]) == (
        "partial",
        Decimal("100.00"),
        Decimal("100.00"),
    )


@pytest.mark.asyncio
async def test_anticipo_then_issue_marks_invoice_paid(
    client: AsyncClient,
    auth_headers: dict,
    test_clinic: Clinic,
    test_patient: Patient,
    db_session: AsyncSession,
) -> None:
    """Quote collected first, invoice issued later → invoice is born paid."""
    budget = await _budget(db_session, test_clinic, test_patient, "200.00")
    await _pay(
        client,
        auth_headers,
        test_patient.id,
        [{"target_type": "budget", "target_id": str(budget.id), "amount": "200.00"}],
    )
    inv = await _draft_invoice(db_session, test_clinic, test_patient, "200.00", budget)
    await _issue(client, auth_headers, inv.id)

    s = await _surfaces(client, auth_headers, inv.id, test_patient.id, budget.id)
    assert (s["status"], s["invoice_paid"]) == ("paid", Decimal("200.00"))


@pytest.mark.asyncio
async def test_reallocate_to_on_account_unlinks_and_back_relinks(
    client: AsyncClient,
    auth_headers: dict,
    test_clinic: Clinic,
    test_patient: Patient,
    db_session: AsyncSession,
) -> None:
    budget = await _budget(db_session, test_clinic, test_patient, "100.00")
    inv = await _draft_invoice(db_session, test_clinic, test_patient, "100.00", budget)
    await _issue(client, auth_headers, inv.id)
    payment = await _pay(
        client,
        auth_headers,
        test_patient.id,
        [{"target_type": "budget", "target_id": str(budget.id), "amount": "100.00"}],
    )
    s = await _surfaces(client, auth_headers, inv.id, test_patient.id, budget.id)
    assert (s["status"], s["invoice_paid"]) == ("paid", Decimal("100.00"))

    r = await client.post(
        f"/api/v1/payments/{payment['id']}/reallocate",
        json={"allocations": [{"target_type": "on_account", "amount": "100.00"}]},
        headers=auth_headers,
    )
    assert r.status_code == 200, r.text
    s = await _surfaces(client, auth_headers, inv.id, test_patient.id, budget.id)
    assert (s["status"], s["invoice_paid"], s["on_account"]) == (
        "issued",
        Decimal("0.00"),
        Decimal("100.00"),
    )

    # "Asignar a presupuesto" from the ledger = reallocate back → re-imputed.
    r = await client.post(
        f"/api/v1/payments/{payment['id']}/reallocate",
        json={
            "allocations": [
                {"target_type": "budget", "target_id": str(budget.id), "amount": "100.00"}
            ]
        },
        headers=auth_headers,
    )
    assert r.status_code == 200, r.text
    s = await _surfaces(client, auth_headers, inv.id, test_patient.id, budget.id)
    assert (s["status"], s["invoice_paid"]) == ("paid", Decimal("100.00"))


@pytest.mark.asyncio
async def test_two_invoices_same_budget_prefer_then_fifo(
    client: AsyncClient,
    auth_headers: dict,
    test_clinic: Clinic,
    test_patient: Patient,
    db_session: AsyncSession,
) -> None:
    budget = await _budget(db_session, test_clinic, test_patient, "300.00")
    older = await _draft_invoice(db_session, test_clinic, test_patient, "100.00", budget)
    newer = await _draft_invoice(db_session, test_clinic, test_patient, "200.00", budget)
    await _issue(client, auth_headers, older.id)
    await _issue(client, auth_headers, newer.id)

    # Collecting on the newer invoice must land there, not FIFO on the older.
    await _pay_invoice(client, auth_headers, newer.id, "150.00")
    s_new = await _surfaces(client, auth_headers, newer.id, test_patient.id, budget.id)
    s_old = await _surfaces(client, auth_headers, older.id, test_patient.id, budget.id)
    assert (s_new["invoice_paid"], s_old["invoice_paid"]) == (Decimal("150.00"), Decimal("0.00"))

    # Quote collect for the rest → FIFO: older first (100), remainder to newer (50).
    await _pay(
        client,
        auth_headers,
        test_patient.id,
        [{"target_type": "budget", "target_id": str(budget.id), "amount": "150.00"}],
    )
    s_new = await _surfaces(client, auth_headers, newer.id, test_patient.id, budget.id)
    s_old = await _surfaces(client, auth_headers, older.id, test_patient.id, budget.id)
    assert (s_old["status"], s_old["invoice_paid"]) == ("paid", Decimal("100.00"))
    assert (s_new["status"], s_new["invoice_paid"]) == ("paid", Decimal("200.00"))
    assert s_new["quote_collected"] == Decimal("300.00")

    links = (
        (
            await db_session.execute(
                select(InvoicePayment).where(InvoicePayment.clinic_id == test_clinic.id)
            )
        )
        .scalars()
        .all()
    )
    assert sum(link.amount for link in links) == Decimal("300.00")


@pytest.mark.asyncio
async def test_manual_invoice_still_collects_on_account(
    client: AsyncClient,
    auth_headers: dict,
    test_clinic: Clinic,
    test_patient: Patient,
    db_session: AsyncSession,
) -> None:
    inv = await _draft_invoice(db_session, test_clinic, test_patient, "50.00", None)
    await _issue(client, auth_headers, inv.id)
    await _pay_invoice(client, auth_headers, inv.id, "50.00")
    invj = (await client.get(f"/api/v1/billing/invoices/{inv.id}", headers=auth_headers)).json()[
        "data"
    ]
    assert (invj["status"], Decimal(str(invj["total_paid"]))) == ("paid", Decimal("50.00"))


@pytest.mark.asyncio
async def test_invoice_payments_list_embeds_payment(
    client: AsyncClient,
    auth_headers: dict,
    test_clinic: Clinic,
    test_patient: Patient,
    db_session: AsyncSession,
) -> None:
    """GET /invoices/{id}/payments returns link rows with the Payment embedded.

    Invoice-side views render date/method from it (issue #184).
    """
    inv = await _draft_invoice(db_session, test_clinic, test_patient, "50.00", None)
    await _issue(client, auth_headers, inv.id)
    link = await _pay_invoice(client, auth_headers, inv.id, "50.00")

    r = await client.get(f"/api/v1/billing/invoices/{inv.id}/payments", headers=auth_headers)
    assert r.status_code == 200, r.text
    rows = r.json()["data"]
    assert [row["id"] for row in rows] == [link["id"]]
    assert Decimal(str(rows[0]["amount"])) == Decimal("50.00")
    payment = rows[0]["payment"]
    assert payment["id"] == link["payment_id"]
    assert (payment["method"], payment["payment_date"]) == ("cash", TODAY)
    assert Decimal(str(payment["net_amount"])) == Decimal("50.00")


@pytest.mark.asyncio
async def test_budget_collection_skips_historical_invoice(
    client: AsyncClient,
    auth_headers: dict,
    test_clinic: Clinic,
    test_patient: Patient,
    db_session: AsyncSession,
) -> None:
    budget = await _budget(db_session, test_clinic, test_patient, "300.00")
    historical = await _draft_invoice(db_session, test_clinic, test_patient, "120.00", budget)
    historical.is_historical = True
    historical.status = "issued"
    historical.issue_date = date(2020, 1, 1)
    await db_session.commit()
    current = await _draft_invoice(db_session, test_clinic, test_patient, "180.00", budget)
    await _issue(client, auth_headers, current.id)

    await _pay(
        client,
        auth_headers,
        test_patient.id,
        [{"target_type": "budget", "target_id": str(budget.id), "amount": "100.00"}],
    )

    links = (
        await db_session.execute(select(InvoicePayment.invoice_id, InvoicePayment.amount))
    ).all()
    assert links == [(current.id, Decimal("100.00"))]
    await db_session.refresh(historical)
    assert historical.status == "issued"
