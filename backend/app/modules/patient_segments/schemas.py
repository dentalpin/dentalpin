"""Schemas for patient_segments."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.schemas import NotNull

_HEX_COLOR = r"^#[0-9a-fA-F]{6}$"


def _strip_name(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    if not value:
        raise ValueError("name must not be blank")
    return value


class SegmentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    color: str | None = Field(default=None, pattern=_HEX_COLOR)
    description: str | None = None

    _strip = field_validator("name")(_strip_name)


class SegmentUpdate(BaseModel):
    """All-optional: PATCH semantics with exclude_unset (M4)."""

    # NOT NULL column: a null is a 422, not the duplicate-name 409 (#1134).
    name: NotNull[str] = Field(default=None, min_length=1, max_length=60)
    color: str | None = Field(default=None, pattern=_HEX_COLOR)
    description: str | None = None

    _strip = field_validator("name")(_strip_name)


class SegmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    color: str | None
    description: str | None
    member_count: int = 0
    created_at: datetime


class SegmentAssign(BaseModel):
    segment_id: UUID


class SegmentMemberResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    patient_id: UUID
    full_name: str
