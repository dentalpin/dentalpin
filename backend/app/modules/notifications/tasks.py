"""Background tasks for the notifications module.

Contains scheduled jobs for automated notifications like
appointment reminders.
"""

import logging
import math
from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_maker
from app.modules.notifications.service import (
    appointment_when_context,
    resolve_patient_communication_locale,
)

logger = logging.getLogger(__name__)


def _reminder_checkin_url(appointment, clinic) -> str | None:
    """Day-valid reminder check-in link, sweep and manual send (ADR 0037).

    Mints a ``source=reminder`` token living until the end of the
    appointment's clinic-local day and returns its patient-facing URL.
    Returns None (and logs) when no public origin is configured, so a
    missing ALLOWED_ORIGINS degrades to a link-less reminder instead of
    failing the whole sweep.
    """
    from app.modules.agenda.checkin import build_checkin_url, mint_checkin_token
    from app.modules.agenda.tz import as_utc, safe_zone

    try:
        tz = safe_zone(getattr(clinic, "timezone", None))
        now_utc = datetime.now(UTC)
        start_utc = as_utc(appointment.start_time, tz)
        day_end_local = start_utc.astimezone(tz).replace(
            hour=23, minute=59, second=59, microsecond=0
        )
        ttl_minutes = max(60, int((day_end_local.astimezone(UTC) - now_utc).total_seconds() // 60))
        token, _ = mint_checkin_token(
            appointment.id, appointment.clinic_id, source="reminder", ttl_minutes=ttl_minutes
        )
        return build_checkin_url(token)
    except HTTPException:
        # No public origin configured: link-less reminders, never a failed sweep.
        logger.warning("Reminder check-in link skipped: no public origin configured")
        return None
    except Exception as exc:  # noqa: BLE001
        # Anything else (bad signing key, clock skew) would go link-less
        # indefinitely on a WARNING; make a permanent failure visible.
        logger.error("Reminder check-in link skipped by unexpected error: %s", exc)
        return None


async def dispatch_outbox() -> None:
    """Scheduled tick: send a batch of due queued/failed messages.

    Thin wrapper around ``NotificationGateway.dispatch_outbox`` that owns the
    DB session. Network I/O happens here (in the scheduler), never in a request.
    """
    from app.modules.notifications.gateway import NotificationGateway

    try:
        async with async_session_maker() as db:
            sent = await NotificationGateway.dispatch_outbox(db)
            if sent:
                logger.debug("Outbox dispatch tick processed %d message(s)", sent)
    except Exception as exc:  # noqa: BLE001
        logger.error("Outbox dispatch tick failed: %s", exc, exc_info=True)


async def _reminder_key(db, appointment) -> str:
    """One reminder per appointment and start time (#1035).

    The first keeps the plain key, which is what rows sent so far carry. A
    later start time gets its own, so a moved appointment is reminded again.
    """
    from app.modules.notifications.models import CommunicationMessage

    key = f"appointment_reminder:{appointment.id}"
    context = await db.scalar(
        select(CommunicationMessage.context_data).where(
            CommunicationMessage.clinic_id == appointment.clinic_id,
            CommunicationMessage.dedup_key == key,
        )
    )
    reminded_for = (context or {}).get("appointment_start_at")
    if not reminded_for or datetime.fromisoformat(reminded_for) == appointment.start_time:
        return key
    return f"{key}:{appointment.start_time.astimezone(UTC).isoformat()}"


# Upper bound the job applies to a stored lead time, so a huge legacy value
# can't overflow ``timedelta``. Far above the 168 h the PUT now allows.
_REMINDER_HOURS_JOB_CAP = 24 * 365


def _reminder_hours_before(config: dict) -> float | None:
    """The clinic's reminder lead time in hours, or ``None`` when unusable.

    The settings PUT validates ``hours_before`` (#1243), but rows saved
    before that can hold anything the old page or API sent. Values that
    worked before keep working: a fractional number (the page saved
    ``Number(v)``, e.g. 12.5) and a numeric string like ``"24"``. ``null``,
    booleans, non-numeric text, NaN/inf and anything below 1 can't build a
    reminder window, so the job skips that clinic instead of raising or
    silently using an empty window.
    """
    value = config.get("hours_before", 24)
    if isinstance(value, bool):
        return None
    if isinstance(value, str):
        try:
            value = float(value.strip())
        except ValueError:
            return None
    if not isinstance(value, int | float) or not math.isfinite(value) or value < 1:
        return None
    return min(value, _REMINDER_HOURS_JOB_CAP)


async def _remind_clinic(db: AsyncSession, clinic_id: UUID, hours_before: float) -> tuple[int, int]:
    """Enqueue the due reminders for one clinic. Returns (sent, skipped)."""
    from app.core.auth.models import Clinic, User
    from app.modules.agenda.models import Appointment
    from app.modules.notifications.gateway import NotificationGateway
    from app.modules.patients.models import Patient

    reminders_sent = 0
    reminders_skipped = 0

    # Calculate the reminder window
    now = datetime.now(UTC)
    window_end = now + timedelta(hours=hours_before)

    # Find appointments in the window that are still scheduled
    result = await db.execute(
        select(Appointment).where(
            and_(
                Appointment.clinic_id == clinic_id,
                Appointment.status == "scheduled",
                Appointment.start_time > now,
                Appointment.start_time <= window_end,
            )
        )
    )
    appointments = list(result.scalars().all())

    if not appointments:
        return 0, 0

    logger.debug(
        f"Found {len(appointments)} appointments in reminder window for clinic {clinic_id}"
    )

    # Get clinic info once
    result = await db.execute(select(Clinic).where(Clinic.id == clinic_id))
    clinic = result.scalar_one_or_none()

    for appointment in appointments:
        # Get patient
        result = await db.execute(select(Patient).where(Patient.id == appointment.patient_id))
        patient = result.scalar_one_or_none()
        # Skip only patients with no contact at all — the gateway
        # resolves email vs phone from the clinic's preferred
        # channel (issue #287 bug 3).
        if not patient or not (patient.email or patient.phone):
            reminders_skipped += 1
            continue

        # Get professional info
        professional_name = None
        if appointment.professional_id:
            result = await db.execute(select(User).where(User.id == appointment.professional_id))
            professional = result.scalar_one_or_none()
            if professional:
                professional_name = f"{professional.first_name} {professional.last_name}"

        # Build context
        context = {
            "patient_name": f"{patient.first_name} {patient.last_name}",
            "appointment_start_at": appointment.start_time.isoformat(),
            **appointment_when_context(
                appointment.start_time,
                clinic,
                await resolve_patient_communication_locale(db, clinic_id, patient.id),
            ),
            "professional_name": professional_name,
            "clinic_name": clinic.name if clinic else "DentalPin",
            "clinic_phone": clinic.phone if clinic else None,
            "clinic_address": clinic.address if clinic else None,
            "appointment_id": str(appointment.id),  # For duplicate check
            "checkin_url": _reminder_checkin_url(appointment, clinic),
        }

        # Enqueue reminder — dedup_key keeps the 5-min re-runs idempotent
        # (replaces the old context_data["appointment_id"] log scan).
        msg = await NotificationGateway.enqueue(
            db=db,
            clinic_id=clinic_id,
            notification_type="appointment_reminder",
            context=context,
            patient_id=patient.id,
            triggered_by_event="scheduler.appointment_reminder",
            force_send=True,  # Skip preference check (already checked auto_send)
            dedup_key=await _reminder_key(db, appointment),
        )

        if msg is None or msg.status == "skipped":
            reminders_skipped += 1
        else:
            reminders_sent += 1
            logger.info(
                f"Queued reminder for appointment {appointment.id} "
                f"via {msg.channel} to {msg.to_address}"
            )

    return reminders_sent, reminders_skipped


async def process_appointment_reminders() -> None:
    """Process and send appointment reminders.

    This job runs periodically and:
    1. Gets all clinics with reminder enabled and auto_send=True
    2. For each clinic, finds appointments in the reminder window
    3. Checks if reminder was already sent (via email_logs)
    4. Sends reminder if not already sent

    The reminder window is: now < start_time <= now + hours_before

    Each clinic runs in its own savepoint: a clinic whose stored settings or
    data make it fail is logged and skipped, and the other clinics still get
    their reminders (#1243).
    """
    from app.modules.notifications.models import ClinicNotificationSettings

    logger.debug("Processing appointment reminders...")
    reminders_sent = 0
    reminders_skipped = 0

    try:
        async with async_session_maker() as db:
            # Get all clinics with notification settings. Read the plain
            # values up front: a rolled-back savepoint expires ORM objects.
            # A fixed order keeps runs reproducible.
            result = await db.execute(
                select(
                    ClinicNotificationSettings.clinic_id, ClinicNotificationSettings.settings
                ).order_by(ClinicNotificationSettings.clinic_id)
            )
            all_settings = list(result.all())

            for clinic_id, type_settings in all_settings:
                # Check if reminder is enabled and auto_send is True
                reminder_config = (type_settings or {}).get("appointment_reminder") or {}
                if not isinstance(reminder_config, dict):
                    logger.warning(
                        "Skipping reminders for clinic %s: appointment_reminder settings "
                        "are not an object",
                        clinic_id,
                    )
                    continue
                if not reminder_config.get("enabled", True):
                    continue
                if not reminder_config.get("auto_send", True):
                    continue

                hours_before = _reminder_hours_before(reminder_config)
                if hours_before is None:
                    logger.warning(
                        "Skipping reminders for clinic %s: invalid hours_before %r",
                        clinic_id,
                        reminder_config.get("hours_before"),
                    )
                    continue

                try:
                    async with db.begin_nested():
                        sent, skipped = await _remind_clinic(db, clinic_id, hours_before)
                except Exception:  # noqa: BLE001 — isolate one clinic's failure
                    logger.error(
                        "Error processing appointment reminders for clinic %s",
                        clinic_id,
                        exc_info=True,
                    )
                    continue
                reminders_sent += sent
                reminders_skipped += skipped

            # This job owns its session, so it commits what ``enqueue``
            # flushed. Once for the whole sweep: the ``dedup_key`` makes a
            # re-run after a failure a no-op.
            await db.commit()

        if reminders_sent > 0 or reminders_skipped > 0:
            logger.info(
                f"Reminder job complete: {reminders_sent} sent, {reminders_skipped} skipped"
            )

    except Exception as e:
        logger.error(f"Error processing appointment reminders: {e}", exc_info=True)
