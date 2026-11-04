"""Recalls module event subscribers.

Reacts to lifecycle events from ``patients``, ``agenda`` and
``treatment_plan``. All cross-module data is consumed via event
payloads — recalls never imports another module's models, except
``Patient`` (which is in ``manifest.depends``) for read-side queries.

Registered in :class:`~app.modules.recalls.RecallsModule.get_event_handlers`.

All state-changing handlers here are **transactional** (ADR 0019): they
declare ``db`` and run inside the publisher's session. A recall's link to an
appointment is an FK to ``appointments.id``, so an own-session handler cannot
even write it before the publisher commits — the row is invisible to a second
connection and the FK check fails (issue #183). Running in-tx also keeps the
recall's state and the appointment's state from diverging when one of them
rolls back.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import Recall
from .service import RecallClosedError, RecallService, RecallSettingsService

logger = logging.getLogger(__name__)


def _safe_uuid(raw: Any) -> UUID | None:
    if raw is None:
        return None
    if isinstance(raw, UUID):
        return raw
    try:
        return UUID(str(raw))
    except (ValueError, TypeError):
        return None


async def on_appointment_scheduled(data: dict[str, Any], *, db: AsyncSession) -> None:
    """Auto-link a pending recall to the new appointment when the
    clinic's setting allows it.

    Transactional: ``Recall.linked_appointment_id`` is an FK to the
    appointment the publisher has only flushed, so this has to run on the
    publisher's session.

    Match policy (V1): same patient + the appointment date is on or
    after the recall's ``due_month`` (which is day-1 of the target
    month). Reason match is best-effort since agenda's
    ``treatment_type`` is free-text — we don't gate on it.
    """
    appointment_id = _safe_uuid(data.get("appointment_id"))
    clinic_id = _safe_uuid(data.get("clinic_id"))
    patient_id = _safe_uuid(data.get("patient_id"))
    start_time_raw = data.get("start_time")
    if not (appointment_id and clinic_id and patient_id and start_time_raw):
        return

    try:
        start_time = (
            start_time_raw
            if isinstance(start_time_raw, datetime)
            else datetime.fromisoformat(str(start_time_raw))
        )
    except (TypeError, ValueError):
        return

    settings = await RecallSettingsService.get_or_create(db, clinic_id)
    if not settings.auto_link_on_appointment_scheduled:
        return
    await RecallService.auto_link_for_appointment(
        db,
        clinic_id=clinic_id,
        patient_id=patient_id,
        appointment_id=appointment_id,
        appointment_date=start_time.date(),
    )


async def on_appointment_completed(data: dict[str, Any], *, db: AsyncSession) -> None:
    """If a recall was linked to the completed appointment, mark it done.

    Transactional: the recall closes with the appointment or not at all.
    """
    appointment_id = _safe_uuid(data.get("appointment_id"))
    clinic_id = _safe_uuid(data.get("clinic_id"))
    if not (appointment_id and clinic_id):
        return

    result = await db.execute(
        select(Recall).where(
            Recall.clinic_id == clinic_id,
            Recall.linked_appointment_id == appointment_id,
            Recall.status.in_(("contacted_scheduled", "pending")),
        )
    )
    for recall in result.scalars().all():
        try:
            await RecallService.mark_done(
                db,
                clinic_id=clinic_id,
                recall_id=recall.id,
                by_user=None,
                commit=False,
            )
        except RecallClosedError:
            # Closed by someone else after the query above; nothing to do.
            continue


async def on_appointment_cancelled(data: dict[str, Any], *, db: AsyncSession) -> None:
    """Unlink the cancelled appointment from any recall and revert
    the recall to ``pending`` so it shows up on the call list again.

    Transactional: leaving a recall pointing at a cancelled appointment
    (or freeing it for a cancellation that rolled back) both put the call
    list out of sync with the agenda.
    """
    appointment_id = _safe_uuid(data.get("appointment_id"))
    clinic_id = _safe_uuid(data.get("clinic_id"))
    if not (appointment_id and clinic_id):
        return

    result = await db.execute(
        select(Recall).where(
            Recall.clinic_id == clinic_id,
            Recall.linked_appointment_id == appointment_id,
        )
    )
    now = datetime.now(UTC)
    for recall in result.scalars().all():
        if recall.status in ("done", "cancelled"):
            continue
        recall.linked_appointment_id = None
        if recall.status == "contacted_scheduled":
            recall.status = "pending"
        recall.updated_at = now


async def on_treatment_plan_completed(data: dict[str, Any]) -> None:
    """Reserved hook for future analytics. The actual suggestion is
    pulled by the frontend via ``GET /recalls/suggestions/next``;
    keeping the handler stateless avoids race conditions and stale
    suggestion rows when the user dismisses a hint.

    The handler still runs so module manifests / event catalogs stay
    consistent and so we have a place to extend later (e.g. notify a
    pro of upcoming auto-suggestions). For now it just logs.

    own-session: payload-only, no DB access at all.
    """
    if not data.get("treatment_category_key"):
        return
    logger.debug(
        "recalls.on_treatment_plan_completed: clinic=%s patient=%s category=%s",
        data.get("clinic_id"),
        data.get("patient_id"),
        data.get("treatment_category_key"),
    )


async def on_patient_archived(data: dict[str, Any], *, db: AsyncSession) -> None:
    """Move active recalls to the ``needs_review`` bucket when the
    patient is archived. Never deletes — the call list filter keeps
    them out of the active queue while preserving history.

    Transactional: this is a cascade of the archive, so it lives or dies
    with it. Otherwise a failed archive leaves the recalls parked.
    """
    patient_id = _safe_uuid(data.get("patient_id"))
    clinic_id = _safe_uuid(data.get("clinic_id"))
    if not patient_id:
        return

    stmt = select(Recall).where(
        Recall.patient_id == patient_id,
        Recall.status.in_(("pending", "contacted_no_answer", "contacted_scheduled")),
    )
    if clinic_id:
        stmt = stmt.where(Recall.clinic_id == clinic_id)
    result = await db.execute(stmt)
    now = datetime.now(UTC)
    for recall in result.scalars().all():
        recall.status = "needs_review"
        recall.updated_at = now
