"""Work manual WhatsApp drafts on their existing communication rows."""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import Select, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_maker
from app.modules.agenda.models import Appointment
from app.modules.notifications.gateway import NotificationGateway
from app.modules.notifications.models import CommunicationMessage
from app.modules.patients.models import Patient

from .adapter import ADAPTER_NAME, ManualWhatsAppAdapter


def manual_messages() -> Select[tuple[CommunicationMessage]]:
    """Scope the tray and every state transition to this adapter's outbox rows."""
    return select(CommunicationMessage).where(
        CommunicationMessage.direction == "outbound",
        CommunicationMessage.channel == "whatsapp",
        CommunicationMessage.provider == ADAPTER_NAME,
    )


def pending() -> Select[tuple[CommunicationMessage]]:
    return manual_messages().where(CommunicationMessage.status == "awaiting_manual")


def appointment_is_active(appointment: Appointment) -> bool:
    return appointment.status not in {"cancelled", "completed", "no_show"}


def appointment_start(row: CommunicationMessage) -> datetime | None:
    """Read the appointment instant captured by the notification producer."""
    raw = (row.context_data or {}).get("appointment_start_at")
    if not isinstance(raw, str):
        return None
    try:
        start = datetime.fromisoformat(raw)
    except ValueError:
        return None
    return start if start.utcoffset() is not None else None


async def unavailable_reason(
    db: AsyncSession, row: CommunicationMessage, now: datetime
) -> str | None:
    """Recheck patient choice and expiry when a staff member opens a draft."""
    start = appointment_start(row)
    context = row.context_data or {}
    if "appointment_id" in context or "appointment_start_at" in context:
        if start is None:
            return "appointment_changed"
        if start <= now:
            return "appointment_expired"
        try:
            appointment_id = UUID(str(context.get("appointment_id")))
        except ValueError:
            return "appointment_changed"
        appointment = await db.scalar(
            select(Appointment).where(
                Appointment.id == appointment_id,
                Appointment.clinic_id == row.clinic_id,
                Appointment.patient_id == row.patient_id,
            )
        )
        if (
            appointment is None
            or not appointment_is_active(appointment)
            or appointment.start_time != start
        ):
            return "appointment_changed"
    patient = await db.scalar(
        select(Patient).where(Patient.clinic_id == row.clinic_id, Patient.id == row.patient_id)
    )
    if not row.body_text or not await NotificationGateway.has_whatsapp_consent(
        db, row.clinic_id, patient, row.template_key
    ):
        return "whatsapp_consent_required"
    if not patient.phone or row.to_address != await ManualWhatsAppAdapter().normalize_recipient(
        db, row.clinic_id, patient.phone
    ):
        return "recipient_changed"
    return None


async def expire_pending(db: AsyncSession, now: datetime) -> int:
    """Expire appointment drafts, leaving unrelated and already handled rows alone."""
    candidates = await db.scalars(
        pending()
        .where(CommunicationMessage.context_data["appointment_start_at"].astext.is_not(None))
        .order_by(CommunicationMessage.id)
    )
    expired = [
        (row.clinic_id, row.id)
        for row in candidates
        if (start := appointment_start(row)) and start <= now
    ]
    count = 0
    for clinic_id, message_id in expired:
        result = await db.execute(
            update(CommunicationMessage)
            .where(
                CommunicationMessage.clinic_id == clinic_id,
                CommunicationMessage.id == message_id,
                CommunicationMessage.status == "awaiting_manual",
                CommunicationMessage.provider == ADAPTER_NAME,
            )
            .values(status="skipped", error_message="appointment_expired")
            .returning(CommunicationMessage.id)
        )
        count += result.scalar_one_or_none() is not None
    return count


async def expire_whatsapp_drafts() -> None:
    """Run the module-owned expiry job in a fresh transaction."""
    async with async_session_maker.begin() as db:
        await expire_pending(db, datetime.now(UTC))
