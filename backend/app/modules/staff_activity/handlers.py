"""Generic event -> journal-row handler.

Subscribes the same handler function to every EventType that represents
a staff/user action, skipping purely internal/system events. Subscription
happens exclusively through BaseModule.get_event_handlers() (bug #4) --
never via a manual event_bus.subscribe() call, since dev-mode
double-instantiates modules.
"""

import uuid
from typing import Any, Awaitable, Callable

from app.core.events import EventType
from app.database import async_session_maker

from .service import create_log_entry

# Internal/system events that are not a "staff action" and would be
# high-volume or redundant noise in the journal.
_SKIP_EVENTS: set[str] = {
    EventType.TENANT_RESOLVED,
    EventType.EMAIL_SENT,
    EventType.EMAIL_FAILED,
    EventType.NOTIFICATION_QUEUED,
    EventType.NOTIFICATION_SENT,
    EventType.NOTIFICATION_FAILED,
    EventType.NOTIFICATION_DELIVERED,
    EventType.NOTIFICATION_REPLY_RECEIVED,
    EventType.MIGRATION_JOB_STARTED,
    EventType.MIGRATION_JOB_COMPLETED,
    EventType.MIGRATION_JOB_FAILED,
    EventType.MIGRATION_BINARY_RESOLVED,
    EventType.MIGRATION_ENTITY_PERSISTED,
    EventType.RECALL_DUE,
    EventType.BUDGET_VIEWED,
    EventType.COPILOT_SESSION_STARTED,
    EventType.COPILOT_SESSION_ENDED,
    EventType.COPILOT_TOOL_INVOKED,
    EventType.COPILOT_BUDGET_THRESHOLD_REACHED,
    EventType.COPILOT_DIGEST_SENT,
    EventType.VERIFACTU_RECORD_REJECTED,
    # High-frequency, low-signal odontogram surface edits -- the
    # higher-level tooth/condition/treatment events are still tracked.
    EventType.ODONTOGRAM_SURFACE_UPDATED,
}

# payload keys (in priority order) that identify the affected entity when
# no explicit entity_type/entity_id pair is present.
_ENTITY_ID_KEYS = (
    "patient_id",
    "appointment_id",
    "budget_id",
    "invoice_id",
    "payment_id",
    "document_id",
    "recall_id",
    "treatment_plan_id",
    "clinical_note_id",
    "credit_note_id",
)


def _entity_from_payload(payload: dict[str, Any]) -> tuple[str | None, str | None]:
    if "entity_type" in payload:
        return payload["entity_type"], (
            str(payload["entity_id"]) if payload.get("entity_id") is not None else None
        )
    for key in _ENTITY_ID_KEYS:
        if payload.get(key) is not None:
            return key[: -len("_id")], str(payload[key])
    return None, None


async def _log_event(event_name: str, payload: dict[str, Any]) -> None:
    clinic_id_raw = payload.get("clinic_id")
    if clinic_id_raw is None:
        # No tenant context -- nothing sensible to log against.
        return
    clinic_id = uuid.UUID(str(clinic_id_raw))

    user_id_raw = (
        payload.get("user_id") or payload.get("performed_by") or payload.get("actor_id")
    )
    user_id = uuid.UUID(str(user_id_raw)) if user_id_raw else None

    entity_type, entity_id = _entity_from_payload(payload)

    async with async_session_maker() as db:
        await create_log_entry(
            db,
            clinic_id=clinic_id,
            action_type=event_name,
            user_id=user_id,
            entity_type=entity_type,
            entity_id=entity_id,
            details=payload,
        )


def _tracked_event_types() -> list[str]:
    return [
        value
        for name, value in vars(EventType).items()
        if not name.startswith("_") and isinstance(value, str) and value not in _SKIP_EVENTS
    ]


def make_activity_handlers() -> dict[str, Callable[[dict[str, Any]], Awaitable[None]]]:
    """Map every tracked EventType to the same generic journal handler."""
    handlers: dict[str, Callable[[dict[str, Any]], Awaitable[None]]] = {}

    for event_name in _tracked_event_types():

        async def _handler(payload: dict[str, Any], _event_name: str = event_name) -> None:
            await _log_event(_event_name, payload)

        handlers[event_name] = _handler

    return handlers
