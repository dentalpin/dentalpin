"""Clinic-scoped endpoints for the manual WhatsApp tray."""

from datetime import UTC, datetime
from typing import Annotated, Literal
from urllib.parse import quote, urlencode
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, Field, StringConstraints
from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.dependencies import ClinicContext, get_clinic_context, require_permission
from app.core.auth.rbac import has_permission_for
from app.core.events import EventType
from app.core.schemas import ApiResponse
from app.database import get_db
from app.modules.agenda.models import Appointment
from app.modules.notifications.gateway import NotificationGateway
from app.modules.notifications.models import ClinicChannelSettings, CommunicationMessage
from app.modules.patients.models import Patient

from .adapter import ADAPTER_NAME, ManualWhatsAppAdapter
from .models import ManualDeliveryDeclaration
from .service import (
    appointment_is_active,
    appointment_start,
    manual_messages,
    pending,
    unavailable_reason,
)

router = APIRouter()
Db = Annotated[AsyncSession, Depends(get_db)]
Context = Annotated[ClinicContext, Depends(get_clinic_context)]
Read = Annotated[None, Depends(require_permission("whatsapp_manual.read"))]
Write = Annotated[None, Depends(require_permission("whatsapp_manual.write"))]
Configure = Annotated[None, Depends(require_permission("whatsapp_manual.settings.write"))]
Draft = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4096)]


class TrayItem(BaseModel):
    id: UUID
    patient_name: str | None
    phone: str
    text: str
    created_at: datetime
    appointment_start_at: datetime | None


class Tray(BaseModel):
    items: list[TrayItem]
    total: int
    enabled: bool


class Settings(BaseModel):
    enabled: bool


class TrayAction(BaseModel):
    action: Literal["mark_sent", "dismiss"]
    ids: list[UUID] = Field(min_length=1, max_length=100)


class QueueDraft(BaseModel):
    patient_id: UUID
    appointment_id: UUID | None = None
    text: Draft
    request_id: UUID


@router.get("/tray")
async def list_tray(
    ctx: Context,
    db: Db,
    _: Read,
    page: Annotated[int, Query(ge=1, le=1_000_000)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
) -> ApiResponse[Tray]:
    """List pending messages for the active clinic."""
    query = pending().where(CommunicationMessage.clinic_id == ctx.clinic_id)
    total = await db.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = await db.scalars(
        query.order_by(CommunicationMessage.created_at, CommunicationMessage.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = [
        TrayItem(
            id=row.id,
            patient_name=(row.context_data or {}).get("patient_name"),
            phone=row.to_address,
            text=row.body_text or "",
            created_at=row.created_at,
            appointment_start_at=appointment_start(row),
        )
        for row in rows
    ]
    enabled = await ManualWhatsAppAdapter().supports(db, ctx.clinic_id)
    return ApiResponse(data=Tray(items=items, total=total, enabled=enabled))


@router.get("/count")
async def pending_count(ctx: Context, db: Db, _: Read) -> ApiResponse[int]:
    """Return just the pending count for the navigation badge."""
    query = pending().where(CommunicationMessage.clinic_id == ctx.clinic_id)
    return ApiResponse(
        data=await db.scalar(select(func.count()).select_from(query.subquery())) or 0
    )


@router.get("/settings")
async def get_settings(ctx: Context, db: Db, _: Read) -> ApiResponse[Settings]:
    """Tell the point-send controls whether the manual adapter is selected."""
    return ApiResponse(
        data=Settings(enabled=await ManualWhatsAppAdapter().supports(db, ctx.clinic_id))
    )


@router.put("/settings")
async def configure_adapter(
    data: Settings, ctx: Context, db: Db, _: Configure
) -> ApiResponse[Settings]:
    """Set the clinic's WhatsApp adapter selection."""
    if data.enabled:
        query = insert(ClinicChannelSettings).values(
            clinic_id=ctx.clinic_id, channel="whatsapp", adapter_name=ADAPTER_NAME, is_enabled=True
        )
        await db.execute(
            query.on_conflict_do_update(
                index_elements=["clinic_id", "channel"],
                set_={
                    "adapter_name": ADAPTER_NAME,
                    "is_enabled": True,
                    "is_verified": False,
                    "config": None,
                },
            )
        )
    else:
        await db.execute(
            delete(ClinicChannelSettings).where(
                ClinicChannelSettings.clinic_id == ctx.clinic_id,
                ClinicChannelSettings.channel == "whatsapp",
                ClinicChannelSettings.adapter_name == ADAPTER_NAME,
            )
        )
    return ApiResponse(data=data)


@router.post("/tray/{message_id}/open")
async def open_draft(message_id: UUID, ctx: Context, db: Db, _: Write) -> ApiResponse[str]:
    """Check the current contact state before handing a draft to WhatsApp."""
    row = await db.scalar(
        pending().where(
            CommunicationMessage.clinic_id == ctx.clinic_id,
            CommunicationMessage.id == message_id,
        )
    )
    if row is None:
        raise HTTPException(404, "draft_not_found")
    reason = await unavailable_reason(db, row, datetime.now(UTC))
    if reason:
        raise HTTPException(409, reason)
    return ApiResponse(
        data=f"https://wa.me/{row.to_address[1:]}?{urlencode({'text': row.body_text}, quote_via=quote)}"
    )


@router.post("/tray/actions")
async def act_on_drafts(data: TrayAction, ctx: Context, db: Db, _: Write) -> ApiResponse[int]:
    """Record staff declarations or dismissals atomically, with the actor."""
    ids = set(data.ids)
    marking = data.action == "mark_sent"
    statuses = ("awaiting_manual", "sent") if marking else ("awaiting_manual",)
    rows = (
        await db.scalars(
            manual_messages()
            .where(
                CommunicationMessage.clinic_id == ctx.clinic_id,
                CommunicationMessage.id.in_(ids),
                CommunicationMessage.status.in_(statuses),
            )
            .order_by(CommunicationMessage.id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
    ).all()
    if len(rows) != len(ids):
        raise HTTPException(409, "drafts_changed")

    now = datetime.now(UTC)
    marked = []
    for row in rows:
        if row.status == "sent":
            continue
        if marking:
            row.status = "sent"
            row.sent_at = now
            db.add(
                ManualDeliveryDeclaration(
                    message_id=row.id,
                    marked_by_user_id=ctx.user_id,
                    marked_at=now,
                )
            )
            marked.append(row)
        else:
            row.status = "skipped"
            row.error_message = "dismissed_by_staff"

    if marked:
        # The timeline handler opens its own transaction. Publish only after
        # saving the declarations, and only for newly marked rows.
        await db.commit()
        for row in marked:
            await NotificationGateway._publish(row, EventType.NOTIFICATION_SENT)
    return ApiResponse(data=len(rows))


@router.post("/drafts", status_code=202)
async def queue_draft(
    data: QueueDraft,
    ctx: Context,
    db: Db,
    _: Write,
    _patients: Annotated[None, Depends(require_permission("patients.read"))],
) -> Response:
    """Enqueue a staff draft via the same gateway as automated drafts."""
    if not await ManualWhatsAppAdapter().supports(db, ctx.clinic_id):
        raise HTTPException(409, "manual_adapter_inactive")
    patient = await db.scalar(
        select(Patient).where(Patient.clinic_id == ctx.clinic_id, Patient.id == data.patient_id)
    )
    if patient is None:
        raise HTTPException(404, "patient_not_found")
    context = {"patient_name": f"{patient.first_name} {patient.last_name}"}
    notification_type = "whatsapp_manual_message"
    if data.appointment_id:
        if not await has_permission_for(db, ctx.clinic_id, ctx.role, "agenda.appointments.read"):
            raise HTTPException(403, "permission_denied")
        appointment = await db.scalar(
            select(Appointment).where(
                Appointment.clinic_id == ctx.clinic_id,
                Appointment.id == data.appointment_id,
                Appointment.patient_id == patient.id,
            )
        )
        if appointment is None:
            raise HTTPException(404, "appointment_not_found")
        if appointment.start_time <= datetime.now(UTC):
            raise HTTPException(409, "appointment_expired")
        if not appointment_is_active(appointment):
            raise HTTPException(409, "appointment_changed")
        local_start = appointment.start_time.astimezone(ZoneInfo(ctx.clinic.timezone))
        context.update(
            appointment_id=str(appointment.id),
            appointment_start_at=appointment.start_time.isoformat(),
            appointment_date=local_start.strftime("%d/%m/%Y"),
            appointment_time=local_start.strftime("%H:%M"),
        )
    dedup_key = (
        f"whatsapp-manual:{ctx.user_id}:{patient.id}:{data.appointment_id}:{data.request_id}"
    )
    try:
        async with db.begin_nested():
            msg = await NotificationGateway.enqueue(
                db,
                ctx.clinic_id,
                notification_type,
                context=context,
                patient_id=patient.id,
                channels=["whatsapp"],
                force_send=True,
                triggered_by_user_id=ctx.user_id,
                body_text=data.text,
                dedup_key=dedup_key,
            )
            if msg is not None and msg.status == "skipped":
                msg.dedup_key = dedup_key
                await db.flush()
    except IntegrityError:
        # A concurrent retry can pass the gateway's initial duplicate check.
        msg = None
    if msg is None:
        msg = await db.scalar(
            select(CommunicationMessage).where(
                CommunicationMessage.clinic_id == ctx.clinic_id,
                CommunicationMessage.dedup_key == dedup_key,
            )
        )
        if msg is None:
            raise HTTPException(500, "draft_queue_failed")
    return Response(status_code=409 if msg.status == "skipped" else 202)
