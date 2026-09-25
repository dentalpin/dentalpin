"""PrescriptionsModule.uninstall() retention guard — direct unit test.

The guard must refuse while ANY issued prescription exists, including
ones later cancelled (issued_at IS NOT NULL covers both) — a cancelled
record is still a clinical artifact. Pure drafts never block.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic
from app.modules.patients.models import Patient
from app.modules.prescriptions import PrescriptionsModule
from app.modules.prescriptions.service import PrescriptionService


@dataclass
class _FakeLogger:
    def info(self, *_args, **_kwargs):
        pass


@dataclass
class _FakeCtx:
    db: AsyncSession
    logger: _FakeLogger


async def _cancelled_after_issue(db_session, clinic_id) -> None:
    from uuid import uuid4

    from app.core.auth.models import User
    from app.core.auth.service import hash_password

    user = User(
        id=uuid4(),
        email=f"rxg-{uuid4().hex[:6]}@t.c",
        password_hash=hash_password("TestPass1234"),
        first_name="Doc",
        last_name="Tor",
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()
    patient = Patient(clinic_id=clinic_id, first_name="Rx", last_name="Taker")
    db_session.add(patient)
    await db_session.commit()
    row = await PrescriptionService.create_draft(
        db_session,
        clinic_id,
        user.id,
        patient.id,
        notes=None,
        locale="es",
        items=[{"medication_name": "Amoxicilina"}],
    )
    await PrescriptionService.issue(db_session, clinic_id, row.id, user.id)
    await PrescriptionService.cancel(db_session, clinic_id, row.id)
    await db_session.commit()


@pytest.mark.asyncio
async def test_uninstall_refuses_cancelled_after_issued(
    db_session: AsyncSession, test_clinic: Clinic
):
    await _cancelled_after_issue(db_session, test_clinic.id)
    with pytest.raises(RuntimeError):
        await PrescriptionsModule().uninstall(_FakeCtx(db_session, _FakeLogger()))


@pytest.mark.asyncio
async def test_uninstall_allows_pure_drafts(db_session: AsyncSession, test_clinic: Clinic):
    from uuid import uuid4

    from app.core.auth.models import User
    from app.core.auth.service import hash_password

    user = User(
        id=uuid4(),
        email=f"rxd-{uuid4().hex[:6]}@t.c",
        password_hash=hash_password("TestPass1234"),
        first_name="Doc",
        last_name="Tor",
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()
    patient = Patient(clinic_id=test_clinic.id, first_name="Rx", last_name="Taker")
    db_session.add(patient)
    await db_session.commit()
    await PrescriptionService.create_draft(
        db_session,
        test_clinic.id,
        user.id,
        patient.id,
        notes=None,
        locale="es",
        items=[],
    )
    await db_session.commit()
    await PrescriptionsModule().uninstall(_FakeCtx(db_session, _FakeLogger()))
