"""Subscribes to recalls' RECALL_CREATED event and enqueues a reminder
via the notifications gateway.

Uses the gateway's existing consent/template/channel-resolution logic
unchanged — this module makes zero decisions about *how* to reach the
patient, only *that* a recall happening should try to.

Subscribed via ``RecallRemindersModule.get_event_handlers()`` in
``__init__.py`` — the framework's official extension point, called
exactly once per final module instance.
"""

from __future__ import annotations

import logging
from datetime import datetime
from uuid import UUID

from babel import UnknownLocaleError
from babel.dates import format_skeleton
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .reason_labels import reason_label

logger = logging.getLogger(__name__)


def _humanize_due_month(due_month: str | None, locale: str = "en") -> str | None:
    """``2026-09-01`` → "September 2026" / "septiembre de 2026" / … (#975).

    ``strftime("%B")`` only ever spoke English, so every non-English
    template printed an English month. Babel wants ``pt_BR``, not the
    ``pt-BR`` tag the app stores (#1135).
    """
    if not due_month:
        return None
    try:
        day = datetime.strptime(due_month, "%Y-%m-%d").date()
    except ValueError:
        return due_month
    try:
        return format_skeleton("yMMMM", day, locale=locale.replace("-", "_"))
    except (UnknownLocaleError, ValueError):
        return day.strftime("%B %Y")


async def _message_locale(db: AsyncSession, clinic_id: UUID, patient_id: UUID) -> str:
    """The locale the gateway renders this patient's message in: the
    patient's preference, else the clinic's communication language."""
    from app.modules.notifications.models import NotificationPreference
    from app.modules.notifications.service import resolve_clinic_communication_locale

    preferred = await db.scalar(
        select(NotificationPreference.preferred_locale).where(
            NotificationPreference.clinic_id == clinic_id,
            NotificationPreference.patient_id == patient_id,
        )
    )
    return preferred or await resolve_clinic_communication_locale(db, clinic_id)


async def _on_recall_created(payload: dict, *, db: AsyncSession) -> None:
    """Handle recall.created.

    Transactional (ADR 0019): queues the reminder on the publisher's
    session. Nothing is sent here — the outbox tick owns the network
    I/O — so a rolled-back request queues nothing, and the rows this
    reads are the publisher's own (issue #183).
    """
    from app.core.auth.models import Clinic
    from app.modules.notifications.gateway import NotificationGateway
    from app.modules.patients.models import Patient

    clinic_id = UUID(payload["clinic_id"])
    patient_id = UUID(payload["patient_id"])
    recall_id = payload["recall_id"]

    async with db.begin_nested():
        result = await db.execute(
            select(Patient).where(Patient.id == patient_id, Patient.clinic_id == clinic_id)
        )
        patient = result.scalar_one_or_none()
        if not patient:
            logger.error(f"Patient not found for recall reminder: {patient_id}")
            return

        result = await db.execute(select(Clinic).where(Clinic.id == clinic_id))
        clinic = result.scalar_one_or_none()

        locale = await _message_locale(db, clinic_id, patient_id)
        context = {
            "patient_name": f"{patient.first_name} {patient.last_name}",
            "clinic_name": clinic.name if clinic else "DentalPin",
            # The payload keeps the code; the message gets its label (#1135).
            "reason": reason_label(payload.get("reason"), locale),
            "due_month": _humanize_due_month(payload.get("due_month"), locale),
        }

        await NotificationGateway.enqueue(
            db=db,
            clinic_id=clinic_id,
            notification_type="recall_reminder",
            context=context,
            patient_id=patient_id,
            triggered_by_event="recall.created",
            # Idempotent safety net: if this ever fires more than once for
            # the same recall, the gateway dedupes on this key rather than
            # sending twice.
            dedup_key=f"recall_reminder:{recall_id}",
        )
