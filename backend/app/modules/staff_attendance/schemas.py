"""Schemas for staff_attendance."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ClockRequest(BaseModel):
    user_id: UUID
    kind: Literal["in", "out"]
    at: datetime | None = None
    note: str | None = Field(default=None, max_length=255)


class AttendanceEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    kind: str
    at: datetime
    note: str | None
    created_by: UUID


class AttendanceStatusResponse(BaseModel):
    user_id: UUID
    state: Literal["in", "out"]
    since: datetime | None


class AttendanceReportRow(BaseModel):
    user_id: UUID
    full_name: str
    seconds: int
    open: bool = False


class AttendanceReportResponse(BaseModel):
    date: str
    rows: list[AttendanceReportRow]


class MemberResponse(BaseModel):
    id: UUID
    first_name: str
    last_name: str
    role: str
