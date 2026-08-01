"""Tests for the per-session earned ledger + FIFO pending-charges endpoint.

Covers the multi-session billing slice that lands in payments:
- The earned ledger is now keyed on ``(treatment_id, source_session_id)``,
  so multi-session treatments produce one row per session.
- ``GET /payments/patients/{id}/pending-charges`` returns earned
  entries that net payments haven't covered yet (FIFO virtual).

Earned rows are inserted directly via ORM to avoid spinning a
second async session inside the test's event loop (the production
handler opens its own ``async_session_maker``, which conflicts with
the test fixture). The contract verified here is on the SQL-level
read path consumed by reception.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic, ClinicMembership
from app.modules.patients.models import Patient
from app.modules.payments.models import PatientEarnedEntry


async def _setup_clinic(db: AsyncSession, auth_headers: dict, client: AsyncClient) -> dict:
    me = await client.get("/api/v1/auth/me", headers=auth_headers)
    user_id = me.json()["data"]["user"]["id"]
    clinic = Clinic(
        id=uuid4(),
        name="MS Clinic",
        tax_id="A28000777",
        timezone="Europe/Madrid",
        currency="EUR",
        settings={},
    )
    db.add(clinic)
    await db.flush()
    db.add(ClinicMembership(id=uuid4(), clinic_id=clinic.id, user_id=user_id, role="admin"))
    patient = Patient(id=uuid4(), clinic_id=clinic.id, first_name="Eva", last_name="MS")
    db.add(patient)
    await db.commit()
    return {"clinic_id": str(clinic.id), "patient_id": str(patient.id)}


async def _add_earned(
    db: AsyncSession,
    *,
    clinic_id: str,
    patient_id: str,
    treatment_id: str,
    session_id: str | None,
    amount: str,
    description: str,
    performed_at: datetime,
) -> None:
    db.add(
        PatientEarnedEntry(
            id=uuid4(),
            clinic_id=UUID(clinic_id),
            patient_id=UUID(patient_id),
            treatment_id=UUID(treatment_id),
            source_session_id=UUID(session_id) if session_id else None,
            description=description,
            amount=Decimal(amount),
            performed_at=performed_at,
            source_event="treatment_plan.item_session_completed",
        )
    )
    await db.commit()


@pytest.mark.asyncio
async def test_unique_constraint_per_treatment_session(
    db_session: AsyncSession, auth_headers: dict, client: AsyncClient
):
    """Same (treatment_id, source_session_id) twice is rejected; different sessions coexist."""
    ctx = await _setup_clinic(db_session, auth_headers, client)
    treatment_id = str(uuid4())
    s1, s2 = str(uuid4()), str(uuid4())

    await _add_earned(
        db_session,
        clinic_id=ctx["clinic_id"],
        patient_id=ctx["patient_id"],
        treatment_id=treatment_id,
        session_id=s1,
        amount="200.00",
        description="Toma de medidas",
        performed_at=datetime(2026, 5, 1, 10, 0, tzinfo=UTC),
    )
    await _add_earned(
        db_session,
        clinic_id=ctx["clinic_id"],
        patient_id=ctx["patient_id"],
        treatment_id=treatment_id,
        session_id=s2,
        amount="600.00",
        description="Colocación",
        performed_at=datetime(2026, 5, 2, 10, 0, tzinfo=UTC),
    )

    from sqlalchemy import select

    rows = (
        (
            await db_session.execute(
                select(PatientEarnedEntry).where(PatientEarnedEntry.treatment_id == treatment_id)
            )
        )
        .scalars()
        .all()
    )
    assert len(rows) == 2
    assert sum(r.amount for r in rows) == Decimal("800.00")

    # Same (treatment, session) twice → IntegrityError
    from sqlalchemy.exc import IntegrityError

    with pytest.raises(IntegrityError):
        await _add_earned(
            db_session,
            clinic_id=ctx["clinic_id"],
            patient_id=ctx["patient_id"],
            treatment_id=treatment_id,
            session_id=s1,
            amount="200.00",
            description="dup",
            performed_at=datetime.now(UTC),
        )


@pytest.mark.asyncio
async def test_null_session_row_is_unique_per_treatment(
    db_session: AsyncSession, auth_headers: dict, client: AsyncClient
):
    """Regression: two NULL-session rows for one treatment must be rejected.

    A plain unique constraint treats NULLs as distinct, so replayed
    ``odontogram.treatment.performed`` events used to insert freely —
    the partial index ``uq_earned_treatment_null_session`` closes that.
    """
    from sqlalchemy.exc import IntegrityError

    ctx = await _setup_clinic(db_session, auth_headers, client)
    treatment_id = str(uuid4())

    await _add_earned(
        db_session,
        clinic_id=ctx["clinic_id"],
        patient_id=ctx["patient_id"],
        treatment_id=treatment_id,
        session_id=None,
        amount="800.00",
        description="Corona",
        performed_at=datetime(2026, 5, 1, 10, 0, tzinfo=UTC),
    )
    with pytest.raises(IntegrityError):
        await _add_earned(
            db_session,
            clinic_id=ctx["clinic_id"],
            patient_id=ctx["patient_id"],
            treatment_id=treatment_id,
            session_id=None,
            amount="800.00",
            description="Corona replay",
            performed_at=datetime(2026, 5, 1, 10, 0, tzinfo=UTC),
        )


@pytest.mark.asyncio
async def test_pending_charges_fifo_partial(
    db_session: AsyncSession, auth_headers: dict, client: AsyncClient
):
    """Net paid covers earned entries in chronological order; remainder is pending."""
    ctx = await _setup_clinic(db_session, auth_headers, client)
    treatment_id = str(uuid4())
    await _add_earned(
        db_session,
        clinic_id=ctx["clinic_id"],
        patient_id=ctx["patient_id"],
        treatment_id=treatment_id,
        session_id=str(uuid4()),
        amount="200.00",
        description="S1",
        performed_at=datetime(2026, 5, 1, 10, 0, tzinfo=UTC),
    )
    await _add_earned(
        db_session,
        clinic_id=ctx["clinic_id"],
        patient_id=ctx["patient_id"],
        treatment_id=treatment_id,
        session_id=str(uuid4()),
        amount="600.00",
        description="S2",
        performed_at=datetime(2026, 5, 2, 10, 0, tzinfo=UTC),
    )

    # No payment yet → both sessions pending
    r = await client.get(
        f"/api/v1/payments/patients/{ctx['patient_id']}/pending-charges",
        headers=auth_headers,
    )
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert len(data) == 2
    assert [Decimal(d["amount"]) for d in data] == [Decimal("200.00"), Decimal("600.00")]

    # Pay 250€ → S1 covered, S2 has 550€ pending
    pay = await client.post(
        f"/api/v1/payments?clinic_id={ctx['clinic_id']}",
        headers=auth_headers,
        json={
            "patient_id": ctx["patient_id"],
            "amount": "250.00",
            "method": "cash",
            "payment_date": "2026-05-03",
            "allocations": [{"target_type": "on_account", "amount": "250.00"}],
        },
    )
    assert pay.status_code == 201, pay.text

    r = await client.get(
        f"/api/v1/payments/patients/{ctx['patient_id']}/pending-charges",
        headers=auth_headers,
    )
    pending = r.json()["data"]
    assert len(pending) == 1
    assert Decimal(pending[0]["amount"]) == Decimal("550.00")
    assert pending[0]["description"] == "S2"


@pytest.mark.asyncio
async def test_pending_charges_empty_when_fully_paid(
    db_session: AsyncSession, auth_headers: dict, client: AsyncClient
):
    ctx = await _setup_clinic(db_session, auth_headers, client)
    treatment_id = str(uuid4())
    await _add_earned(
        db_session,
        clinic_id=ctx["clinic_id"],
        patient_id=ctx["patient_id"],
        treatment_id=treatment_id,
        session_id=str(uuid4()),
        amount="300.00",
        description="Only",
        performed_at=datetime.now(UTC),
    )
    pay = await client.post(
        f"/api/v1/payments?clinic_id={ctx['clinic_id']}",
        headers=auth_headers,
        json={
            "patient_id": ctx["patient_id"],
            "amount": "300.00",
            "method": "cash",
            "payment_date": "2026-05-04",
            "allocations": [{"target_type": "on_account", "amount": "300.00"}],
        },
    )
    assert pay.status_code == 201
    r = await client.get(
        f"/api/v1/payments/patients/{ctx['patient_id']}/pending-charges",
        headers=auth_headers,
    )
    assert r.json()["data"] == []
