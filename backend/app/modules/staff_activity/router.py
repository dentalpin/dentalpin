import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.dependencies import ClinicContext, get_clinic_context, require_permission
from app.database import get_db

from .schemas import StaffActivityLogListResponse
from .service import list_log_entries

router = APIRouter(tags=["staff-activity"])


@router.get("/", response_model=StaffActivityLogListResponse)
async def list_staff_activity(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("staff_activity.view"))],
    user_id: uuid.UUID | None = Query(default=None),
    action_type: str | None = Query(default=None),
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    search: str | None = Query(default=None),
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> StaffActivityLogListResponse:
    # NOTE: verify the exact attribute name on ClinicContext for the
    # current clinic id -- `ctx.clinic_id` is the common convention but
    # wasn't confirmed against the live class definition. Same for
    # `ctx.current_user_id` if you later want to default `user_id` to
    # "my own activity" for non-admin roles.
    items, total = await list_log_entries(
        db,
        clinic_id=ctx.clinic_id,
        user_id=user_id,
        action_type=action_type,
        date_from=date_from,
        date_to=date_to,
        search=search,
        limit=limit,
        offset=offset,
    )
    return StaffActivityLogListResponse(items=items, total=total)
