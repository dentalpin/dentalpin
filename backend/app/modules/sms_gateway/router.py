"""sms_gateway HTTP surface — mounted at ``/api/v1/sms_gateway/`` (admin only)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.dependencies import ClinicContext, get_clinic_context, require_permission
from app.core.schemas import ApiResponse
from app.database import get_db

from . import providers as sms_providers
from .schemas import SmsSettingsResponse, SmsSettingsUpdate, mask_settings
from .service import SmsGatewayService

router = APIRouter()


@router.get("/providers", response_model=ApiResponse[list[str]])
async def list_providers(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("sms_gateway.settings.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[list[str]]:
    """Wire backends actually registered (issue #392 review). The settings
    page offers only these, so an admin can never select a backend that
    fails every message."""
    return ApiResponse(data=sorted(sms_providers.list_providers()))


@router.get("/settings", response_model=ApiResponse[SmsSettingsResponse])
async def get_settings(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("sms_gateway.settings.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[SmsSettingsResponse]:
    row = await SmsGatewayService.get_settings(db, ctx.clinic_id)
    if row is None:
        # Opening the page must not enable the channel: the admin flips
        # the toggle explicitly (the log placeholder reports "sent"
        # while sending nothing).
        row = await SmsGatewayService.upsert_settings(db, ctx.clinic_id, {"is_active": False})
    return ApiResponse(data=mask_settings(row))


@router.put("/settings", response_model=ApiResponse[SmsSettingsResponse])
async def update_settings(
    data: SmsSettingsUpdate,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("sms_gateway.settings.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[SmsSettingsResponse]:
    if data.provider is not None and sms_providers.get_provider(data.provider) is None:
        # A selectable-but-unimplemented backend (e.g. twilio in v1) must
        # fail loudly here, never silently at send time (issue #392 review).
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unknown SMS provider: {data.provider}",
        )
    row = await SmsGatewayService.upsert_settings(
        db, ctx.clinic_id, data.model_dump(exclude_unset=True)
    )
    return ApiResponse(data=mask_settings(row))


@router.post("/test", response_model=ApiResponse[dict], status_code=status.HTTP_200_OK)
async def test_connection(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("sms_gateway.settings.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[dict]:
    """Dry-run honesty check: reports what WOULD happen. Sends nothing."""
    row = await SmsGatewayService.get_settings(db, ctx.clinic_id)
    if row is None or not row.is_active:
        return ApiResponse(data={"configured": False, "would_send": False})
    if row.provider == "log":
        return ApiResponse(
            data={
                "configured": True,
                "would_send": True,
                "note": "log placeholder: messages are recorded in the server log, NOT SENT",
            }
        )
    return ApiResponse(
        data={
            "configured": True,
            "would_send": False,
            "note": f"provider '{row.provider}' is not implemented in v1",
        }
    )
