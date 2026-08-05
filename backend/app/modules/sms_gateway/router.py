"""sms_gateway HTTP surface. Mounts under ``/api/v1/sms-gateway/*``."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.dependencies import ClinicContext, get_clinic_context, require_permission
from app.core.schemas import ApiResponse, PaginatedApiResponse
from app.database import get_db

from .schemas import SmsOutboxLogResponse, SmsSettingsResponse, SmsSettingsUpdate
from .service import SmsGatewayService

router = APIRouter()


def _to_response(settings) -> SmsSettingsResponse:
    return SmsSettingsResponse(
        provider_name=settings.provider_name,
        sender_id=settings.sender_id,
        base_url=settings.base_url,
        has_api_key=bool(settings.api_key_encrypted),
        is_active=settings.is_active,
    )


@router.get("/providers", response_model=ApiResponse[list[str]])
async def list_providers(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("sms_gateway.settings.read"))],
) -> ApiResponse[list[str]]:
    return ApiResponse(data=SmsGatewayService.list_available_providers())


@router.get("/settings", response_model=ApiResponse[SmsSettingsResponse])
async def get_settings(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("sms_gateway.settings.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[SmsSettingsResponse]:
    settings = await SmsGatewayService.get_or_create_settings(db, ctx.clinic_id)
    return ApiResponse(data=_to_response(settings))


@router.patch("/settings", response_model=ApiResponse[SmsSettingsResponse])
async def update_settings(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("sms_gateway.settings.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    payload: SmsSettingsUpdate,
) -> ApiResponse[SmsSettingsResponse]:
    settings = await SmsGatewayService.update_settings(db, ctx.clinic_id, payload)
    return ApiResponse(data=_to_response(settings))


@router.get("/outbox", response_model=PaginatedApiResponse[SmsOutboxLogResponse])
async def list_outbox(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("sms_gateway.settings.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> PaginatedApiResponse[SmsOutboxLogResponse]:
    logs, total = await SmsGatewayService.list_outbox(db, ctx.clinic_id, page, page_size)
    return PaginatedApiResponse(
        data=[SmsOutboxLogResponse.model_validate(log) for log in logs],
        total=total,
        page=page,
        page_size=page_size,
    )
