"""Background tasks for the notifications module.

Contains scheduled jobs for automated notifications like
appointment reminders.
"""

import logging
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import and_, select

from app.database import async_session_maker

logger = logging.getLogger(__name__)


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
                    if not patient or not patient.email:
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
                        "appointment_date": appointment.start_time.strftime("%d/%m/%Y"),
                        "appointment_time": appointment.start_time.strftime("%H:%M"),
                        "professional_name": professional_name,
                        "clinic_name": clinic.name if clinic else "Denplant",
                        "clinic_phone": clinic.phone if clinic else None,
                        "clinic_address": clinic.address if clinic else None,
                        "appointment_id": str(appointment.id),  # For duplicate check
                    }

                    # Enqueue reminder — dedup_key keeps the 5-min re-runs idempotent
                    # (replaces the old context_data["appointment_id"] log scan).
                    msg = await NotificationGateway.enqueue(
                        db=db,
                        clinic_id=clinic_id,
                        notification_type="appointment_reminder",
                        context=context,
                        patient_id=patient.id,
                        to_address=patient.email,
                        triggered_by_event="scheduler.appointment_reminder",
                        force_send=True,  # Skip preference check (already checked auto_send)
                        dedup_key=f"appointment_reminder:{appointment.id}",
                    )

                    if msg is None or msg.status == "skipped":
                        reminders_skipped += 1
                    else:
                        reminders_sent += 1
                        logger.info(
                            f"Queued reminder for appointment {appointment.id} to {patient.email}"
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


async def send_single_reminder(appointment_id: UUID, clinic_id: UUID) -> bool:
    """Send a single appointment reminder manually.

    This can be called directly from the API for manual reminder sending.

    Args:
        appointment_id: The appointment to send reminder for.
        clinic_id: The clinic ID.

    Returns:
        True if sent successfully, False otherwise.
    """
    from app.core.auth.models import Clinic, User
    from app.modules.agenda.models import Appointment
    from app.modules.notifications.gateway import NotificationGateway
    from app.modules.patients.models import Patient

    try:
        async with async_session_maker() as db:
            # Get appointment
            result = await db.execute(
                select(Appointment).where(
                    and_(
                        Appointment.id == appointment_id,
                        Appointment.clinic_id == clinic_id,
                    )
                )
            )
            appointment = result.scalar_one_or_none()
            if not appointment:
                logger.error(f"Appointment not found: {appointment_id}")
                return False

            # Get patient
            result = await db.execute(select(Patient).where(Patient.id == appointment.patient_id))
            patient = result.scalar_one_or_none()
            if not patient or not patient.email:
                logger.warning(f"Patient has no email for appointment: {appointment_id}")
                return False

            # Get clinic
            result = await db.execute(select(Clinic).where(Clinic.id == clinic_id))
            clinic = result.scalar_one_or_none()

            # Get professional
            professional_name = None
            if appointment.professional_id:
                result = await db.execute(
                    select(User).where(User.id == appointment.professional_id)
                )
                professional = result.scalar_one_or_none()
                if professional:
                    professional_name = f"{professional.first_name} {professional.last_name}"

            # Build context
            context = {
                "patient_name": f"{patient.first_name} {patient.last_name}",
                "appointment_date": appointment.start_time.strftime("%d/%m/%Y"),
                "appointment_time": appointment.start_time.strftime("%H:%M"),
                "professional_name": professional_name,
                "clinic_name": clinic.name if clinic else "Denplant",
                "clinic_phone": clinic.phone if clinic else None,
                "clinic_address": clinic.address if clinic else None,
                "appointment_id": str(appointment.id),
            }

            # Enqueue reminder (force_send to bypass auto_send check)
            msg = await NotificationGateway.enqueue(
                db=db,
                clinic_id=clinic_id,
                notification_type="appointment_reminder",
                context=context,
                patient_id=patient.id,
                to_address=patient.email,
                triggered_by_event="manual.appointment_reminder",
                force_send=True,
                dedup_key=f"appointment_reminder:{appointment.id}",
            )
            await db.commit()  # own session → own commit (``enqueue`` only flushes)

            return msg is not None and msg.status != "skipped"

    except Exception as e:
        logger.error(f"Error sending single reminder: {e}", exc_info=True)
        return False
