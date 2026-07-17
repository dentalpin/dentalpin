"""Pydantic schemas for the tasks (handoff board) module."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

TaskPriority = Literal["low", "normal", "high"]
TaskStatus = Literal["open", "done"]


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    description: str | None = Field(default=None, max_length=2000)
    priority: TaskPriority = "normal"
    assigned_to: UUID | None = None
    due_date: date | None = None


class TaskUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=300)
    description: str | None = Field(default=None, max_length=2000)
    priority: TaskPriority | None = None
    status: TaskStatus | None = None
    assigned_to: UUID | None = None
    due_date: date | None = None


class TaskResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    clinic_id: UUID
    title: str
    description: str | None
    priority: TaskPriority
    status: TaskStatus
    assigned_to: UUID | None
    assigned_to_name: str | None
    assigned_by: UUID | None
    assigned_by_name: str | None
    due_date: date | None
    completed_at: date | None
    created_at: datetime
    updated_at: datetime


class AssignableUser(BaseModel):
    id: UUID
    full_name: str
    role: str
