"""TaskService — business logic for handoff-note CRUD and the staff picker."""

from __future__ import annotations

from datetime import date
from uuid import UUID

from fastapi import HTTPException, status as http_status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

# `users` / `clinic_memberships` are core tables, not plugin modules, so
# importing them needs no `manifest.depends` entry (same as `created_by`
# FKs elsewhere in the project).
from app.core.auth.models import ClinicMembership, User

from .models import Task
from .schemas import TaskCreate, TaskUpdate


def _to_response_dict(task: Task, names: dict[UUID, str]) -> dict:
    return {
        "id": task.id,
        "clinic_id": task.clinic_id,
        "title": task.title,
        "description": task.description,
        "priority": task.priority,
        "status": task.status,
        "assigned_to": task.assigned_to,
        "assigned_to_name": names.get(task.assigned_to) if task.assigned_to else None,
        "assigned_by": task.assigned_by,
        "assigned_by_name": names.get(task.assigned_by) if task.assigned_by else None,
        "due_date": task.due_date,
        "completed_at": task.completed_at,
        "created_at": task.created_at,
        "updated_at": task.updated_at,
    }


class TaskService:
    @staticmethod
    async def list_assignable_users(db: AsyncSession, clinic_id: UUID) -> list[dict]:
        stmt = (
            select(User.id, User.first_name, User.last_name, ClinicMembership.role)
            .join(ClinicMembership, ClinicMembership.user_id == User.id)
            .where(ClinicMembership.clinic_id == clinic_id, User.is_active.is_(True))
            .order_by(User.first_name.asc())
        )
        rows = (await db.execute(stmt)).all()
        return [
            {"id": r.id, "full_name": f"{r.first_name} {r.last_name}", "role": r.role}
            for r in rows
        ]

    @staticmethod
    async def _name_lookup(db: AsyncSession, user_ids: set[UUID]) -> dict[UUID, str]:
        user_ids.discard(None)
        if not user_ids:
            return {}
        stmt = select(User).where(User.id.in_(user_ids))
        users = (await db.execute(stmt)).scalars().all()
        return {u.id: u.full_name for u in users}

    @staticmethod
    async def create_task(
        db: AsyncSession, clinic_id: UUID, payload: TaskCreate, assigned_by: UUID | None
    ) -> Task:
        task = Task(
            clinic_id=clinic_id,
            title=payload.title,
            description=payload.description,
            priority=payload.priority,
            assigned_to=payload.assigned_to,
            assigned_by=assigned_by,
            due_date=payload.due_date,
            status="open",
        )
        db.add(task)
        await db.commit()
        await db.refresh(task)
        return task

    @staticmethod
    async def list_tasks(
        db: AsyncSession,
        clinic_id: UUID,
        task_status: str | None = None,
        assigned_to: UUID | None = None,
        priority: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Task], int]:
        stmt = select(Task).where(Task.clinic_id == clinic_id)
        if task_status:
            stmt = stmt.where(Task.status == task_status)
        if assigned_to:
            stmt = stmt.where(Task.assigned_to == assigned_to)
        if priority:
            stmt = stmt.where(Task.priority == priority)

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await db.execute(count_stmt)).scalar_one()

        stmt = (
            stmt.order_by(Task.status.asc(), Task.due_date.asc().nulls_last())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        rows = (await db.execute(stmt)).scalars().all()
        return list(rows), total

    @staticmethod
    async def get_task(db: AsyncSession, clinic_id: UUID, task_id: UUID) -> Task:
        stmt = select(Task).where(Task.id == task_id, Task.clinic_id == clinic_id)
        task = (await db.execute(stmt)).scalar_one_or_none()
        if task is None:
            raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail="Task not found")
        return task

    @staticmethod
    async def list_task_responses(
        db: AsyncSession,
        clinic_id: UUID,
        task_status: str | None = None,
        assigned_to: UUID | None = None,
        priority: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[dict], int]:
        tasks, total = await TaskService.list_tasks(
            db, clinic_id, task_status, assigned_to, priority, page, page_size
        )
        ids = {t.assigned_to for t in tasks} | {t.assigned_by for t in tasks}
        names = await TaskService._name_lookup(db, ids)
        return [_to_response_dict(t, names) for t in tasks], total

    @staticmethod
    async def get_task_response(db: AsyncSession, clinic_id: UUID, task_id: UUID) -> dict:
        task = await TaskService.get_task(db, clinic_id, task_id)
        names = await TaskService._name_lookup(db, {task.assigned_to, task.assigned_by})
        return _to_response_dict(task, names)

    @staticmethod
    async def update_task(
        db: AsyncSession, clinic_id: UUID, task_id: UUID, payload: TaskUpdate
    ) -> Task:
        task = await TaskService.get_task(db, clinic_id, task_id)
        data = payload.model_dump(exclude_unset=True)
        # Convenience: marking a task "done" auto-stamps today's date if
        # the caller didn't supply one — same pattern as lab_orders.received_date.
        if data.get("status") == "done" and task.completed_at is None:
            data["completed_at"] = date.today()
        elif data.get("status") == "open":
            data["completed_at"] = None

        for field, value in data.items():
            setattr(task, field, value)
        await db.commit()
        await db.refresh(task)
        return task

    @staticmethod
    async def delete_task(db: AsyncSession, clinic_id: UUID, task_id: UUID) -> None:
        task = await TaskService.get_task(db, clinic_id, task_id)
        await db.delete(task)
        await db.commit()
