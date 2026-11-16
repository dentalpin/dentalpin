"""StaffTaskService — clinic-scoped CRUD and status transitions."""

from __future__ import annotations

from datetime import UTC, date, datetime
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import ClinicMembership
from app.core.events import event_bus
from app.core.events.types import EventType

from .models import StaffTask
from .schemas import StaffTaskCreate, StaffTaskUpdate

_VALID_TRANSITIONS = {
    "open": {"claimed", "done", "cancelled"},
    "claimed": {"done", "cancelled", "open"},
    "done": set(),
    "cancelled": {"open"},
}


async def _check_assignee(db: AsyncSession, clinic_id: UUID, user_id: UUID) -> None:
    """400 unless ``user_id`` is a member of the task's clinic."""
    member = await db.scalar(
        select(ClinicMembership.id).where(
            ClinicMembership.clinic_id == clinic_id, ClinicMembership.user_id == user_id
        )
    )
    if member is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Assignee is not a member of this clinic",
        )


class StaffTaskService:
    @staticmethod
    async def create_task(
        db: AsyncSession,
        clinic_id: UUID,
        payload: StaffTaskCreate,
        created_by: UUID | None,
    ) -> StaffTask:
        if payload.assignee_id is not None:
            await _check_assignee(db, clinic_id, payload.assignee_id)
        task = StaffTask(
            clinic_id=clinic_id,
            title=payload.title,
            details=payload.details,
            priority=payload.priority,
            assignee_id=payload.assignee_id,
            due_date=payload.due_date,
            created_by=created_by,
            status="open",
        )
        db.add(task)
        await db.flush()
        # ADR 0019 — publish inside the transaction with the publisher's
        # session; the caller (router / agent runtime) owns the commit.
        await event_bus.publish(
            EventType.STAFF_TASK_CREATED,
            StaffTaskService._event_payload(task),
            db=db,
        )
        await db.commit()
        await db.refresh(task)
        return task

    @staticmethod
    async def list_tasks(
        db: AsyncSession,
        clinic_id: UUID,
        task_status: str | None = None,
        assignee_id: UUID | None = None,
        due_before: date | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[StaffTask], int]:
        stmt = select(StaffTask).where(StaffTask.clinic_id == clinic_id)
        if task_status:
            stmt = stmt.where(StaffTask.status == task_status)
        if assignee_id:
            stmt = stmt.where(StaffTask.assignee_id == assignee_id)
        if due_before:
            stmt = stmt.where(StaffTask.due_date <= due_before)

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await db.execute(count_stmt)).scalar_one()

        # Open work first (by due date), then newest; id as final tiebreaker
        # so pagination is stable.
        stmt = (
            stmt.order_by(
                StaffTask.completed_at.is_not(None),
                StaffTask.due_date.asc().nulls_last(),
                StaffTask.created_at.desc(),
                StaffTask.id,
            )
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        rows = (await db.execute(stmt)).scalars().all()
        return list(rows), total

    @staticmethod
    async def get_task(db: AsyncSession, clinic_id: UUID, task_id: UUID) -> StaffTask:
        stmt = select(StaffTask).where(StaffTask.id == task_id, StaffTask.clinic_id == clinic_id)
        task = (await db.execute(stmt)).scalar_one_or_none()
        if task is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
        return task

    @staticmethod
    async def update_task(
        db: AsyncSession,
        clinic_id: UUID,
        task_id: UUID,
        payload: StaffTaskUpdate,
        actor_id: UUID | None,
    ) -> StaffTask:
        task = await StaffTaskService.get_task(db, clinic_id, task_id)
        data = payload.model_dump(exclude_unset=True)
        new_assignee = data.get("assignee_id")
        if new_assignee is not None and new_assignee != task.assignee_id:
            await _check_assignee(db, clinic_id, new_assignee)

        new_status = data.get("status")
        if new_status and new_status != task.status:
            allowed = _VALID_TRANSITIONS.get(task.status, set())
            if new_status not in allowed:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"cannot transition from '{task.status}' to '{new_status}'",
                )
            if new_status == "claimed" and task.assignee_id is None and "assignee_id" not in data:
                # Claiming an unassigned task assigns the claimer. Agent
                # actors carry no user identity — the field stays null.
                data["assignee_id"] = actor_id
            if new_status == "open" and "assignee_id" not in data:
                # Un-claiming / re-opening puts the task back up for grabs.
                data["assignee_id"] = None
            if new_status == "done":
                data["completed_at"] = datetime.now(UTC)
        elif new_status == task.status:
            # No-op transition — drop it so the event doesn't fire.
            data.pop("status", None)

        for field, value in data.items():
            setattr(task, field, value)
        await db.flush()

        if "status" in data:
            await event_bus.publish(
                EventType.STAFF_TASK_STATUS_CHANGED,
                StaffTaskService._event_payload(task),
                db=db,
            )
        await db.commit()
        await db.refresh(task)
        return task

    @staticmethod
    async def delete_task(db: AsyncSession, clinic_id: UUID, task_id: UUID) -> None:
        task = await StaffTaskService.get_task(db, clinic_id, task_id)
        await db.delete(task)
        await db.commit()

    @staticmethod
    def _event_payload(task: StaffTask) -> dict:
        return {
            "clinic_id": str(task.clinic_id),
            "task_id": str(task.id),
            "status": task.status,
            "priority": task.priority,
            "assignee_id": str(task.assignee_id) if task.assignee_id else None,
            "due_date": task.due_date.isoformat() if task.due_date else None,
        }
