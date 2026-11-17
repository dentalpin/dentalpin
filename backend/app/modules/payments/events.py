"""Event handlers consumed by the payments module.

Earned entries are keyed on ``(treatment_id, source_session_id)``:

- ``odontogram.treatment.performed`` and the legacy
  ``treatment_plan.treatment_completed`` handler still upsert with
  ``source_session_id = NULL`` (single-session semantics).
- ``treatment_plan.item_session_completed`` upserts one row per
  session — multi-session treatments thus produce N rows whose
  amounts add up to the treatment price.

Idempotency: the composite unique constraint dedupes session rows and
the partial index ``uq_earned_treatment_null_session`` dedupes the
NULL-session row (plain unique constraints treat NULLs as distinct).

Exclusivity between the two paths is the *publishers'* responsibility,
not reconciled here: when treatment_plan finalizes a sessioned item it
calls ``perform(publish_price=False)`` so the performed event carries
``unit_price: None`` (skipped below); when the odontogram performs
first, treatment_plan cancels the item's pending sessions so session
events can never fire on top of the NULL row.

Both handlers are **transactional** (ADR 0019): revenue is booked in the
same transaction as the treatment that earned it. On their own session they
committed independently, so a request that failed after the publish left an
earned entry for a treatment that never existed — and ``treatment_id``
carries no FK to stop it (issue #183).
"""

from __future__ import annotations

import logging
from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from .models import PatientEarnedEntry

logger = logging.getLogger(__name__)


def _parse_uuid(value: Any) -> UUID | None:
    if value is None:
        return None
    if isinstance(value, UUID):
        return value
    try:
        return UUID(str(value))
    except (ValueError, TypeError):
        return None


def _parse_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


def _parse_amount(value: Any) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except Exception:
        return None


async def _upsert_earned_entry(
    data: dict[str, Any],
    source_event: str,
    *,
    db: AsyncSession,
    source_session_id: UUID | None = None,
    amount_override: Any = None,
    description: str | None = None,
    performed_at_override: Any = None,
) -> None:
    clinic_id = _parse_uuid(data.get("clinic_id"))
    patient_id = _parse_uuid(data.get("patient_id"))
    treatment_id = _parse_uuid(data.get("treatment_id"))
    performed_at = _parse_datetime(
        performed_at_override
        if performed_at_override is not None
        else (data.get("performed_at") or data.get("occurred_at"))
    )
    if amount_override is not None:
        amount = _parse_amount(amount_override)
    else:
        amount = _parse_amount(data.get("unit_price") or data.get("price_snapshot"))

    if not (clinic_id and patient_id and treatment_id and performed_at):
        logger.debug(
            "%s: missing required fields, skipping earned upsert (data=%s)",
            source_event,
            data,
        )
        return
    if amount is None:
        logger.info(
            "%s: no amount in payload, skipping (treatment_id=%s)",
            source_event,
            treatment_id,
        )
        return

    catalog_item_id = _parse_uuid(data.get("catalog_item_id"))
    professional_id = _parse_uuid(data.get("performed_by") or data.get("professional_id"))

    stmt = (
        pg_insert(PatientEarnedEntry)
        .values(
            clinic_id=clinic_id,
            patient_id=patient_id,
            treatment_id=treatment_id,
            catalog_item_id=catalog_item_id,
            source_session_id=source_session_id,
            description=description,
            amount=amount,
            performed_at=performed_at,
            professional_id=professional_id,
            source_event=source_event,
        )
        # Bare form: swallows conflicts on the composite constraint
        # AND the partial NULL-session index alike.
        .on_conflict_do_nothing()
    )
    await db.execute(stmt)


async def on_treatment_performed(data: dict[str, Any], *, db: AsyncSession) -> None:
    """Handler for ``odontogram.treatment.performed`` (single-session row).

    The NULL-session row books what the treatment's sessions have not booked
    yet. Performing a sessioned treatment on the odontogram after one of its
    sessions was completed would otherwise book that session's money twice:
    the event carries the full price, and treatment_plan only cancels the
    *pending* sessions (#891).
    """
    amount = _parse_amount(data.get("unit_price") or data.get("price_snapshot"))
    treatment_id = _parse_uuid(data.get("treatment_id"))
    clinic_id = _parse_uuid(data.get("clinic_id"))
    if amount is not None and treatment_id and clinic_id:
        booked = (
            await db.execute(
                select(func.coalesce(func.sum(PatientEarnedEntry.amount), 0)).where(
                    PatientEarnedEntry.clinic_id == clinic_id,
                    PatientEarnedEntry.treatment_id == treatment_id,
                    PatientEarnedEntry.source_session_id.is_not(None),
                )
            )
        ).scalar_one()
        if booked:
            remaining = amount - Decimal(booked)
            if remaining <= 0:
                logger.info(
                    "odontogram.treatment.performed: sessions already booked %s of %s, "
                    "skipping (treatment_id=%s)",
                    booked,
                    amount,
                    treatment_id,
                )
                return
            await _upsert_earned_entry(
                data,
                source_event="odontogram.treatment.performed",
                db=db,
                amount_override=remaining,
            )
            return
    await _upsert_earned_entry(data, source_event="odontogram.treatment.performed", db=db)


async def on_session_completed(data: dict[str, Any], *, db: AsyncSession) -> None:
    """Handler for ``treatment_plan.item_session_completed``.

    Books a per-session earned row keyed on ``(treatment_id,
    source_session_id)``. Treatments without a session_id (legacy single
    completion through ``odontogram.treatment.performed``) live on a
    separate row whose ``source_session_id`` is NULL.
    """
    session_id = _parse_uuid(data.get("session_id"))
    description = data.get("label")
    await _upsert_earned_entry(
        data,
        source_event="treatment_plan.item_session_completed",
        db=db,
        source_session_id=session_id,
        amount_override=data.get("amount"),
        description=description if isinstance(description, str) else None,
        performed_at_override=data.get("occurred_at"),
    )
