"""Event handlers for the notifications module.

These handlers listen to events from other modules and queue notifications
when appropriate.

All of them are **transactional** (ADR 0019): they read the publisher's own
rows and queue a ``CommunicationMessage`` on its session. Nothing is sent
here — ``NotificationGateway.dispatch_outbox`` (scheduler) owns the network
I/O, so there is no external side effect inside the transaction.

Each body runs inside a **savepoint**: queueing a message is best-effort and
must never fail the appointment, patient or invoice it announces, but an
error still has to unwind cleanly or the publisher's transaction would be
left unusable. The outer transaction rolling back discards the queued
message too, which is the point — no confirmation email for an appointment
that was never booked (issue #183).
"""

import logging
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .service import (
    appointment_when_context,
    budget_treatments_context,
    clinic_date_label,
    money_formatter,
    resolve_patient_communication_locale,
)

logger = logging.getLogger(__name__)


def _has_contact(patient) -> bool:
    """A patient is reachable when they have an email OR a phone.

    The gateway resolves the concrete address per channel
    (``patient.email`` for email, ``patient.phone`` for WhatsApp), so
    handlers only gate on "some contact exists" and never steer the
    channel by passing an email address.
    """
    return patient is not None and bool(patient.email or patient.phone)


def _public_budget_url(public_token) -> str | None:
    """Best-effort absolute public quote link (``/p/budget/{token}``).

    The frontend origin is not stored per clinic; the first configured
    ``ALLOWED_ORIGINS`` entry is the deployment's public origin. Without
    one (dev/test) the path is still emitted so templates can render a
    stable link target.
    """
    if not public_token:
        return None
    from app.config import settings

    origins = settings.allowed_origins_list
    base = origins[0].rstrip("/") if origins else ""
    return f"{base}/p/budget/{public_token}"


class NotificationHandlers:
    """Event handlers for notification triggers."""

    @staticmethod
    async def on_patient_updated(data: dict[str, Any], *, db: AsyncSession) -> None:
        if "do_not_contact" not in data.get("changes", ()):
            return

        from app.modules.patients.models import Patient

        from .service import NotificationService

        clinic_id, patient_id = UUID(data["clinic_id"]), UUID(data["patient_id"])
        blocked = await db.scalar(
            select(Patient.do_not_contact).where(
                Patient.clinic_id == clinic_id, Patient.id == patient_id
            )
        )
        if blocked:
            await NotificationService.cancel_pending_whatsapp(db, clinic_id, patient_id)

    @staticmethod
    async def on_appointment_scheduled(data: dict[str, Any], *, db: AsyncSession) -> None:
        """Handle appointment.scheduled event.

        Queues the appointment confirmation for the patient.

        Transactional (ADR 0019): queues the message on the publisher's
        session. Nothing is sent here — the outbox tick owns the network
        I/O — so a rolled-back request queues nothing, and the rows this
        reads are the publisher's own (issue #183).
        """
        from app.modules.agenda.models import Appointment
        from app.modules.notifications.gateway import NotificationGateway
        from app.modules.patients.models import Patient

        try:
            clinic_id = UUID(data["clinic_id"])
            appointment_id = UUID(data["appointment_id"])

            async with db.begin_nested():
                # Get appointment with patient
                result = await db.execute(
                    select(Appointment).where(
                        Appointment.clinic_id == clinic_id, Appointment.id == appointment_id
                    )
                )
                appointment = result.scalar_one_or_none()
                if not appointment:
                    logger.error(f"Appointment not found: {appointment_id}")
                    return

                # Get patient
                result = await db.execute(
                    select(Patient).where(
                        Patient.clinic_id == clinic_id, Patient.id == appointment.patient_id
                    )
                )
                patient = result.scalar_one_or_none()
                if not _has_contact(patient):
                    logger.info(
                        f"Patient has no email or phone, skipping notification: "
                        f"{appointment.patient_id}"
                    )
                    return

                # Get clinic info
                from app.core.auth.models import Clinic

                result = await db.execute(select(Clinic).where(Clinic.id == clinic_id))
                clinic = result.scalar_one_or_none()

                # Get professional info if assigned
                professional_name = None
                if appointment.professional_id:
                    from app.core.auth.models import User

                    result = await db.execute(
                        select(User).where(User.id == appointment.professional_id)
                    )
                    professional = result.scalar_one_or_none()
                    if professional:
                        professional_name = f"{professional.first_name} {professional.last_name}"

                # Build context
                context = {
                    "patient_name": f"{patient.first_name} {patient.last_name}",
                    "appointment_id": str(appointment.id),
                    "appointment_start_at": appointment.start_time.isoformat(),
                    **appointment_when_context(appointment.start_time, clinic),
                    "professional_name": professional_name,
                    "clinic_name": clinic.name if clinic else "DentalPin",
                    "clinic_phone": clinic.phone if clinic else None,
                    "clinic_address": clinic.address if clinic else None,
                }

                # Queue it — the outbox tick does the sending. No
                # to_address / channels: the gateway resolves the clinic's
                # preferred channel and the matching patient contact.
                await NotificationGateway.enqueue(
                    db=db,
                    clinic_id=clinic_id,
                    notification_type="appointment_confirmation",
                    context=context,
                    patient_id=patient.id,
                    triggered_by_event="appointment.scheduled",
                )

        except Exception as e:
            logger.error(f"Error handling appointment.scheduled: {e}", exc_info=True)

    @staticmethod
    async def on_appointment_cancelled(data: dict[str, Any], *, db: AsyncSession) -> None:
        """Handle appointment.cancelled event.

        Queues the cancellation notice for the patient.

        Transactional (ADR 0019): queues the message on the publisher's
        session. Nothing is sent here — the outbox tick owns the network
        I/O — so a rolled-back request queues nothing, and the rows this
        reads are the publisher's own (issue #183).
        """
        from app.modules.agenda.models import Appointment
        from app.modules.notifications.gateway import NotificationGateway
        from app.modules.patients.models import Patient

        try:
            clinic_id = UUID(data["clinic_id"])
            appointment_id = UUID(data["appointment_id"])
            cancellation_reason = data.get("reason")

            async with db.begin_nested():
                # Get appointment
                result = await db.execute(
                    select(Appointment).where(
                        Appointment.clinic_id == clinic_id, Appointment.id == appointment_id
                    )
                )
                appointment = result.scalar_one_or_none()
                if not appointment:
                    return

                # Get patient
                result = await db.execute(
                    select(Patient).where(
                        Patient.clinic_id == clinic_id, Patient.id == appointment.patient_id
                    )
                )
                patient = result.scalar_one_or_none()
                if not _has_contact(patient):
                    return

                # Get clinic info
                from app.core.auth.models import Clinic

                result = await db.execute(select(Clinic).where(Clinic.id == clinic_id))
                clinic = result.scalar_one_or_none()

                # Get professional info
                professional_name = None
                if appointment.professional_id:
                    from app.core.auth.models import User

                    result = await db.execute(
                        select(User).where(User.id == appointment.professional_id)
                    )
                    professional = result.scalar_one_or_none()
                    if professional:
                        professional_name = f"{professional.first_name} {professional.last_name}"

                # Build context
                context = {
                    "patient_name": f"{patient.first_name} {patient.last_name}",
                    "appointment_id": str(appointment.id),
                    "appointment_start_at": appointment.start_time.isoformat(),
                    **appointment_when_context(appointment.start_time, clinic),
                    "professional_name": professional_name,
                    "cancellation_reason": cancellation_reason,
                    "clinic_name": clinic.name if clinic else "DentalPin",
                    "clinic_phone": clinic.phone if clinic else None,
                }

                await NotificationGateway.enqueue(
                    db=db,
                    clinic_id=clinic_id,
                    notification_type="appointment_cancelled",
                    context=context,
                    patient_id=patient.id,
                    triggered_by_event="appointment.cancelled",
                )

        except Exception as e:
            logger.error(f"Error handling appointment.cancelled: {e}", exc_info=True)

    @staticmethod
    async def on_patient_created(data: dict[str, Any], *, db: AsyncSession) -> None:
        """Handle patient.created event.

        Queues the welcome message for the new patient (if auto_send is enabled).

        Transactional (ADR 0019): queues the message on the publisher's
        session. Nothing is sent here — the outbox tick owns the network
        I/O — so a rolled-back request queues nothing, and the rows this
        reads are the publisher's own (issue #183).
        """
        from app.modules.notifications.gateway import NotificationGateway
        from app.modules.patients.models import Patient

        try:
            clinic_id = UUID(data["clinic_id"])
            patient_id = UUID(data["patient_id"])

            async with db.begin_nested():
                # Get patient
                result = await db.execute(
                    select(Patient).where(Patient.clinic_id == clinic_id, Patient.id == patient_id)
                )
                patient = result.scalar_one_or_none()
                if not _has_contact(patient):
                    return

                # Get clinic info
                from app.core.auth.models import Clinic

                result = await db.execute(select(Clinic).where(Clinic.id == clinic_id))
                clinic = result.scalar_one_or_none()

                # Build context
                context = {
                    "patient_name": f"{patient.first_name} {patient.last_name}",
                    "clinic_name": clinic.name if clinic else "DentalPin",
                    "clinic_phone": clinic.phone if clinic else None,
                    "clinic_address": clinic.address if clinic else None,
                }

                await NotificationGateway.enqueue(
                    db=db,
                    clinic_id=clinic_id,
                    notification_type="welcome",
                    context=context,
                    patient_id=patient.id,
                    triggered_by_event="patient.created",
                )

        except Exception as e:
            logger.error(f"Error handling patient.created: {e}", exc_info=True)

    @staticmethod
    async def on_budget_sent(data: dict[str, Any], *, db: AsyncSession) -> None:
        """Handle budget.sent event.

        Queues the budget notification for the patient when staff chose a
        real channel (``send_method`` is ``email`` or ``whatsapp``).
        Manual sends (printed/handed) don't queue anything.

        Transactional (ADR 0019): queues the message on the publisher's
        session. Nothing is sent here — the outbox tick owns the network
        I/O — so a rolled-back request queues nothing, and the rows this
        reads are the publisher's own (issue #183).
        """
        from app.modules.budget.models import Budget
        from app.modules.notifications.gateway import NotificationGateway
        from app.modules.patients.models import Patient

        # Only queue when staff explicitly picked a channel.
        send_method = data.get("send_method", "manual")
        if send_method not in ("email", "whatsapp"):
            logger.info(
                f"Budget sent manually (no channel), skipping notification: {data.get('budget_id')}"
            )
            return

        try:
            clinic_id = UUID(data["clinic_id"])
            budget_id = UUID(data["budget_id"])

            async with db.begin_nested():
                # Get budget with items
                result = await db.execute(
                    select(Budget).where(Budget.clinic_id == clinic_id, Budget.id == budget_id)
                )
                budget = result.scalar_one_or_none()
                if not budget:
                    return

                # Get patient
                result = await db.execute(
                    select(Patient).where(
                        Patient.clinic_id == clinic_id, Patient.id == budget.patient_id
                    )
                )
                patient = result.scalar_one_or_none()
                if not _has_contact(patient):
                    return

                # Get clinic info
                from app.core.auth.models import Clinic

                result = await db.execute(select(Clinic).where(Clinic.id == clinic_id))
                clinic = result.scalar_one_or_none()

                # Amounts are formatted for the locale the gateway will
                # render in, in the clinic's currency (#1133).
                money = money_formatter(
                    clinic, await resolve_patient_communication_locale(db, clinic_id, patient.id)
                )

                # Get budget items
                treatments = await budget_treatments_context(db, budget_id, money)

                # Build context
                context = {
                    "patient_name": f"{patient.first_name} {patient.last_name}",
                    "budget_number": budget.budget_number,
                    "budget_date": budget.valid_from.strftime("%d/%m/%Y"),
                    "treatments": treatments,
                    "subtotal": money(budget.subtotal),
                    "discount_amount": money(budget.total_discount)
                    if budget.total_discount
                    else None,
                    "total": money(budget.total),
                    "validity_days": (budget.valid_until - budget.valid_from).days
                    if budget.valid_until
                    else None,
                    "notes": budget.patient_notes,
                    "custom_message": data.get("custom_message"),
                    "clinic_name": clinic.name if clinic else "DentalPin",
                    "clinic_phone": clinic.phone if clinic else None,
                    # Public quote link — the WhatsApp HSM carries this
                    # instead of the HTML treatments table.
                    "public_url": _public_budget_url(budget.public_token),
                }

                # Staff explicitly picked the channel on the send modal, so
                # steer resolution to exactly that channel (no fallback) and
                # bypass the auto_send gate — this is a manual send.
                # ``do_not_contact`` still hard-blocks inside the gateway.
                await NotificationGateway.enqueue(
                    db=db,
                    clinic_id=clinic_id,
                    notification_type="budget_sent",
                    context=context,
                    patient_id=patient.id,
                    channels=[send_method],
                    force_send=True,
                    triggered_by_event="budget.sent",
                )

        except Exception as e:
            logger.error(f"Error handling budget.sent: {e}", exc_info=True)

    @staticmethod
    async def on_invoice_sent(data: dict[str, Any], *, db: AsyncSession) -> None:
        """Handle invoice.sent event.

        Queues the invoice notification for the patient when staff chose a
        real channel (``send_method`` is ``email`` or ``whatsapp``).
        Manual sends don't queue anything.

        Transactional (ADR 0019): queues the message on the publisher's
        session. Nothing is sent here — the outbox tick owns the network
        I/O — so a rolled-back request queues nothing, and the rows this
        reads are the publisher's own (issue #183).
        """
        from app.modules.billing.models import Invoice, InvoiceItem
        from app.modules.billing.service import compute_paid_summary
        from app.modules.notifications.gateway import NotificationGateway
        from app.modules.patients.models import Patient

        # Only queue when staff explicitly picked a channel.
        send_method = data.get("send_method", "manual")
        if send_method not in ("email", "whatsapp"):
            logger.info(
                f"Invoice sent manually (no channel), skipping notification: {data.get('invoice_id')}"
            )
            return

        try:
            clinic_id = UUID(data["clinic_id"])
            invoice_id = UUID(data["invoice_id"])

            async with db.begin_nested():
                # Get invoice with items
                result = await db.execute(
                    select(Invoice).where(Invoice.clinic_id == clinic_id, Invoice.id == invoice_id)
                )
                invoice = result.scalar_one_or_none()
                if not invoice:
                    return

                # Get patient
                result = await db.execute(
                    select(Patient).where(
                        Patient.clinic_id == clinic_id, Patient.id == invoice.patient_id
                    )
                )
                patient = result.scalar_one_or_none()
                if not _has_contact(patient):
                    return

                # Get clinic info
                from app.core.auth.models import Clinic

                result = await db.execute(select(Clinic).where(Clinic.id == clinic_id))
                clinic = result.scalar_one_or_none()

                # Get invoice items
                result = await db.execute(
                    select(InvoiceItem).where(InvoiceItem.invoice_id == invoice_id)
                )
                items = result.scalars().all()

                # Amounts are formatted for the locale the gateway will
                # render in, in the clinic's currency (#1133).
                money = money_formatter(
                    clinic, await resolve_patient_communication_locale(db, clinic_id, patient.id)
                )

                # ``balance_due`` is computed from payments, not a column:
                # reading ``invoice.balance_due`` raised and the handler
                # never queued the email.
                _, balance_due = await compute_paid_summary(db, clinic_id, invoice_id)

                # Build items list for template
                invoice_items = []
                for item in items:
                    invoice_items.append(
                        {
                            "description": item.description,
                            "quantity": item.quantity,
                            "unit_price": money(item.unit_price),
                            "line_total": money(item.line_total),
                        }
                    )

                # Build context
                context = {
                    "patient_name": f"{patient.first_name} {patient.last_name}",
                    "invoice_number": invoice.invoice_number,
                    "invoice_date": invoice.issue_date.strftime("%d/%m/%Y")
                    if invoice.issue_date
                    else None,
                    "due_date": invoice.due_date.strftime("%d/%m/%Y") if invoice.due_date else None,
                    "items": invoice_items,
                    "subtotal": money(invoice.subtotal),
                    "total_discount": money(invoice.total_discount)
                    if invoice.total_discount
                    else None,
                    "total_tax": money(invoice.total_tax) if invoice.total_tax else None,
                    "total": money(invoice.total),
                    # A settled invoice hides the balance row: the template
                    # tests its truthiness, and "0,00 €" is truthy.
                    "balance_due": money(balance_due) if balance_due else None,
                    "billing_name": invoice.billing_name,
                    "custom_message": data.get("custom_message"),
                    "clinic_name": clinic.name if clinic else "DentalPin",
                    "clinic_phone": clinic.phone if clinic else None,
                    "clinic_address": clinic.address if clinic else None,
                }

                # Staff explicitly picked the channel on the send modal —
                # same manual-send semantics as budget_sent above.
                await NotificationGateway.enqueue(
                    db=db,
                    clinic_id=clinic_id,
                    notification_type="invoice_sent",
                    context=context,
                    patient_id=patient.id,
                    channels=[send_method],
                    force_send=True,
                    triggered_by_event="invoice.sent",
                )

        except Exception as e:
            logger.error(f"Error handling invoice.sent: {e}", exc_info=True)

    @staticmethod
    async def on_budget_accepted(data: dict[str, Any], *, db: AsyncSession) -> None:
        """Handle budget.accepted event.

        Queues the budget acceptance confirmation for the patient.

        Transactional (ADR 0019): queues the message on the publisher's
        session. Nothing is sent here — the outbox tick owns the network
        I/O — so a rolled-back request queues nothing, and the rows this
        reads are the publisher's own (issue #183).
        """
        from app.modules.budget.models import Budget
        from app.modules.notifications.gateway import NotificationGateway
        from app.modules.patients.models import Patient

        try:
            clinic_id = UUID(data["clinic_id"])
            budget_id = UUID(data["budget_id"])

            async with db.begin_nested():
                # Get budget
                result = await db.execute(
                    select(Budget).where(Budget.clinic_id == clinic_id, Budget.id == budget_id)
                )
                budget = result.scalar_one_or_none()
                if not budget:
                    return

                # Get patient
                result = await db.execute(
                    select(Patient).where(
                        Patient.clinic_id == clinic_id, Patient.id == budget.patient_id
                    )
                )
                patient = result.scalar_one_or_none()
                if not _has_contact(patient):
                    return

                # Get clinic info
                from app.core.auth.models import Clinic

                result = await db.execute(select(Clinic).where(Clinic.id == clinic_id))
                clinic = result.scalar_one_or_none()

                money = money_formatter(
                    clinic, await resolve_patient_communication_locale(db, clinic_id, patient.id)
                )

                # Build context
                context = {
                    "patient_name": f"{patient.first_name} {patient.last_name}",
                    "budget_number": budget.budget_number,
                    "accepted_date": clinic_date_label(budget.updated_at, clinic),
                    "total": money(budget.total),
                    "notes": budget.patient_notes,
                    "clinic_name": clinic.name if clinic else "DentalPin",
                    "clinic_phone": clinic.phone if clinic else None,
                }

                await NotificationGateway.enqueue(
                    db=db,
                    clinic_id=clinic_id,
                    notification_type="budget_accepted",
                    context=context,
                    patient_id=patient.id,
                    triggered_by_event="budget.accepted",
                )

        except Exception as e:
            logger.error(f"Error handling budget.accepted: {e}", exc_info=True)

    @staticmethod
    async def on_budget_reminder_sent(data: dict[str, Any], *, db: AsyncSession) -> None:
        """Handle budget.reminder_sent event (7d / 14d milestones).

        The budget cron (and the manual ``/send-reminder`` endpoint) only
        stamps ``last_reminder_sent_at`` and publishes the event — this
        handler is what actually queues a patient-visible message through
        the gateway (issue #287 bug 7: before it existed, the timeline
        recorded a reminder no patient ever received).

        Transactional (ADR 0019): queues the message on the publisher's
        session. Nothing is sent here — the outbox tick owns the network
        I/O — so a rolled-back request queues nothing, and the rows this
        reads are the publisher's own (issue #183).
        """
        from app.modules.budget.models import Budget
        from app.modules.notifications.gateway import NotificationGateway
        from app.modules.patients.models import Patient

        try:
            clinic_id = UUID(data["clinic_id"])
            budget_id = UUID(data["budget_id"])
            milestone_days = data.get("milestone_days")

            async with db.begin_nested():
                # Get budget
                result = await db.execute(
                    select(Budget).where(Budget.clinic_id == clinic_id, Budget.id == budget_id)
                )
                budget = result.scalar_one_or_none()
                if not budget:
                    return

                # Get patient
                result = await db.execute(
                    select(Patient).where(
                        Patient.clinic_id == clinic_id, Patient.id == budget.patient_id
                    )
                )
                patient = result.scalar_one_or_none()
                if not _has_contact(patient):
                    logger.info(
                        f"Patient has no email or phone, skipping budget reminder: {budget_id}"
                    )
                    return

                # Get clinic info
                from app.core.auth.models import Clinic

                result = await db.execute(select(Clinic).where(Clinic.id == clinic_id))
                clinic = result.scalar_one_or_none()

                money = money_formatter(
                    clinic, await resolve_patient_communication_locale(db, clinic_id, patient.id)
                )

                context = {
                    "patient_name": f"{patient.first_name} {patient.last_name}",
                    "budget_number": budget.budget_number,
                    "milestone_days": milestone_days,
                    # The template hides the row when falsy; keep a zero
                    # total hidden as the old 0.0 did.
                    "total": money(budget.total) if budget.total else None,
                    "valid_until": budget.valid_until.strftime("%d/%m/%Y")
                    if budget.valid_until
                    else None,
                    "public_url": _public_budget_url(budget.public_token),
                    "clinic_name": clinic.name if clinic else "DentalPin",
                    "clinic_phone": clinic.phone if clinic else None,
                }

                # No force_send: the clinic-level budget_reminder toggle and
                # the patient's per-type opt-out both apply. A skip still
                # writes an outbox row with the real reason, so "reminder
                # sent" on the timeline is never silent again.
                await NotificationGateway.enqueue(
                    db=db,
                    clinic_id=clinic_id,
                    notification_type="budget_reminder",
                    context=context,
                    patient_id=patient.id,
                    triggered_by_event="budget.reminder_sent",
                    # One automatic reminder per budget and milestone (#1115);
                    # manual reminders from reception always go out.
                    dedup_key=(
                        f"budget_reminder:{budget_id}:{milestone_days}"
                        if data.get("automatic")
                        else None
                    ),
                )

        except Exception as e:
            logger.error(f"Error handling budget.reminder_sent: {e}", exc_info=True)
