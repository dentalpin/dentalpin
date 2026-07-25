import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import StaffActivityLog


async def create_log_entry(
    db: AsyncSession,
    *,
    clinic_id: uuid.UUID,
    action_type: str,
    user_id: uuid.UUID | None = None,
    entity_type: str | None = None,
    entity_id: str | None = None,
    details: dict[str, Any] | None = None,
) -> StaffActivityLog:
    entry = StaffActivityLog(
        clinic_id=clinic_id,
        action_type=action_type,
        user_id=user_id,
        entity_type=entity_type,
        entity_id=entity_id,
        details=details or {},
    )
    db.add(entry)
    await db.commit()
    await db.refresh(entry)
    return entry


async def list_log_entries(
    db: AsyncSession,
    *,
    clinic_id: uuid.UUID,
    user_id: uuid.UUID | None = None,
    action_type: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    search: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[StaffActivityLog], int]:
    stmt = select(StaffActivityLog).where(StaffActivityLog.clinic_id == clinic_id)

    if user_id is not None:
        stmt = stmt.where(StaffActivityLog.user_id == user_id)
    if action_type is not None:
        stmt = stmt.where(StaffActivityLog.action_type == action_type)
    if date_from is not None:
        stmt = stmt.where(StaffActivityLog.timestamp >= date_from)
    if date_to is not None:
        stmt = stmt.where(StaffActivityLog.timestamp <= date_to)
    if search:
        like = f"%{search}%"
        stmt = stmt.where(
            (StaffActivityLog.action_type.ilike(like))
            | (StaffActivityLog.entity_type.ilike(like))
            | (StaffActivityLog.entity_id.ilike(like))
        )

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await db.execute(count_stmt)).scalar_one()

    stmt = stmt.order_by(StaffActivityLog.timestamp.desc()).limit(limit).offset(offset)
    rows = (await db.execute(stmt)).scalars().all()
    return list(rows), total
