"""Copilot Pydantic schemas (non-SSE endpoints)."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class SessionCreate(BaseModel):
    context: dict[str, Any] = Field(default_factory=dict)


class ConversationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str | None
    status: str
    provider: str
    model: str
    total_input_tokens: int
    total_output_tokens: int
    created_at: datetime
    updated_at: datetime


class MessageCreate(BaseModel):
    content: str = Field(min_length=1, max_length=8000)


class MessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    role: str
    content: list[dict[str, Any]]
    created_at: datetime


class ConfirmRequest(BaseModel):
    decision: Literal["confirm", "reject"]


class SettingsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    provider: str
    model: str
    redaction_enabled: bool
    monthly_token_limit: int | None
    monthly_cost_limit_cents: int | None
    digest_enabled: bool
    digest_hour: int
    digest_recipient_user_ids: list[UUID]
    period_input_tokens: int
    period_output_tokens: int


class PendingItem(BaseModel):
    kind: Literal["recall", "budget"]
    id: str
    patient_id: str | None = None
    title: str | None = None
    link: str
    # kind-specific extras (reason/priority for recalls, number/amount for budgets)
    reason: str | None = None
    priority: str | None = None
    number: str | None = None
    amount: float | None = None


class NudgeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    kind: str
    payload: dict[str, Any]
    created_at: datetime
    expires_at: datetime


class ToolStat(BaseModel):
    tool_name: str
    calls: int
    errors: int


class MetricsResponse(BaseModel):
    window_days: int
    total_tool_calls: int
    failed_tool_calls: int
    error_rate: float
    avg_execution_ms: int
    conversations: int
    top_tools: list[ToolStat]
    period_input_tokens: int
    period_output_tokens: int
    monthly_token_limit: int | None
    token_usage_pct: float | None


class SettingsUpdate(BaseModel):
    provider: str | None = Field(default=None, max_length=20)
    model: str | None = Field(default=None, max_length=100)
    redaction_enabled: bool | None = None
    # ``null`` removes a limit. Zero stops the copilot; a negative value would too.
    monthly_token_limit: int | None = Field(default=None, ge=0)
    monthly_cost_limit_cents: int | None = Field(default=None, ge=0)
    digest_enabled: bool | None = None
    digest_hour: int | None = Field(default=None, ge=0, le=23)
    # v2: full replacement of the recipient list. None = leave unchanged;
    # [] = clear all recipients (effectively mutes the digest).
    digest_recipient_user_ids: list[UUID] | None = None
