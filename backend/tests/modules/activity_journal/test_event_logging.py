"""activity_journal: transactional event-handler behaviour (ADR 0019).

The handlers must write inside the publisher's transaction: a commit
persists the row, a rollback discards it. That is the whole value of the
module, so it is pinned here explicitly.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic
from app.core.events.bus import _wants_db, event_bus
from app.core.events.types import EventType
from app.modules.activity_journal.__init__ import _SUBSCRIBED, build_handlers
from app.modules.activity_journal.models import ActivityJournalEntry


@pytest.mark.asyncio
async def test_every_subscribed_handler_is_transactional():
    """A non-transactional handler here would silently lose audit rows on
    publisher failure — ADR 0019 forbids it for this module."""
    for handler in build_handlers(_SUBSCRIBED).values():
        assert _wants_db(handler), handler


@pytest.mark.asyncio
async def test_publish_commit_persists_row(db_session: AsyncSession, test_clinic: Clinic):
    await event_bus.publish(
        EventType.PATIENT_CREATED,
        {
            "clinic_id": str(test_clinic.id),
            "patient_id": str(uuid4()),
            "user_id": str(uuid4()),
        },
        db=db_session,
    )
    # flushed into the publisher's transaction — visible before commit.
    stmt = select(ActivityJournalEntry).where(ActivityJournalEntry.clinic_id == test_clinic.id)
    rows = (await db_session.execute(stmt)).scalars().all()
    assert len(rows) == 1
    entry = rows[0]
    assert entry.event_type == "patient.created"
    assert entry.source_table == "patient"
    assert entry.source_entity_id is not None
    assert entry.actor_id is not None
    assert entry.payload["clinic_id"] == str(test_clinic.id)
    await db_session.commit()

    rows = (await db_session.execute(stmt)).scalars().all()
    assert len(rows) == 1  # survives the commit


@pytest.mark.asyncio
async def test_publisher_rollback_discards_row(db_session: AsyncSession, test_clinic: Clinic):
    # Capture before publish/rollback: rollback expires ORM objects and
    # touching an expired attribute afterwards raises MissingGreenlet.
    clinic_id = test_clinic.id
    await event_bus.publish(
        EventType.RECALL_CREATED,
        {
            "clinic_id": str(clinic_id),
            "recall_id": str(uuid4()),
            "patient_id": str(uuid4()),
        },
        db=db_session,
    )
    await db_session.rollback()

    stmt = select(ActivityJournalEntry).where(ActivityJournalEntry.clinic_id == clinic_id)
    rows = (await db_session.execute(stmt)).scalars().all()
    assert rows == []


@pytest.mark.asyncio
async def test_payload_without_clinic_is_skipped_not_fatal(db_session: AsyncSession):
    """A journal row cannot be scoped without a clinic — skip instead of
    crashing the publisher's business operation."""
    await event_bus.publish(
        EventType.PATIENT_CREATED,
        {"patient_id": str(uuid4())},
        db=db_session,
    )
    rows = (await db_session.execute(select(ActivityJournalEntry))).scalars().all()
    assert rows == []


@pytest.mark.asyncio
async def test_occurred_at_and_actor_attribution(db_session: AsyncSession, test_clinic: Clinic):
    await event_bus.publish(
        EventType.APPOINTMENT_SCHEDULED,
        {
            "clinic_id": str(test_clinic.id),
            "appointment_id": str(uuid4()),
            "actor_id": str(uuid4()),
            # ``start_time`` on this payload is a *future* visit time and is
            # deliberately NOT used as the journal timestamp; an explicit
            # occurred_at wins, else the handler stamps now().
            "occurred_at": "2026-08-20T09:30:00+00:00",
        },
        db=db_session,
    )
    entry = (
        (
            await db_session.execute(
                select(ActivityJournalEntry).where(ActivityJournalEntry.clinic_id == test_clinic.id)
            )
        )
        .scalars()
        .one()
    )
    assert entry.occurred_at == datetime(2026, 8, 20, 9, 30, tzinfo=UTC)
    assert entry.actor_id is not None


@pytest.mark.asyncio
async def test_actor_attribution_from_by_suffixed_keys(
    db_session: AsyncSession, test_clinic: Clinic
):
    """Most publishers carry the acting user under a ``*_by`` key
    (``changed_by``, ``performed_by``, ...) rather than ``user_id`` —
    pin that those attribute the row (the whole point of the Actor
    column)."""
    actor = uuid4()
    await event_bus.publish(
        EventType.APPOINTMENT_CONFIRMED,
        {
            "clinic_id": str(test_clinic.id),
            "appointment_id": str(uuid4()),
            "changed_by": str(actor),
        },
        db=db_session,
    )
    entry = (
        (
            await db_session.execute(
                select(ActivityJournalEntry).where(ActivityJournalEntry.clinic_id == test_clinic.id)
            )
        )
        .scalars()
        .one()
    )
    assert entry.actor_id == actor


@pytest.mark.asyncio
async def test_odontogram_treatment_delete_is_recorded_for_admin_journal(
    db_session: AsyncSession, test_clinic: Clinic
):
    actor = uuid4()
    await event_bus.publish(
        EventType.ODONTOGRAM_TREATMENT_DELETED,
        {
            "clinic_id": str(test_clinic.id),
            "patient_id": str(uuid4()),
            "treatment_id": str(uuid4()),
            "deleted_by": str(actor),
        },
        db=db_session,
    )
    entry = (
        (
            await db_session.execute(
                select(ActivityJournalEntry).where(ActivityJournalEntry.clinic_id == test_clinic.id)
            )
        )
        .scalars()
        .one()
    )
    assert entry.event_type == "odontogram.treatment.deleted"
    assert entry.actor_id == actor


@pytest.mark.asyncio
async def test_malformed_ids_degrade_to_null_not_crash(
    db_session: AsyncSession, test_clinic: Clinic
):
    """A malformed actor/patient id in a payload must never abort the
    publisher's transaction — the row is written with NULLs instead."""
    await event_bus.publish(
        EventType.PATIENT_CREATED,
        {
            "clinic_id": str(test_clinic.id),
            "patient_id": "not-a-uuid",
            "user_id": "system",
        },
        db=db_session,
    )
    entry = (
        (
            await db_session.execute(
                select(ActivityJournalEntry).where(ActivityJournalEntry.clinic_id == test_clinic.id)
            )
        )
        .scalars()
        .one()
    )
    assert entry.actor_id is None
    assert entry.patient_id is None
    assert entry.payload["patient_id"] == "not-a-uuid"
