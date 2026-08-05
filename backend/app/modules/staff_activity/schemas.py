import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class StaffActivityLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    clinic_id: uuid.UUID
    user_id: uuid.UUID | None = None
    action_type: str
    entity_type: str | None = None
    entity_id: str | None = None
    details: dict[str, Any]
    timestamp: datetime


class StaffActivityLogListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    items: list[StaffActivityLogRead]
    total: int
