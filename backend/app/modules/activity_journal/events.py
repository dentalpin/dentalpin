"""Transactional event handlers (ADR 0019) — the whole point of this module.

Every handler declares ``db``, so the bus treats it as transactional: the
row is flushed inside the *publisher's* transaction and committed (or
rolled back) with it. A handler failure aborts the publisher's operation
rather than silently losing the audit entry.

Subscription set: every EventType whose publishers all pass ``db=db``
(audited across ``app/``). Events published from non-transactional
contexts (gateways, background tasks, migration tooling — e.g.
``email.*``, ``copilot.*``, ``migration.*``, legacy odontogram updates)
are deliberately NOT subscribed: the bus raises RuntimeError when a
transactional handler receives no session, so subscribing to them would
crash those flows. See ``docs/technical/activity_journal/events.md`` for
the full inclusion/exclusion rationale.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from .models import ActivityJournalEntry

logger = logging.getLogger(__name__)

# Payload keys inspected for actor attribution, in priority order. Only
# keys that hold a *user* id across all subscribed publishers are listed
# (each ``*_by`` key below is a ``users.id`` FK or ``ctx.user_id`` at its
# publish site) — e.g. ``professional_id`` may point at a catalog
# professional rather than a user, so it is not listed.
_ACTOR_KEYS = (
    "user_id",
    "actor_id",
    "created_by",
    "changed_by",  # agenda status transitions
    "performed_by",  # odontogram.treatment.performed
    "deleted_by",  # odontogram.treatment.deleted
    "completed_by",  # treatment_plan.item_session_completed
    "refunded_by",  # payment.refunded
    "cancelled_by",  # budget.cancelled / budget.renegotiated
    "resent_by",  # budget.superseded
    "accepted_by",  # budget.accepted (ctx.user_id at the publish site)
    "recommended_by",  # recall.created
)

# Payload keys that identify the row the event is about (after
# clinic_id/patient_id/actor keys are excluded). First match wins.
_SOURCE_ID_SUFFIX = "_id"


def _uuid_or_none(value) -> UUID | None:
    """Parse loosely: these handlers run inside the publisher's
    transaction, so a malformed id must degrade to NULL rather than
    abort the business operation being audited."""
    if not value or not str(value).strip():
        return None
    try:
        return UUID(str(value))
    except ValueError:
        return None


def _source_table(event_type_value: str) -> str:
    """``appointment.scheduled`` -> ``appointment`` (the event namespace)."""
    return event_type_value.split(".", 1)[0]


def _parse_occurred_at(data: dict) -> datetime:
    raw = data.get("occurred_at") or data.get("changed_at")
    if isinstance(raw, str):
        try:
            parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
        except ValueError:
            logger.warning("activity_journal: unparseable occurred_at %r", raw)
    if isinstance(raw, datetime):
        return raw if raw.tzinfo else raw.replace(tzinfo=UTC)
    return datetime.now(UTC)


def make_handler(event_type_value: str):
    """Build a transactional handler bound to one event type value."""

    async def _record(data: dict, db: AsyncSession) -> None:
        # A treatment created atomically for a plan is represented by the
        # treatment_plan.treatment_added event below; avoid duplicate rows.
        if (
            event_type_value == "odontogram.treatment.added"
            and data.get("source_module") == "treatment_plan"
        ):
            return

        clinic_id = _uuid_or_none(data.get("clinic_id"))
        if clinic_id is None:
            # A journal row without a clinic cannot be scoped or isolated;
            # skip instead of crashing the publisher's business operation.
            logger.warning(
                "activity_journal: %s payload without valid clinic_id — skipped",
                event_type_value,
            )
            return

        actor_id = next(
            (aid for k in _ACTOR_KEYS if (aid := _uuid_or_none(data.get(k))) is not None),
            None,
        )

        patient_id = _uuid_or_none(data.get("patient_id"))

        source_entity_id = next(
            (
                sid
                for key, value in data.items()
                if key.endswith(_SOURCE_ID_SUFFIX)
                and key not in ("clinic_id", "patient_id", *_ACTOR_KEYS)
                and (sid := _uuid_or_none(value)) is not None
            ),
            None,
        )
        # Patient-only events (e.g. patient.created) carry no separate
        # entity id — the row is about the patient itself.
        source_entity_id = source_entity_id or patient_id

        db.add(
            ActivityJournalEntry(
                clinic_id=clinic_id,
                event_type=event_type_value,
                actor_id=actor_id,
                patient_id=patient_id,
                source_table=_source_table(event_type_value),
                source_entity_id=source_entity_id,
                payload=dict(data),
                occurred_at=_parse_occurred_at(data),
            )
        )
        # flush, never commit — ADR 0019 transactional handler.

    _record.__name__ = f"on_{event_type_value.replace('.', '_')}"
    _record.__qualname__ = _record.__name__
    return _record


def build_handlers(event_types) -> dict:
    """Map each EventType constant to its transactional handler."""
    return {et: make_handler(et.value if hasattr(et, "value") else str(et)) for et in event_types}
