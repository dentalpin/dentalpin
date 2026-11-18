"""Expire core access metadata independently of GDPR module installation."""

from calendar import monthrange
from datetime import UTC, datetime

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic
from app.core.patient_access import PatientAccessLog, retention_years
from app.database import async_session_maker


async def purge_expired_access(db: AsyncSession, *, now: datetime) -> None:
    clinics = await db.execute(select(Clinic.id, Clinic.settings))
    for clinic_id, settings in clinics:
        year = now.year - retention_years(settings)
        cutoff = now.replace(year=year, day=min(now.day, monthrange(year, now.month)[1]))
        await db.execute(
            delete(PatientAccessLog).where(
                PatientAccessLog.clinic_id == clinic_id,
                PatientAccessLog.occurred_at < cutoff,
            )
        )


async def run_access_retention() -> None:
    async with async_session_maker.begin() as db:
        await purge_expired_access(db, now=datetime.now(UTC))
