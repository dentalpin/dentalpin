"""whatsapp_kapso HTTP surface — mounted at ``/api/v1/whatsapp_kapso/``.

Settings endpoints require ``whatsapp_kapso.settings.*``. ``/webhook`` is
PUBLIC (no JWT — auth is per-route, there is no global gate): it resolves the
clinic by ``phone_number_id`` and verifies the per-clinic HMAC signature.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.dependencies import ClinicContext, get_clinic_context, require_permission
from app.core.auth.router import limiter
from app.core.schemas import ApiResponse
from app.database import get_db
from app.modules.notifications.gateway import NotificationGateway

from .schemas import (
    KapsoSettingsResponse,
    KapsoSettingsUpdate,
    KapsoTemplateMapRequest,
    KapsoTemplateResponse,
    KapsoTestRequest,
)
from .service import KapsoService, PhoneNumberIdTakenError

logger = logging.getLogger(__name__)
router = APIRouter()


def _settings_response(settings) -> KapsoSettingsResponse:
    return KapsoSettingsResponse(
        phone_number_id=settings.phone_number_id if settings else None,
        business_account_id=settings.business_account_id if settings else None,
        display_phone_number=settings.display_phone_number if settings else None,
        has_api_key=bool(settings and settings.api_key_encrypted),
        has_webhook_secret=bool(settings and settings.webhook_secret_encrypted),
        is_active=bool(settings and settings.is_active),
        is_verified=bool(settings and settings.is_verified),
        last_verified_at=settings.last_verified_at if settings else None,
        last_template_sync_at=settings.last_template_sync_at if settings else None,
    )


@router.get("/settings", response_model=ApiResponse[KapsoSettingsResponse])
async def get_settings(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("whatsapp_kapso.settings.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[KapsoSettingsResponse]:
    settings = await KapsoService.get_settings(db, ctx.clinic_id)
    return ApiResponse(data=_settings_response(settings))


@router.put("/settings", response_model=ApiResponse[KapsoSettingsResponse])
async def update_settings(
    data: KapsoSettingsUpdate,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("whatsapp_kapso.settings.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[KapsoSettingsResponse]:
    try:
        settings = await KapsoService.upsert_settings(db, ctx.clinic_id, data.model_dump())
    except PhoneNumberIdTakenError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    return ApiResponse(data=_settings_response(settings))


@router.post("/templates/sync", response_model=ApiResponse[list[KapsoTemplateResponse]])
async def sync_templates(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("whatsapp_kapso.settings.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[list[KapsoTemplateResponse]]:
    try:
        templates = await KapsoService.sync_templates(db, ctx.clinic_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return ApiResponse(data=[KapsoTemplateResponse.model_validate(t) for t in templates])


@router.post("/templates/map", status_code=status.HTTP_204_NO_CONTENT)
async def map_template(
    data: KapsoTemplateMapRequest,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("whatsapp_kapso.settings.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    await KapsoService.map_template(
        db,
        ctx.clinic_id,
        notification_type=data.notification_type,
        locale=data.locale,
        template_name=data.template_name,
    )


@router.post("/test", response_model=ApiResponse[dict])
async def test_connection(
    data: KapsoTestRequest,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("whatsapp_kapso.settings.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[dict]:
    ok, error = await KapsoService.test_connection(
        db, ctx.clinic_id, data.to_number, data.template_name, data.language
    )
    return ApiResponse(data={"success": ok, "error": error})


# --------------------------------------------------------------------------- #
# PUBLIC webhook — no JWT. Verified by per-clinic HMAC signature.
# --------------------------------------------------------------------------- #
@router.post("/webhook")
@limiter.limit("120/minute")
async def webhook(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    raw = await request.body()
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid json")

    phone_number_id = payload.get("phone_number_id")
    if not phone_number_id:
        return {"ok": True}  # nothing to route

    candidates = await KapsoService.resolve_by_phone_number_id(db, phone_number_id)
    if not candidates:
        # Unknown number — accept-and-ignore so Kapso doesn't hammer retries.
        return {"ok": True}

    signature = request.headers.get("X-Webhook-Signature", "")
    settings = next(
        (s for s in candidates if KapsoService.verify_signature(s, raw, signature)), None
    )
    if settings is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid signature")

    await _process_event(db, settings.clinic_id, payload)
    return {"ok": True}


def _parse_ts(value) -> datetime | None:
    try:
        return datetime.fromtimestamp(int(value), tz=UTC)
    except (TypeError, ValueError):
        return None


async def _process_event(db: AsyncSession, clinic_id, payload: dict) -> None:
    message = payload.get("message") or {}
    kapso = message.get("kapso") or {}
    wamid = message.get("id")
    direction = kapso.get("direction")

    if direction == "inbound":
        from_addr = message.get("from") or ""
        body = (message.get("text") or {}).get("body") or kapso.get("content") or ""
        patient = await NotificationGateway.resolve_patient_by_phone(db, clinic_id, from_addr)
        await NotificationGateway.record_inbound_reply(
            db,
            clinic_id,
            channel="whatsapp",
            from_address=from_addr,
            body=body,
            patient_id=patient.id if patient else None,
            provider_message_id=wamid,
            occurred_at=_parse_ts(message.get("timestamp")),
        )
        return

    # Outbound delivery/read/failed status.
    status_value = kapso.get("status")
    if status_value in ("delivered", "read", "failed") and wamid:
        await NotificationGateway.record_delivery_status(db, clinic_id, wamid, status_value)
