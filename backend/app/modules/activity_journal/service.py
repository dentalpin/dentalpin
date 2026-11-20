"""ActivityJournalService — read-only queries over the journal.

Every query is clinic-scoped. There is intentionally no create/update/
delete here: rows are written exclusively by the transactional event
handlers in ``events.py`` (append-only by construction).
"""

from __future__ import annotations

from datetime import date
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.utils.dates import clinic_day_range, clinic_zone_for

from .models import ActivityJournalEntry


class ActivityJournalService:
    @staticmethod
    async def list_entries(
        db: AsyncSession,
        clinic_id: UUID,
        event_type: str | None = None,
        actor_id: UUID | None = None,
        patient_id: UUID | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[ActivityJournalEntry], int]:
        stmt = select(ActivityJournalEntry).where(ActivityJournalEntry.clinic_id == clinic_id)
        if event_type:
            stmt = stmt.where(ActivityJournalEntry.event_type == event_type)
        if actor_id:
            stmt = stmt.where(ActivityJournalEntry.actor_id == actor_id)
        if patient_id:
            stmt = stmt.where(ActivityJournalEntry.patient_id == patient_id)
        if date_from or date_to:
            # ``occurred_at`` is an instant: cut it on the clinic's days (#920).
            zone = await clinic_zone_for(db, clinic_id)
            if date_from:
                start, _ = clinic_day_range(zone, date_from, date_from)
                stmt = stmt.where(ActivityJournalEntry.occurred_at >= start)
            if date_to:
                _, end = clinic_day_range(zone, date_to, date_to)
                stmt = stmt.where(ActivityJournalEntry.occurred_at < end)

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await db.execute(count_stmt)).scalar_one()

        stmt = (
            stmt.order_by(ActivityJournalEntry.occurred_at.desc(), ActivityJournalEntry.id)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        rows = (await db.execute(stmt)).scalars().all()
        return list(rows), total

    @staticmethod
    async def get_entry(db: AsyncSession, clinic_id: UUID, entry_id: UUID) -> ActivityJournalEntry:
        stmt = select(ActivityJournalEntry).where(
            ActivityJournalEntry.id == entry_id,
            ActivityJournalEntry.clinic_id == clinic_id,
        )
        entry = (await db.execute(stmt)).scalar_one_or_none()
        if entry is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Journal entry not found"
            )
        return entry
