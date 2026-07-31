"""Professional hours service — weekly templates + date-range overrides."""

from __future__ import annotations

from datetime import date
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.auth.models import ClinicMembership

from ..models import (
    ProfessionalOverride,
    ProfessionalWeeklySchedule,
    ScheduleShift,
)


class ProfessionalHoursService:
    @staticmethod
    async def is_professional(db: AsyncSession, clinic_id: UUID, user_id: UUID) -> bool:
        result = await db.execute(
            select(ClinicMembership.id).where(
                ClinicMembership.clinic_id == clinic_id,
                ClinicMembership.user_id == user_id,
                ClinicMembership.is_professional.is_(True),
            )
        )
        return result.scalar_one_or_none() is not None

    @staticmethod
    async def get_or_create_weekly(
        db: AsyncSession, clinic_id: UUID, user_id: UUID
    ) -> ProfessionalWeeklySchedule:
        result = await db.execute(
            select(ProfessionalWeeklySchedule)
            .options(selectinload(ProfessionalWeeklySchedule.shifts))
            .where(
                ProfessionalWeeklySchedule.clinic_id == clinic_id,
                ProfessionalWeeklySchedule.user_id == user_id,
            )
        )
        weekly = result.scalar_one_or_none()
        if weekly is not None:
            return weekly

        weekly = ProfessionalWeeklySchedule(clinic_id=clinic_id, user_id=user_id, is_active=True)
        db.add(weekly)
        await db.flush()
        await db.refresh(weekly, ["shifts"])
        return weekly

    @staticmethod
    async def replace_weekly_shifts(
        db: AsyncSession,
        weekly: ProfessionalWeeklySchedule,
        days: list[dict[str, Any]],
    ) -> ProfessionalWeeklySchedule:
        weekdays_touched = {d["weekday"] for d in days}
        for shift in list(weekly.shifts):
            if shift.weekday in weekdays_touched:
                await db.delete(shift)
        await db.flush()

        for day in days:
            for s in day["shifts"]:
                db.add(
                    ScheduleShift(
                        professional_weekly_id=weekly.id,
                        weekday=day["weekday"],
                        start_time=s["start_time"],
                        end_time=s["end_time"],
                    )
                )
        await db.flush()
        await db.refresh(weekly, ["shifts"])
        return weekly

    @staticmethod
    async def list_overrides(
        db: AsyncSession,
        clinic_id: UUID,
        user_id: UUID,
        start: date | None = None,
        end: date | None = None,
    ) -> list[ProfessionalOverride]:
        query = (
            select(ProfessionalOverride)
            .options(selectinload(ProfessionalOverride.shifts))
            .where(
                ProfessionalOverride.clinic_id == clinic_id,
                ProfessionalOverride.user_id == user_id,
            )
        )
        if start is not None:
            query = query.where(ProfessionalOverride.end_date >= start)
        if end is not None:
            query = query.where(ProfessionalOverride.start_date <= end)
        query = query.order_by(ProfessionalOverride.start_date)
        result = await db.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def get_override(
        db: AsyncSession,
        clinic_id: UUID,
        user_id: UUID,
        override_id: UUID,
    ) -> ProfessionalOverride | None:
        result = await db.execute(
            select(ProfessionalOverride)
            .options(selectinload(ProfessionalOverride.shifts))
            .where(
                ProfessionalOverride.id == override_id,
                ProfessionalOverride.clinic_id == clinic_id,
                ProfessionalOverride.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def create_override(
        db: AsyncSession, clinic_id: UUID, user_id: UUID, data: dict[str, Any]
    ) -> ProfessionalOverride:
        shifts = data.pop("shifts", []) or []
        override = ProfessionalOverride(clinic_id=clinic_id, user_id=user_id, **data)
        db.add(override)
        await db.flush()
        for s in shifts:
            db.add(
                ScheduleShift(
                    professional_override_id=override.id,
                    shift_date=override.start_date,
                    start_time=s["start_time"],
                    end_time=s["end_time"],
                )
            )
        await db.flush()
        await db.refresh(override, ["shifts"])
        return override

    @staticmethod
    async def update_override(
        db: AsyncSession,
        override: ProfessionalOverride,
        data: dict[str, Any],
    ) -> ProfessionalOverride:
        shifts = data.pop("shifts", None)
        for key, value in data.items():
            setattr(override, key, value)
        await db.flush()

        if shifts is not None:
            for existing in list(override.shifts):
                await db.delete(existing)
            await db.flush()
            for s in shifts:
                db.add(
                    ScheduleShift(
                        professional_override_id=override.id,
                        shift_date=override.start_date,
                        start_time=s["start_time"],
                        end_time=s["end_time"],
                    )
                )
            await db.flush()
            await db.refresh(override, ["shifts"])
        return override

    @staticmethod
    async def delete_override(db: AsyncSession, override: ProfessionalOverride) -> None:
        await db.delete(override)
        await db.flush()
