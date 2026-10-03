"""Duplicate clinic_memberships rows must not break membership checks.

``clinic_memberships`` has no unique ``(clinic_id, user_id)`` constraint,
so a duplicated row used to make every ``scalar_one_or_none()`` existence
check raise ``MultipleResultsFound`` and 500 the request — the bug
reported for orthodontics in #590. PR #598 fixed the orthodontics
checks; these tests pin the same tolerance for the remaining existence
checks (treatment_plan, schedules professional hours, agenda), which
share the identical query shape.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic, ClinicMembership, User
from app.core.auth.service import hash_password
from app.modules.agenda.service import AppointmentService
from app.modules.schedules.services.professional_hours import ProfessionalHoursService
from app.modules.treatment_plan.service import _validate_professional_in_clinic


async def _professional_with_duplicate_membership(db_session: AsyncSession, clinic_id) -> User:
    user = User(
        id=uuid4(),
        email=f"dup-{uuid4().hex[:6]}@t.c",
        password_hash=hash_password("TestPass1234"),
        first_name="Dup",
        last_name="Member",
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()
    for _ in range(2):
        db_session.add(
            ClinicMembership(id=uuid4(), user_id=user.id, clinic_id=clinic_id, role="dentist")
        )
    await db_session.commit()
    return user


@pytest.mark.asyncio
async def test_treatment_plan_professional_check_tolerates_duplicate_membership(
    db_session: AsyncSession, test_clinic: Clinic
):
    doc = await _professional_with_duplicate_membership(db_session, test_clinic.id)
    # Must not raise MultipleResultsFound.
    await _validate_professional_in_clinic(db_session, test_clinic.id, doc.id)


@pytest.mark.asyncio
async def test_professional_hours_is_professional_tolerates_duplicate_membership(
    db_session: AsyncSession, test_clinic: Clinic
):
    doc = await _professional_with_duplicate_membership(db_session, test_clinic.id)
    assert await ProfessionalHoursService.is_professional(db_session, test_clinic.id, doc.id)


@pytest.mark.asyncio
async def test_agenda_professional_access_tolerates_duplicate_membership(
    db_session: AsyncSession, test_clinic: Clinic
):
    doc = await _professional_with_duplicate_membership(db_session, test_clinic.id)
    assert await AppointmentService.validate_professional_access(db_session, test_clinic.id, doc.id)


@pytest.mark.asyncio
async def test_membership_checks_still_reject_non_members(
    db_session: AsyncSession, test_clinic: Clinic
):
    stranger = uuid4()
    with pytest.raises(ValueError):
        await _validate_professional_in_clinic(db_session, test_clinic.id, stranger)
    assert not await ProfessionalHoursService.is_professional(db_session, test_clinic.id, stranger)
    assert not await AppointmentService.validate_professional_access(
        db_session, test_clinic.id, stranger
    )
