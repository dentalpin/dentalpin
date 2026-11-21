"""Two simultaneous punches of the same kind store one.

``clock`` rejects a punch that repeats its neighbour's kind, but it read the
neighbours without a lock. A double tap on "Clock in" sent two requests that
both saw no previous punch and both inserted ``in``: the member had two
consecutive clock-ins, which the alternation rule exists to prevent, and the
daily report paired only the second one. Production hands each request its
own session, so these tests do too.
"""

from __future__ import annotations

import asyncio
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic, ClinicMembership, User
from app.database import async_session_maker
from app.modules.staff_attendance.models import AttendanceEvent
from app.modules.staff_attendance.service import AttendanceService


async def _punch(clinic_id, user_id, kind: str) -> int:
    async with async_session_maker() as session:
        try:
            await AttendanceService.clock(session, clinic_id, user_id, kind, created_by=user_id)
            await session.commit()
        except HTTPException as exc:
            await session.rollback()
            return exc.status_code
        return 201


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["in", "out"])
async def test_a_double_tap_stores_one_punch(
    db_session: AsyncSession, test_clinic: Clinic, kind: str
):
    user = User(email=f"s-{uuid4().hex[:6]}@t.c", password_hash="x", first_name="S", last_name="T")
    db_session.add(user)
    await db_session.flush()
    db_session.add(ClinicMembership(user_id=user.id, clinic_id=test_clinic.id, role="assistant"))
    await db_session.commit()
    if kind == "out":
        await AttendanceService.clock(db_session, test_clinic.id, user.id, "in", created_by=user.id)
        await db_session.commit()

    outcomes = await asyncio.gather(
        _punch(test_clinic.id, user.id, kind), _punch(test_clinic.id, user.id, kind)
    )

    assert sorted(outcomes) == [201, 409]
    async with async_session_maker() as fresh:
        kinds = (
            await fresh.scalars(
                select(AttendanceEvent.kind)
                .where(AttendanceEvent.user_id == user.id)
                .order_by(AttendanceEvent.at)
            )
        ).all()
    assert kinds == (["in"] if kind == "in" else ["in", "out"])
