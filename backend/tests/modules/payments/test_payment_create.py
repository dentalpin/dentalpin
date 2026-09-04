"""Smoke tests for the payments module (issue #53)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic, ClinicMembership
from app.modules.patients.models import Patient


async def _setup_clinic(db: AsyncSession, auth_headers: dict, client: AsyncClient) -> dict:
    me = await client.get("/api/v1/auth/me", headers=auth_headers)
    user_id = me.json()["data"]["user"]["id"]

    clinic = Clinic(
        id=uuid4(),
        name="Test Clinic",
        tax_id="A28000000",
        timezone="Europe/Madrid",
        currency="EUR",
        settings={},
    )
    db.add(clinic)
    await db.flush()
    db.add(ClinicMembership(id=uuid4(), clinic_id=clinic.id, user_id=user_id, role="admin"))

    patient = Patient(
        id=uuid4(),
        clinic_id=clinic.id,
        first_name="Ana",
        last_name="García",
    )
    db.add(patient)
    await db.commit()

    return {
        "clinic_id": str(clinic.id),
        "user_id": user_id,
        "patient_id": str(patient.id),
    }


@pytest.mark.asyncio
async def test_create_payment_with_on_account_allocation(
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
):
    setup = await _setup_clinic(db_session, auth_headers, client)

    body = {
        "patient_id": setup["patient_id"],
        "amount": "150.00",
        "method": "cash",
        "payment_date": date.today().isoformat(),
        "allocations": [{"target_type": "on_account", "amount": "150.00"}],
    }
    resp = await client.post(
        f"/api/v1/payments?clinic_id={setup['clinic_id']}",
        headers=auth_headers,
        json=body,
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()["data"]
    assert Decimal(data["amount"]) == Decimal("150.00")
    assert data["currency"] == "EUR"
    assert len(data["allocations"]) == 1
    assert data["allocations"][0]["target_type"] == "on_account"
    assert Decimal(data["net_amount"]) == Decimal("150.00")


@pytest.mark.asyncio
async def test_allocation_sum_invariant_enforced(
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
):
    setup = await _setup_clinic(db_session, auth_headers, client)

    body = {
        "patient_id": setup["patient_id"],
        "amount": "100.00",
        "method": "cash",
        "payment_date": date.today().isoformat(),
        "allocations": [
            {"target_type": "on_account", "amount": "60.00"}
            # Missing 40 → must fail at the schema layer.
        ],
    }
    resp = await client.post(
        f"/api/v1/payments?clinic_id={setup['clinic_id']}",
        headers=auth_headers,
        json=body,
    )
    assert resp.status_code == 422, resp.text


@pytest.mark.asyncio
async def test_refund_partial_then_full(
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
):
    setup = await _setup_clinic(db_session, auth_headers, client)

    create_resp = await client.post(
        f"/api/v1/payments?clinic_id={setup['clinic_id']}",
        headers=auth_headers,
        json={
            "patient_id": setup["patient_id"],
            "amount": "200.00",
            "method": "card",
            "payment_date": date.today().isoformat(),
            "allocations": [{"target_type": "on_account", "amount": "200.00"}],
        },
    )
    payment_id = create_resp.json()["data"]["id"]

    # First refund — partial
    r1 = await client.post(
        f"/api/v1/payments/{payment_id}/refunds?clinic_id={setup['clinic_id']}",
        headers=auth_headers,
        json={
            "amount": "50.00",
            "method": "card",
            "reason_code": "overpaid",
        },
    )
    assert r1.status_code == 201, r1.text

    # Second refund — would exceed cap
    r2 = await client.post(
        f"/api/v1/payments/{payment_id}/refunds?clinic_id={setup['clinic_id']}",
        headers=auth_headers,
        json={
            "amount": "200.00",
            "method": "card",
            "reason_code": "duplicate",
        },
    )
    assert r2.status_code == 422, r2.text


@pytest.mark.asyncio
async def test_patient_ledger_endpoint(
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
):
    setup = await _setup_clinic(db_session, auth_headers, client)

    await client.post(
        f"/api/v1/payments?clinic_id={setup['clinic_id']}",
        headers=auth_headers,
        json={
            "patient_id": setup["patient_id"],
            "amount": "300.00",
            "method": "bank_transfer",
            "payment_date": date.today().isoformat(),
            "allocations": [{"target_type": "on_account", "amount": "300.00"}],
        },
    )

    resp = await client.get(
        f"/api/v1/payments/patients/{setup['patient_id']}/ledger?clinic_id={setup['clinic_id']}",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    ledger = resp.json()["data"]
    assert Decimal(ledger["total_paid"]) == Decimal("300.00")
    # No earned entries seeded, so the entire amount sits as patient credit.
    assert Decimal(ledger["patient_credit"]) == Decimal("300.00")
    assert Decimal(ledger["clinic_receivable"]) == Decimal("0.00")


@pytest.mark.asyncio
async def test_idempotency_key_returns_existing_payment(
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
):
    """#365: retrying record_payment with the same key never double-records."""
    setup = await _setup_clinic(db_session, auth_headers, client)
    body = {
        "patient_id": setup["patient_id"],
        "amount": "80.00",
        "method": "card",
        "payment_date": date.today().isoformat(),
        "allocations": [{"target_type": "on_account", "amount": "80.00"}],
        "idempotency_key": "gw-txn-0001",
    }
    first = await client.post(
        f"/api/v1/payments?clinic_id={setup['clinic_id']}", headers=auth_headers, json=body
    )
    assert first.status_code == 201, first.text
    second = await client.post(
        f"/api/v1/payments?clinic_id={setup['clinic_id']}", headers=auth_headers, json=body
    )
    assert second.status_code == 201, second.text
    assert second.json()["data"]["id"] == first.json()["data"]["id"]

    listing = await client.get(
        f"/api/v1/payments?clinic_id={setup['clinic_id']}", headers=auth_headers
    )
    assert listing.json()["total"] == 1

    # A different key is a different payment.
    other = await client.post(
        f"/api/v1/payments?clinic_id={setup['clinic_id']}",
        headers=auth_headers,
        json={**body, "idempotency_key": "gw-txn-0002"},
    )
    assert other.json()["data"]["id"] != first.json()["data"]["id"]


@pytest.mark.asyncio
async def test_india_methods_accepted(
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
):
    setup = await _setup_clinic(db_session, auth_headers, client)
    for method in ("upi", "netbanking"):
        resp = await client.post(
            f"/api/v1/payments?clinic_id={setup['clinic_id']}",
            headers=auth_headers,
            json={
                "patient_id": setup["patient_id"],
                "amount": "10.00",
                "method": method,
                "payment_date": date.today().isoformat(),
                "allocations": [{"target_type": "on_account", "amount": "10.00"}],
            },
        )
        assert resp.status_code == 201, resp.text
        assert resp.json()["data"]["method"] == method


@pytest.mark.asyncio
async def test_idempotency_key_concurrent_race_adopts_winner(
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    monkeypatch,
):
    """Two concurrent record_payment calls with one key: the loser of the
    unique index must return the winner's payment, not 500 (#365 follow-up)."""
    from sqlalchemy import text

    from app.modules.payments import workflow as wf

    setup = await _setup_clinic(db_session, auth_headers, client)
    original = wf._validate_allocations_for_clinic

    async def validate_then_race(db, clinic_id, allocations):
        # Runs after the pre-check SELECT and before the INSERT — inject the
        # concurrent writer's row here so our INSERT collides.
        await original(db, clinic_id, allocations)
        await db.execute(
            text(
                "INSERT INTO payments (id, clinic_id, patient_id, amount, currency, method, "
                " payment_date, recorded_by, idempotency_key, created_at, updated_at) "
                "VALUES (gen_random_uuid(), :clinic, :patient, 80.00, 'EUR', 'card', "
                " CURRENT_DATE, :user, 'gw-race-1', now(), now())"
            ),
            {
                "clinic": setup["clinic_id"],
                "patient": setup["patient_id"],
                "user": setup["user_id"],
            },
        )

    monkeypatch.setattr(wf, "_validate_allocations_for_clinic", validate_then_race)
    resp = await client.post(
        f"/api/v1/payments?clinic_id={setup['clinic_id']}",
        headers=auth_headers,
        json={
            "patient_id": setup["patient_id"],
            "amount": "80.00",
            "method": "card",
            "payment_date": date.today().isoformat(),
            "allocations": [{"target_type": "on_account", "amount": "80.00"}],
            "idempotency_key": "gw-race-1",
        },
    )
    assert resp.status_code == 201, resp.text
    listing = await client.get(
        f"/api/v1/payments?clinic_id={setup['clinic_id']}", headers=auth_headers
    )
    assert listing.json()["total"] == 1
