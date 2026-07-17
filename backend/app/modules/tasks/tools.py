"""Agent tools for the tasks (handoff board) module. Thin wrappers over TaskService."""

from __future__ import annotations

from datetime import date as date_cls
from uuid import UUID

from pydantic import BaseModel, Field

from app.core.agents import AgentContext, Tool, ToolCategory

from .schemas import TaskCreate, TaskPriority, TaskStatus
from .service import TaskService


class ListTasksArgs(BaseModel):
    task_status: TaskStatus | None = None
    assigned_to: UUID | None = None
    priority: TaskPriority | None = None
    limit: int = Field(default=20, ge=1, le=100)


class CreateTaskArgs(BaseModel):
    title: str
    description: str | None = None
    priority: TaskPriority = "normal"
    assigned_to: UUID | None = None
    due_date: date_cls | None = None


class MarkTaskDoneArgs(BaseModel):
    task_id: UUID


def _task_summary(task) -> dict:
    return {
        "id": str(task.id),
        "title": task.title,
        "status": task.status,
        "priority": task.priority,
        "assigned_to": str(task.assigned_to) if task.assigned_to else None,
        "due_date": task.due_date,
    }


async def _list_tasks(ctx: AgentContext, params: ListTasksArgs) -> dict:
    items, total = await TaskService.list_tasks(
        ctx.db,
        ctx.clinic_id,
        task_status=params.task_status,
        assigned_to=params.assigned_to,
        priority=params.priority,
        page=1,
        page_size=params.limit,
    )
    return {"total": total, "tasks": [_task_summary(t) for t in items]}


async def _create_task(ctx: AgentContext, params: CreateTaskArgs) -> dict:
    payload = TaskCreate(
        title=params.title,
        description=params.description,
        priority=params.priority,
        assigned_to=params.assigned_to,
        due_date=params.due_date,
    )
    task = await TaskService.create_task(ctx.db, ctx.clinic_id, payload, ctx.user_id)
    return _task_summary(task)


async def _mark_task_done(ctx: AgentContext, params: MarkTaskDoneArgs) -> dict:
    from .schemas import TaskUpdate

    task = await TaskService.update_task(
        ctx.db, ctx.clinic_id, params.task_id, TaskUpdate(status="done")
    )
    return _task_summary(task)


def get_tools() -> list[Tool]:
    return [
        Tool(
            name="list_tasks",
            description="List staff handoff tasks, optionally filtered by status, assignee, or priority.",
            parameters=ListTasksArgs,
            handler=_list_tasks,
            permissions=["tasks.read"],
            category=ToolCategory.READ,
        ),
        Tool(
            name="create_task",
            description="Create a new staff handoff task, optionally assigned to a specific team member.",
            parameters=CreateTaskArgs,
            handler=_create_task,
            permissions=["tasks.write"],
            category=ToolCategory.WRITE,
        ),
        Tool(
            name="mark_task_done",
            description="Mark a handoff task as done.",
            parameters=MarkTaskDoneArgs,
            handler=_mark_task_done,
            permissions=["tasks.write"],
            category=ToolCategory.WRITE,
        ),
    ]
