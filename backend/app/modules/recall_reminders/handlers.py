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

from uuid import UUID

from app.database import async_session_maker
from app.modules.notifications.gateway import NotificationGateway


async def _on_recall_created(payload: dict) -> None:
    clinic_id = UUID(payload["clinic_id"])
    patient_id = UUID(payload["patient_id"])
    recall_id = payload["recall_id"]

    async with async_session_maker() as db:
        await NotificationGateway.enqueue(
            db=db,
            clinic_id=clinic_id,
            notification_type="recall_reminder",
            context={
                "reason": payload.get("reason"),
                "due_month": payload.get("due_month"),
            },
            patient_id=patient_id,
            triggered_by_event="recall.created",
            # Idempotent safety net: if this ever fires more than once for
            # the same recall, the gateway dedupes on this key rather than
            # sending twice.
            dedup_key=f"recall_reminder:{recall_id}",
        )
