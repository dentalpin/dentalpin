"""nav_online HTTP surface — mounted at ``/api/v1/nav_online/``."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.dependencies import ClinicContext, get_clinic_context, require_permission
from app.core.email.encryption import encrypt_password
from app.core.schemas import ApiResponse, PaginatedApiResponse
from app.database import get_db

from .models import NavOnlineRecord, NavOnlineSettings
from .schemas import NavRecordResponse, NavSettingsResponse, NavSettingsUpdate
from .services import nav_client, submission_queue

router = APIRouter()


async def _get_settings(db: AsyncSession, clinic_id: UUID) -> NavOnlineSettings | None:
    return (
        await db.execute(select(NavOnlineSettings).where(NavOnlineSettings.clinic_id == clinic_id))
    ).scalar_one_or_none()


def _settings_response(s: NavOnlineSettings | None) -> NavSettingsResponse:
    return NavSettingsResponse(
        enabled=bool(s and s.enabled),
        environment=s.environment if s else "test",
        tax_number=s.tax_number if s else None,
        technical_user_login=s.technical_user_login if s else None,
        has_password=bool(s and s.technical_user_password_encrypted),
        has_signature_key=bool(s and s.signature_key_encrypted),
        has_exchange_key=bool(s and s.exchange_key_encrypted),
        software_id=s.software_id if s else "DENTALPIN-00000001",
        software_dev_contact=s.software_dev_contact if s else None,
        last_nav_response_at=s.last_nav_response_at if s else None,
        next_send_after=s.next_send_after if s else None,
        last_error=s.last_error if s else None,
    )


@router.get("/settings", response_model=ApiResponse[NavSettingsResponse])
async def get_settings(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("nav_online.settings.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[NavSettingsResponse]:
    return ApiResponse(data=_settings_response(await _get_settings(db, ctx.clinic_id)))


@router.put("/settings", response_model=ApiResponse[NavSettingsResponse])
async def update_settings(
    data: NavSettingsUpdate,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("nav_online.settings.configure"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[NavSettingsResponse]:
    s = await _get_settings(db, ctx.clinic_id)
    if s is None:
        s = NavOnlineSettings(clinic_id=ctx.clinic_id, enabled=False, environment="test")
        db.add(s)
    for field in (
        "environment",
        "tax_number",
        "technical_user_login",
        "software_id",
        "software_dev_contact",
    ):
        value = getattr(data, field)
        if value is not None:
            setattr(s, field, value)
    if data.technical_user_password:
        s.technical_user_password_encrypted = encrypt_password(data.technical_user_password)
    if data.signature_key:
        s.signature_key_encrypted = encrypt_password(data.signature_key)
    if data.exchange_key:
        s.exchange_key_encrypted = encrypt_password(data.exchange_key)
    if data.enabled is not None:
        if data.enabled and submission_queue.credentials_for(s) is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Add meg az adószámot, a technikai felhasználót és mindkét kulcsot az aktiválás előtt.",
            )
        s.enabled = data.enabled
    # Any config change lifts a tokenExchange pause.
    s.next_send_after = None
    await db.flush()
    return ApiResponse(data=_settings_response(s))


@router.post("/settings/test-connection", response_model=ApiResponse[dict])
async def test_connection(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("nav_online.settings.configure"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[dict]:
    """Round-trip a tokenExchange against the selected environment."""
    s = await _get_settings(db, ctx.clinic_id)
    creds = submission_queue.credentials_for(s) if s else None
    if creds is None:
        return ApiResponse(data={"success": False, "error": "incomplete credentials"})
    try:
        token = await nav_client.exchange_token(creds, s.environment)
    except (nav_client.NavClientError, ValueError) as exc:
        s.last_error = str(exc)[:500]
        await db.flush()
        return ApiResponse(data={"success": False, "error": str(exc)[:500]})
    s.last_error = None
    s.next_send_after = None
    await db.flush()
    return ApiResponse(data={"success": True, "token_length": len(token)})


@router.get("/records", response_model=PaginatedApiResponse[NavRecordResponse])
async def list_records(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("nav_online.records.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    state: str | None = Query(default=None, max_length=20),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> PaginatedApiResponse[NavRecordResponse]:
    stmt = select(NavOnlineRecord).where(NavOnlineRecord.clinic_id == ctx.clinic_id)
    if state:
        stmt = stmt.where(NavOnlineRecord.state == state)
    total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    rows = (
        (
            await db.execute(
                stmt.order_by(NavOnlineRecord.created_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        )
        .scalars()
        .all()
    )
    return PaginatedApiResponse(
        data=[NavRecordResponse.model_validate(r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/records/{record_id}/xml")
async def record_xml(
    record_id: UUID,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("nav_online.records.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    row = await db.get(NavOnlineRecord, record_id)
    if row is None or row.clinic_id != ctx.clinic_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Record not found")
    return {"xml": row.xml_payload}


@router.post("/records/{record_id}/retry", response_model=ApiResponse[NavRecordResponse])
async def retry_record(
    record_id: UUID,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("nav_online.queue.manage"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[NavRecordResponse]:
    """Re-queue a rejected/aborted/failed row (after the invoice was fixed).

    ``sending`` is accepted too: a worker that died between committing the
    state and getting NAV's answer leaves the row stuck there for good.
    """
    row = await db.get(NavOnlineRecord, record_id)
    if row is None or row.clinic_id != ctx.clinic_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Record not found")
    if row.state not in ("rejected", "aborted", "failed", "sending"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot retry a record in state {row.state}",
        )
    row.state = "pending"
    row.attempts = 0
    row.next_attempt_at = None
    row.transaction_id = None
    row.nav_status = None
    row.error_code = None
    row.error_message = None
    row.finished_at = None
    await db.flush()
    return ApiResponse(data=NavRecordResponse.model_validate(row))


@router.post("/queue/process-now", response_model=ApiResponse[dict])
async def process_now(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("nav_online.queue.manage"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[dict]:
    counters = await submission_queue.process_clinic(db, ctx.clinic_id)
    return ApiResponse(data=counters)
