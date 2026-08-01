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
"""

from __future__ import annotations

import logging
from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.database import async_session_maker

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

    async with async_session_maker() as db:
        try:
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
            await db.commit()
        except Exception as exc:  # pragma: no cover - defensive
            logger.error("Failed to upsert PatientEarnedEntry: %s", exc, exc_info=True)
            await db.rollback()


async def on_treatment_performed(data: dict[str, Any]) -> None:
    """Handler for ``odontogram.treatment.performed`` (single-session row)."""
    await _upsert_earned_entry(data, source_event="odontogram.treatment.performed")


async def on_session_completed(data: dict[str, Any]) -> None:
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
        source_session_id=session_id,
        amount_override=data.get("amount"),
        description=description if isinstance(description, str) else None,
        performed_at_override=data.get("occurred_at"),
    )
