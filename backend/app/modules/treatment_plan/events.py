"""Treatment plan module event handlers.

Listens to events from other modules and reacts accordingly.
"""

import logging
from typing import Any
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.events import event_bus
from app.database import async_session_maker

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


async def on_appointment_completed(data: dict[str, Any]) -> None:
    """Handle appointment completed event.

    When an appointment is completed, mark associated planned treatments as completed.
    """
    appointment_id = data.get("appointment_id")
    clinic_id = data.get("clinic_id")

    if not appointment_id or not clinic_id:
        logger.warning("on_appointment_completed: missing appointment_id or clinic_id")
        return

    async with async_session_maker() as db:
        try:
            # Import here to avoid circular imports
            from app.modules.agenda.models import AppointmentTreatment

            # Get completed treatments from the appointment
            result = await db.execute(
                select(AppointmentTreatment).where(
                    AppointmentTreatment.appointment_id == UUID(appointment_id),
                    AppointmentTreatment.completed_in_appointment == True,  # noqa: E712
                )
            )
            completed_treatments = result.scalars().all()

            for apt_treatment in completed_treatments:
                # Find planned item that references this treatment
                if apt_treatment.planned_treatment_item_id:
                    item_result = await db.execute(
                        select(PlannedTreatmentItem).where(
                            PlannedTreatmentItem.id == apt_treatment.planned_treatment_item_id,
                            PlannedTreatmentItem.clinic_id == UUID(clinic_id),
                        )
                    )
                    item = item_result.scalar_one_or_none()

                    if item and item.status != "completed":
                        item.status = "completed"
                        item.completed_without_appointment = False

                        category_key = await _resolve_treatment_category_key(db, item.treatment_id)
                        await event_bus.publish(
                            "treatment_plan.treatment_completed",
                            {
                                "plan_id": str(item.treatment_plan_id),
                                "item_id": str(item.id),
                                "treatment_id": str(item.treatment_id),
                                "clinic_id": clinic_id,
                                "patient_id": data.get("patient_id"),
                                "triggered_by": "appointment_completed",
                                "treatment_category_key": category_key,
                            },
                        )

                        # Check if plan should auto-complete
                        from .service import TreatmentPlanService

                        await TreatmentPlanService._check_and_complete_plan(
                            db, UUID(clinic_id), item.treatment_plan_id
                        )

            await db.commit()
            logger.info(
                f"Processed appointment completion for {len(completed_treatments)} treatments"
            )

        except Exception as e:
            logger.error(f"Error processing appointment completion: {e}", exc_info=True)
            await db.rollback()


async def on_budget_accepted(data: dict[str, Any]) -> None:
    """Activate the linked plan when its budget is accepted.

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

    async with async_session_maker() as db:
        try:
            await TreatmentPlanService.accept_from_budget(db, UUID(clinic_id), UUID(plan_id))
            await db.commit()
        except Exception as e:
            logger.error(f"Error processing budget acceptance: {e}", exc_info=True)
            await db.rollback()


async def on_budget_rejected(data: dict[str, Any]) -> None:
    """Close the linked plan with ``rejected_by_patient`` when the
    patient rejects the budget. Idempotent.
    """
    clinic_id = data.get("clinic_id")
    plan_id = data.get("plan_id")
    note = data.get("rejection_note")

    if not clinic_id or not plan_id:
        return

    from .service import TreatmentPlanService

    async with async_session_maker() as db:
        try:
            await TreatmentPlanService.reject_from_budget(
                db, UUID(clinic_id), UUID(plan_id), rejection_note=note
            )
            await db.commit()
        except Exception as e:
            logger.error(f"Error processing budget rejection: {e}", exc_info=True)
            await db.rollback()


async def on_budget_renegotiated(data: dict[str, Any]) -> None:
    """Reopen the linked plan back to ``draft`` when reception
    cancels a sent budget for renegotiation.

    Uses ``reopen_from_budget``, which never writes the budget row:
    the publisher's still-open transaction holds a lock on it, and the
    bus awaits handlers inline — calling ``reopen()`` here (which
    cancels the budget) would hang on that lock.
    """
    clinic_id = data.get("clinic_id")
    plan_id = data.get("plan_id")

    if not clinic_id or not plan_id:
        return

    from .service import TreatmentPlanService

    async with async_session_maker() as db:
        try:
            await TreatmentPlanService.reopen_from_budget(db, UUID(clinic_id), UUID(plan_id))
            await db.commit()
        except Exception as e:
            logger.error(f"Error processing budget renegotiation: {e}", exc_info=True)
            await db.rollback()


async def on_budget_cancelled(data: dict[str, Any]) -> None:
    """Reopen the linked pending plan to ``draft`` when staff cancels
    its budget directly from the budgets module (issue #162).

    Idempotent: non-pending plans are a warn + no-op inside
    ``reopen_from_budget``. Standalone budgets carry no ``plan_id``.
    """
    clinic_id = data.get("clinic_id")
    plan_id = data.get("plan_id")

    if not clinic_id or not plan_id:
        return

    from .service import TreatmentPlanService

    async with async_session_maker() as db:
        try:
            await TreatmentPlanService.reopen_from_budget(db, UUID(clinic_id), UUID(plan_id))
            await db.commit()
        except Exception as e:
            logger.error(f"Error processing budget cancellation: {e}", exc_info=True)
            await db.rollback()


async def on_budget_superseded(data: dict[str, Any]) -> None:
    """Repoint the plan's budget link when a terminal budget is cloned
    to a new draft version ("Resend", issue #162).

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

    async with async_session_maker() as db:
        try:
            plan = await TreatmentPlanService.get(db, UUID(clinic_id), UUID(plan_id))
            if plan and str(plan.budget_id) == old_budget_id:
                plan.budget_id = UUID(new_budget_id)
                await db.commit()
        except Exception as e:
            logger.error(f"Error processing budget supersede: {e}", exc_info=True)
            await db.rollback()


async def on_treatment_performed(data: dict[str, Any]) -> None:
    """Handle treatment performed from odontogram.

    Mark the corresponding planned item as completed when the odontogram performs
    a Treatment that belongs to an active plan item.
    """
    treatment_id = data.get("treatment_id")
    clinic_id = data.get("clinic_id")

    if not treatment_id or not clinic_id:
        logger.warning("on_treatment_performed: missing treatment_id or clinic_id")
        return

    async with async_session_maker() as db:
        try:
            # ``SKIP LOCKED`` avoids a deadlock when this handler runs as a
            # sub-step of ``TreatmentPlanService.complete_item``: the parent
            # transaction already holds a row lock on this item (it flushed
            # its own ``status='completed'`` UPDATE before publishing the
            # event). Without ``SKIP LOCKED`` the handler would open a new
            # session, block waiting for the parent to commit, and the
            # parent would block waiting for this handler to return —
            # surfaced as a request timeout in the client. When the lock is
            # held we treat the originator as responsible for the
            # state transition and exit silently; the parent's UPDATE
            # achieves the same end state.
            result = await db.execute(
                select(PlannedTreatmentItem)
                .where(
                    PlannedTreatmentItem.treatment_id == UUID(treatment_id),
                    PlannedTreatmentItem.clinic_id == UUID(clinic_id),
                    PlannedTreatmentItem.status == "pending",
                )
                .with_for_update(skip_locked=True)
            )
            item = result.scalar_one_or_none()

            if item:
                item.status = "completed"
                item.completed_without_appointment = True

                # The odontogram-performed event already carried the full
                # price to the payments earned ledger. Cancel the item's
                # pending sessions (no session events) so they can't be
                # completed later and book the same money a second time.
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
                    "treatment_plan.treatment_completed",
                    {
                        "plan_id": str(item.treatment_plan_id),
                        "item_id": str(item.id),
                        "treatment_id": treatment_id,
                        "clinic_id": clinic_id,
                        "patient_id": data.get("patient_id"),
                        "triggered_by": "odontogram_performed",
                        "treatment_category_key": category_key,
                    },
                )

                from .service import TreatmentPlanService

                await TreatmentPlanService._check_and_complete_plan(
                    db, UUID(clinic_id), item.treatment_plan_id
                )

                await db.commit()
                logger.info("Marked planned item %s as completed from odontogram", item.id)

        except Exception as e:
            logger.error("Error processing treatment performed: %s", e, exc_info=True)
            await db.rollback()
