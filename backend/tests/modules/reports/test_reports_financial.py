"""Financial family: aging buckets + issued trend (invoice axis only)."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic, User
from app.modules.billing.models import Invoice
from app.modules.patients.models import Patient
from app.modules.reports.services import FinancialReportService


async def _staff_id(db: AsyncSession) -> object:
    from uuid import uuid4

    user = User(
        email=f"fin-{uuid4().hex[:8]}@test.clinic",
        password_hash="not-a-real-hash",
        first_name="Fin",
        last_name="Staff",
    )
    db.add(user)
    await db.commit()
    return user.id


async def _invoice(
    db: AsyncSession,
    clinic_id,
    patient_id,
    *,
    total: str = "100",
    status: str = "issued",
    due_in_days: int | None = -10,
    issue: date | None = None,
    deleted: bool = False,
) -> Invoice:
    from datetime import UTC, datetime

    row = Invoice(
        clinic_id=clinic_id,
        patient_id=patient_id,
        created_by=await _staff_id(db),
        status=status,
        total=Decimal(total),
        issue_date=issue or date.today(),
        due_date=(date.today() + timedelta(days=due_in_days)) if due_in_days is not None else None,
        deleted_at=datetime.now(UTC) if deleted else None,
    )
    db.add(row)
    await db.commit()
    return row


def _by_label(buckets: list[dict]) -> dict[str, dict]:
    return {b["label"]: b for b in buckets}


@pytest.mark.asyncio
async def test_aging_buckets(db_session: AsyncSession, test_clinic: Clinic, test_patient: Patient):
    clinic_id = test_clinic.id
    patient_id = test_patient.id
    # 0-30: due in 5 days (not yet due still counts as current outstanding).
    await _invoice(db_session, clinic_id, patient_id, total="100", due_in_days=5)
    # 31-60: 40 days overdue.
    await _invoice(db_session, clinic_id, patient_id, total="200", due_in_days=-40)
    # 90+: 100 days overdue, partial status still counts.
    await _invoice(
        db_session, clinic_id, patient_id, total="400", status="partial", due_in_days=-100
    )
    # No due date counts as current.
    await _invoice(db_session, clinic_id, patient_id, total="50", due_in_days=None)
    # Excluded: draft, paid, cancelled, voided, soft-deleted.
    await _invoice(db_session, clinic_id, patient_id, total="999", status="draft", due_in_days=-50)
    await _invoice(db_session, clinic_id, patient_id, total="999", status="paid", due_in_days=-50)
    await _invoice(
        db_session, clinic_id, patient_id, total="999", status="cancelled", due_in_days=-50
    )
    await _invoice(db_session, clinic_id, patient_id, total="999", status="voided", due_in_days=-50)
    await _invoice(db_session, clinic_id, patient_id, total="999", due_in_days=-50, deleted=True)

    buckets = _by_label(await FinancialReportService.aging_buckets(db_session, clinic_id))
    assert buckets["0-30"]["total"] == Decimal("150")
    assert buckets["0-30"]["count"] == 2
    assert buckets["31-60"]["total"] == Decimal("200")
    assert buckets["31-60"]["count"] == 1
    assert buckets["61-90"]["total"] == Decimal("0")
    assert buckets["61-90"]["count"] == 0
    assert buckets["90+"]["total"] == Decimal("400")
    assert buckets["90+"]["count"] == 1
    assert buckets["90+"]["patient_count"] == 1


@pytest.mark.asyncio
async def test_issued_trend(db_session: AsyncSession, test_clinic: Clinic, test_patient: Patient):
    clinic_id = test_clinic.id
    patient_id = test_patient.id
    jan = date(2026, 1, 15)
    feb = date(2026, 2, 10)
    await _invoice(db_session, clinic_id, patient_id, total="100", issue=jan)
    await _invoice(db_session, clinic_id, patient_id, total="300", issue=jan)
    await _invoice(db_session, clinic_id, patient_id, total="50", issue=feb)
    await _invoice(db_session, clinic_id, patient_id, total="999", status="draft", issue=jan)
    await _invoice(db_session, clinic_id, patient_id, total="999", status="cancelled", issue=feb)

    points = await FinancialReportService.issued_trend(
        db_session, clinic_id, date(2026, 1, 1), date(2026, 2, 28)
    )
    by_month = {p["month"]: p for p in points}
    assert set(by_month) == {"2026-01", "2026-02"}
    assert by_month["2026-01"]["total"] == Decimal("400")
    assert by_month["2026-01"]["count"] == 2
    assert by_month["2026-02"]["total"] == Decimal("50")
    assert by_month["2026-02"]["count"] == 1
