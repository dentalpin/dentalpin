"""Clinic-local calendar dates.

The server runs on UTC (no ``TZ`` in the images), so ``date.today()`` is
the UTC date — a day ahead of a UTC-6 clinic from 18:00 local, a day
behind a UTC+2 clinic until 02:00. Anything that stamps a *calendar*
date a clinic will read (an invoice's issue date, the year in its
number) must ask the clinic's clock instead.
"""

from datetime import date, datetime
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic


def clinic_zone(timezone: str | None) -> ZoneInfo:
    """The clinic's IANA ``timezone`` as a zone (UTC if unknown)."""
    try:
        return ZoneInfo(timezone) if timezone else ZoneInfo("UTC")
    except (ZoneInfoNotFoundError, ValueError):
        return ZoneInfo("UTC")


def clinic_today(timezone: str | None) -> date:
    """Today's date in the clinic's IANA ``timezone`` (UTC if unknown)."""
    return datetime.now(clinic_zone(timezone)).date()


async def clinic_zone_for(db: AsyncSession, clinic_id: UUID) -> ZoneInfo:
    """``clinic_zone`` for a clinic known only by id (one indexed read)."""
    timezone = await db.scalar(select(Clinic.timezone).where(Clinic.id == clinic_id))
    return clinic_zone(timezone)


async def clinic_today_for(db: AsyncSession, clinic_id: UUID) -> date:
    """``clinic_today`` for a clinic known only by id (one indexed read)."""
    return datetime.now(await clinic_zone_for(db, clinic_id)).date()
