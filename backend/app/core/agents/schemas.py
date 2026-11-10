"""Pydantic schemas for /api/v1/agents/* endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.core.agents.models import ApprovalStatus


class AgentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    type: str = Field(min_length=1, max_length=100)
    mode: str = Field(pattern="^(autonomous|supervised)$")
    config: dict[str, Any] = Field(default_factory=dict)


class AgentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    clinic_id: UUID
    name: str
    type: str
    mode: str
    config: dict[str, Any]
    status: str
    created_at: datetime
    updated_at: datetime


class AgentSessionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    agent_id: UUID
    supervisor_id: UUID | None
    status: str
    created_at: datetime
    ended_at: datetime | None


class ApprovalResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    agent_id: UUID
    session_id: UUID
    tool_name: str
    arguments: dict[str, Any]
    reason: str | None
    status: ApprovalStatus
    reviewed_by: UUID | None
    reviewed_at: datetime | None
    review_notes: str | None
    created_at: datetime
    # Only on the approve response, when the run ended ``failed``: the
    # tool's error, so the reviewer sees why without opening the audit
    # log. Not stored on the row (the audit log keeps it).
    error: str | None = None


class ApprovalDecision(BaseModel):
    notes: str | None = Field(default=None, max_length=1000)


class AuditLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    agent_id: UUID
    session_id: UUID
    supervisor_id: UUID | None
    tool_name: str
    tool_arguments: dict[str, Any]
    result: dict[str, Any] | None
    error: str | None
    status: str
    execution_time_ms: int
    created_at: datetime
