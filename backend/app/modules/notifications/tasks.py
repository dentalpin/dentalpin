"""Background tasks for the notifications module.

Contains scheduled jobs for automated notifications like
appointment reminders.
"""

import logging
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import and_, select

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


async def reap_stuck_sending() -> None:
    """Scheduled job: retry messages left in ``sending`` by an interrupted send."""
    from app.modules.notifications.gateway import NotificationGateway

    try:
        async with async_session_maker() as db:
            await NotificationGateway.reap_stuck_sending(db)
    except Exception as exc:  # noqa: BLE001
        logger.error("Outbox stuck-sending reaper failed: %s", exc, exc_info=True)


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


async def process_appointment_reminders() -> None:
    """Process and send appointment reminders.

    This job runs periodically and:
    1. Gets all clinics with reminder enabled and auto_send=True
    2. For each clinic, finds appointments in the reminder window
    3. Checks if reminder was already sent (via email_logs)
    4. Sends reminder if not already sent

    The reminder window is: now < start_time <= now + hours_before
    """
    from app.core.auth.models import Clinic, User
    from app.modules.agenda.models import Appointment
    from app.modules.notifications.gateway import NotificationGateway
    from app.modules.notifications.models import ClinicNotificationSettings
    from app.modules.patients.models import Patient

    logger.debug("Processing appointment reminders...")
    reminders_sent = 0
    reminders_skipped = 0

    try:
        async with async_session_maker() as db:
            # Get all clinics with notification settings
            result = await db.execute(select(ClinicNotificationSettings))
            all_settings = list(result.scalars().all())

            for clinic_settings in all_settings:
                # Check if reminder is enabled and auto_send is True
                reminder_config = clinic_settings.settings.get("appointment_reminder", {})
                if not reminder_config.get("enabled", True):
                    continue
                if not reminder_config.get("auto_send", True):
                    continue

                hours_before = reminder_config.get("hours_before", 24)
                clinic_id = clinic_settings.clinic_id

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
                    continue

                logger.debug(
                    f"Found {len(appointments)} appointments in reminder window for clinic {clinic_id}"
                )

                # Get clinic info once
                result = await db.execute(select(Clinic).where(Clinic.id == clinic_id))
                clinic = result.scalar_one_or_none()

                for appointment in appointments:
                    # Get patient
                    result = await db.execute(
                        select(Patient).where(Patient.id == appointment.patient_id)
                    )
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
                        result = await db.execute(
                            select(User).where(User.id == appointment.professional_id)
                        )
                        professional = result.scalar_one_or_none()
                        if professional:
                            professional_name = (
                                f"{professional.first_name} {professional.last_name}"
                            )

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
