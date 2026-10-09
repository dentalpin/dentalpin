"""Treatment plan module event handlers.

Listens to events from other modules and reacts accordingly.

Every handler here is **transactional** (ADR 0019): it declares ``db`` and
runs inside the publisher's session. The plan mirrors budget and agenda
state, so the two have to move together — on its own session a handler read
rows the publisher had only flushed (stale), competed for locks with it, and
committed changes the publisher could still roll back (issue #183).

A handler that publishes forwards its ``db`` so subscribers further down the
chain keep the same guarantee.
"""

import logging
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.events import event_bus
from app.core.events.types import EventType

from .models import PlannedTreatmentItem, PlannedTreatmentItemSession

logger = logging.getLogger(__name__)


async def _resolve_treatment_category_key(db: AsyncSession, treatment_id: UUID) -> str | None:
    """Look up the catalog category key for a Treatment.

    Used to enrich ``treatment_plan.treatment_completed`` payloads so
    sibling modules (e.g. ``recalls``) can map the completed treatment
    to a recall reason without importing catalog or treatment_plan
    models. ``odontogram`` and ``catalog`` are in this module's
    ``depends``, so the read is permitted.
    """
    from app.modules.catalog.models import TreatmentCatalogItem, TreatmentCategory
    from app.modules.odontogram.models import Treatment

    result = await db.execute(
        select(TreatmentCategory.key)
        .join(
            TreatmentCatalogItem,
            TreatmentCatalogItem.category_id == TreatmentCategory.id,
        )
        .join(Treatment, Treatment.catalog_item_id == TreatmentCatalogItem.id)
        .where(Treatment.id == treatment_id)
    )
    return result.scalar_one_or_none()


async def on_appointment_completed(data: dict[str, Any], *, db: AsyncSession) -> None:
    """Handle appointment completed event.

    When an appointment is completed, mark associated planned treatments as
    completed. Transactional: it reads ``completed_in_appointment`` flags the
    publisher has only flushed — a second session saw the pre-visit values and
    closed nothing (issue #183).
    """
    appointment_id = data.get("appointment_id")
    clinic_id = data.get("clinic_id")

    if not appointment_id or not clinic_id:
        logger.warning("on_appointment_completed: missing appointment_id or clinic_id")
        return

    # Import here to avoid circular imports
    from .models import AppointmentTreatment
    from .service import TreatmentPlanService

    result = await db.execute(
        select(AppointmentTreatment).where(
            AppointmentTreatment.appointment_id == UUID(appointment_id),
            AppointmentTreatment.completed_in_appointment == True,  # noqa: E712
        )
    )
    completed_treatments = result.scalars().all()

    for apt_treatment in completed_treatments:
        # Find planned item that references this treatment
        if not apt_treatment.planned_treatment_item_id:
            continue
        item_result = await db.execute(
            select(PlannedTreatmentItem).where(
                PlannedTreatmentItem.id == apt_treatment.planned_treatment_item_id,
                PlannedTreatmentItem.clinic_id == UUID(clinic_id),
            )
        )
        item = item_result.scalar_one_or_none()
        if not item or item.status == "completed":
            continue

        item.status = "completed"
        item.completed_without_appointment = False

        category_key = await _resolve_treatment_category_key(db, item.treatment_id)
        await event_bus.publish(
            EventType.TREATMENT_PLAN_TREATMENT_COMPLETED,
            {
                "plan_id": str(item.treatment_plan_id),
                "item_id": str(item.id),
                "treatment_id": str(item.treatment_id),
                "clinic_id": clinic_id,
                "patient_id": data.get("patient_id"),
                "triggered_by": "appointment_completed",
                "treatment_category_key": category_key,
            },
            db=db,
        )

        # Check if plan should auto-complete
        await TreatmentPlanService._check_and_complete_plan(
            db, UUID(clinic_id), item.treatment_plan_id
        )

    logger.info("Processed appointment completion for %d treatments", len(completed_treatments))


async def on_budget_accepted(data: dict[str, Any], *, db: AsyncSession) -> None:
    """Activate the linked plan when its budget is accepted.

    Transactional: an accepted budget whose plan failed to activate is a
    silent divergence between the two modules — the error used to be logged
    and swallowed.

    Idempotent: ``TreatmentPlanService.accept_from_budget`` is a no-op
    when the plan is already active. The plan_id is read from the
    snapshot payload so we never need to query treatment_plan from a
    different module's perspective.
    """
    budget_id = data.get("budget_id")
    clinic_id = data.get("clinic_id")
    plan_id = data.get("plan_id")

    if not budget_id or not clinic_id:
        logger.warning("on_budget_accepted: missing budget_id or clinic_id")
        return
    if not plan_id:
        # Nothing to activate (orphan budget).
        return

    from .service import TreatmentPlanService

    # Snapshot of the accepted lines: ex-tax net amount per treatment.
    line_amounts = {
        UUID(i["treatment_id"]): Decimal(i["net_amount"])
        for i in data.get("items") or []
        if i.get("treatment_id") and i.get("net_amount") is not None
    }

    await TreatmentPlanService.accept_from_budget(db, UUID(clinic_id), UUID(plan_id), line_amounts)


async def on_budget_rejected(data: dict[str, Any], *, db: AsyncSession) -> None:
    """Close the linked plan with ``rejected_by_patient`` when the
    patient rejects the budget. Idempotent.

    Transactional: plan and budget must not disagree about the rejection.
    """
    clinic_id = data.get("clinic_id")
    plan_id = data.get("plan_id")
    note = data.get("rejection_note")

    if not clinic_id or not plan_id:
        return

    from .service import TreatmentPlanService

    await TreatmentPlanService.reject_from_budget(
        db, UUID(clinic_id), UUID(plan_id), rejection_note=note
    )


async def on_budget_renegotiated(data: dict[str, Any], *, db: AsyncSession) -> None:
    """Reopen the linked plan back to ``draft`` when reception
    cancels a sent budget for renegotiation.

    Uses ``reopen_from_budget``, which never writes the budget row: the
    publisher is already cancelling it, and ``reopen()`` would cancel it
    again and echo another ``budget.cancelled`` back into this module.
    """
    clinic_id = data.get("clinic_id")
    plan_id = data.get("plan_id")

    if not clinic_id or not plan_id:
        return

    from .service import TreatmentPlanService

    await TreatmentPlanService.reopen_from_budget(db, UUID(clinic_id), UUID(plan_id))


async def on_budget_cancelled(data: dict[str, Any], *, db: AsyncSession) -> None:
    """Reopen the linked pending plan to ``draft`` when staff cancels
    its budget directly from the budgets module (issue #162).

    Idempotent: non-pending plans are a warn + no-op inside
    ``reopen_from_budget``. Standalone budgets carry no ``plan_id``.

    Transactional: the plan reopens with the cancellation or not at all.
    """
    clinic_id = data.get("clinic_id")
    plan_id = data.get("plan_id")

    if not clinic_id or not plan_id:
        return

    from .service import TreatmentPlanService

    await TreatmentPlanService.reopen_from_budget(db, UUID(clinic_id), UUID(plan_id))


async def on_budget_superseded(data: dict[str, Any], *, db: AsyncSession) -> None:
    """Repoint the plan's budget link when a terminal budget is cloned
    to a new draft version ("Resend", issue #162).

    Transactional: ``treatment_plans.budget_id`` is an FK to the new budget
    row, which only exists inside the publisher's transaction. This used to
    force the publisher to commit before publishing (issue #183).

    Relinks only while the plan still points at the superseded budget —
    idempotent on redelivery, and a no-op if the plan already moved on
    (e.g. it was reactivated and re-confirmed onto a fresh budget).
    Plan status is deliberately untouched.
    """
    clinic_id = data.get("clinic_id")
    plan_id = data.get("plan_id")
    old_budget_id = data.get("budget_id")
    new_budget_id = data.get("new_budget_id")

    if not clinic_id or not plan_id or not old_budget_id or not new_budget_id:
        return

    from .service import TreatmentPlanService

    plan = await TreatmentPlanService.get(db, UUID(clinic_id), UUID(plan_id))
    if plan and str(plan.budget_id) == old_budget_id:
        plan.budget_id = UUID(new_budget_id)


async def on_treatment_performed(data: dict[str, Any], *, db: AsyncSession) -> None:
    """Handle treatment performed from odontogram.

    Mark the corresponding planned item as completed when the odontogram
    performs a Treatment that belongs to an active plan item.

    Transactional: this also runs as a sub-step of
    ``TreatmentPlanService.complete_item``, which has already flushed its own
    ``status='completed'`` UPDATE on this row. Sharing the publisher's session
    means sharing its locks, so there is nothing left to wait for — the old
    own-session version had to ``SKIP LOCKED`` past the row to avoid
    deadlocking against the publisher it was awaiting (issue #183).
    """
    treatment_id = data.get("treatment_id")
    clinic_id = data.get("clinic_id")

    if not treatment_id or not clinic_id:
        logger.warning("on_treatment_performed: missing treatment_id or clinic_id")
        return

    from .service import TreatmentPlanService

    result = await db.execute(
        select(PlannedTreatmentItem)
        .where(
            PlannedTreatmentItem.treatment_id == UUID(treatment_id),
            PlannedTreatmentItem.clinic_id == UUID(clinic_id),
            PlannedTreatmentItem.status == "pending",
        )
        .with_for_update()
    )
    item = result.scalar_one_or_none()
    if item is None:
        return

    item.status = "completed"
    item.completed_without_appointment = True

    # The odontogram-performed event already carried the full price to the
    # payments earned ledger. Cancel the item's pending sessions (no session
    # events) so they can't be completed later and book the same money a
    # second time.
    await db.execute(
        update(PlannedTreatmentItemSession)
        .where(
            PlannedTreatmentItemSession.plan_item_id == item.id,
            PlannedTreatmentItemSession.status == "pending",
        )
        .values(status="cancelled")
    )

    category_key = await _resolve_treatment_category_key(db, item.treatment_id)
    await event_bus.publish(
        EventType.TREATMENT_PLAN_TREATMENT_COMPLETED,
        {
            "plan_id": str(item.treatment_plan_id),
            "item_id": str(item.id),
            "treatment_id": treatment_id,
            "clinic_id": clinic_id,
            "patient_id": data.get("patient_id"),
            "triggered_by": "odontogram_performed",
            "treatment_category_key": category_key,
        },
        db=db,
    )

    await TreatmentPlanService._check_and_complete_plan(db, UUID(clinic_id), item.treatment_plan_id)
    logger.info("Marked planned item %s as completed from odontogram", item.id)
