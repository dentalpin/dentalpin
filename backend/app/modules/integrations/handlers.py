"""Event handlers for the integrations module.

Transactional (ADR 0019), matching notifications/handlers.py exactly:
each body queues WebhookDelivery rows on the publisher's own session —
DB-only, no network I/O. The scheduled dispatch tick owns the network
I/O, so a rolled-back request queues no delivery.

Phase 1 ships two triggers end-to-end (Ramón 2026-08-21, see
notes/dentalpin/65-integrations-api.md "Current status") — the full
trigger catalog (issue #65 §3) is a follow-up PR.
"""

import logging
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class IntegrationsHandlers:
    """Event handlers for webhook trigger events."""

    @staticmethod
    async def on_patient_created(data: dict[str, Any], *, db: AsyncSession) -> None:
        """Handle patient.created: queue a delivery for every subscription
        that lists it, one row per matching active subscription.

        Transactional (ADR 0019): queues on the publisher's session, no
        network I/O here — the outbox tick does the sending.
        """
        from app.core.events import EventType

        from .gateway import WebhookGateway

        try:
            clinic_id = UUID(data["clinic_id"])
        except (KeyError, ValueError) as exc:
            logger.error("integrations: malformed patient.created payload: %s", exc)
            return

        async with db.begin_nested():
            await WebhookGateway.enqueue_for_event(
                db,
                clinic_id,
                EventType.PATIENT_CREATED,
                data,
            )

    @staticmethod
    async def on_appointment_completed(data: dict[str, Any], *, db: AsyncSession) -> None:
        """Handle appointment.completed: queue a delivery for every
        subscription that lists it, one row per matching active
        subscription.

        Transactional (ADR 0019): queues on the publisher's session, no
        network I/O here — the outbox tick does the sending. Mirrors
        ``on_patient_created`` exactly; payload shape comes from
        ``agenda/service.py``'s status-transition publish site.
        """
        from app.core.events import EventType

        from .gateway import WebhookGateway

        try:
            clinic_id = UUID(data["clinic_id"])
        except (KeyError, ValueError) as exc:
            logger.error("integrations: malformed appointment.completed payload: %s", exc)
            return

        async with db.begin_nested():
            await WebhookGateway.enqueue_for_event(
                db,
                clinic_id,
                EventType.APPOINTMENT_COMPLETED,
                data,
            )
