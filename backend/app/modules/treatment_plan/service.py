"""Treatment plan module service layer."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.auth.models import ClinicMembership
from app.core.events import event_bus
from app.core.events.types import EventType
from app.modules.odontogram.models import Treatment
from app.modules.patients.models import Patient

from .models import PlannedTreatmentItem, PlannedTreatmentItemSession, TreatmentPlan


async def _validate_professional_in_clinic(
    db: AsyncSession, clinic_id: UUID, user_id: UUID
) -> None:
    """Confirm ``user_id`` is a dentist/hygienist member of ``clinic_id``.

    Used when assigning a doctor to a plan item (or the plan itself) to
    avoid leaking users across tenants or assigning a non-clinical role.
    Raises ``ValueError`` so the router maps it to a 400 response, in
    line with the other validation errors in this module.
    """
    result = await db.execute(
        select(ClinicMembership.id).where(
            ClinicMembership.clinic_id == clinic_id,
            ClinicMembership.user_id == user_id,
            ClinicMembership.role.in_(("dentist", "hygienist")),
        )
    )
    if result.scalar_one_or_none() is None:
        raise ValueError("Invalid professional for this clinic")


logger = logging.getLogger(__name__)


def _treatment_loader() -> selectinload:
    """Eager-load the Treatment (with teeth + catalog_item + its category).

    The ``category`` chain is loaded so consumers of the
    ``treatment_plan.treatment_completed`` event get the
    ``treatment_category_key`` snapshot without a follow-up query
    (issue #62, recalls).
    """
    from app.modules.catalog.models import TreatmentCatalogItem

    return selectinload(PlannedTreatmentItem.treatment).options(
        selectinload(Treatment.teeth),
        selectinload(Treatment.catalog_item).selectinload(TreatmentCatalogItem.category),
    )


def _item_with_sessions_loader() -> list:
    """Eager-load both treatment chain and sessions for a plan item."""
    return [
        _treatment_loader(),
        selectinload(PlannedTreatmentItem.sessions),
    ]


def _snapshot_sessions_from_catalog(
    item: PlannedTreatmentItem,
    treatment: Treatment,
) -> list[PlannedTreatmentItemSession]:
    """Build the session rows for a newly added plan item.

    Pulls the template from ``catalog_item.sessions`` when present;
    otherwise emits a single session worth ``treatment.price_snapshot``.
    When ``price_snapshot`` differs from the catalog's ``default_price``
    (e.g. per_tooth strategy multiplying the unit price), session amounts
    are scaled proportionally so the per-session weights survive.
    Returned rows are appended to ``item.sessions`` by the caller.
    """
    catalog_item = getattr(treatment, "catalog_item", None)
    catalog_sessions = getattr(catalog_item, "sessions", None) if catalog_item else None
    treatment_total = (
        Decimal(str(treatment.price_snapshot))
        if treatment.price_snapshot is not None
        else Decimal("0")
    )

    if not catalog_sessions:
        return [
            PlannedTreatmentItemSession(
                sequence=1,
                label=None,
                amount=treatment_total,
                status="pending",
            )
        ]

    catalog_total = sum(
        (Decimal(str(s.default_price)) for s in catalog_sessions),
        Decimal("0"),
    )
    rows: list[PlannedTreatmentItemSession] = []
    if catalog_total > 0 and treatment_total > 0 and catalog_total != treatment_total:
        # Scale per-session amounts to the actual treatment total.
        scale = treatment_total / catalog_total
        scaled = [
            (Decimal(str(s.default_price)) * scale).quantize(Decimal("0.01"))
            for s in catalog_sessions
        ]
        # Adjust last session to absorb rounding drift so Σ matches exactly.
        delta = treatment_total - sum(scaled, Decimal("0"))
        scaled[-1] = scaled[-1] + delta
        amounts = scaled
    else:
        amounts = [Decimal(str(s.default_price)) for s in catalog_sessions]

    for idx, (cs, amount) in enumerate(zip(catalog_sessions, amounts, strict=True), start=1):
        label = None
        if cs.labels:
            label = cs.labels.get("es") or cs.labels.get("en") or next(iter(cs.labels.values()))
        rows.append(
            PlannedTreatmentItemSession(
                sequence=idx,
                label=label,
                amount=amount,
                status="pending",
            )
        )
    return rows


# Allowed status transitions for ``TreatmentPlan``. See ADR 0006 and
# docs/workflows/plan-budget-flow-tech-plan.md §3.1 for the model.
#
#   draft     ──confirm──► pending ──accept──► active ──complete──► completed
#                            │                    │
#                            │ rejected/expired   │ cancelled by clinic
#                            ▼                    ▼
#                                       closed (closure_reason)
#                                          │
#                                          └── reactivate ──► draft
VALID_PLAN_TRANSITIONS: dict[str, set[str]] = {
    "draft": {"pending", "closed"},
    "pending": {"active", "draft", "closed"},
    "active": {"completed", "closed"},
    "completed": {"archived"},
    "closed": {"draft"},
    "archived": set(),
}

VALID_CLOSURE_REASONS: set[str] = {
    "rejected_by_patient",
    "expired",
    "cancelled_by_clinic",
    "patient_abandoned",
    "other",
}


class PlanLockedError(ValueError):
    """Raised when a mutation is attempted on a plan locked by an active budget."""


def _is_plan_locked(plan: TreatmentPlan) -> bool:
    """A plan is locked once it has a non-cancelled budget attached.

    Rationale: generating/sending/accepting a budget turns the plan into a
    contract with the patient. Any structural change would silently invalidate
    that contract, so mutations must go through the explicit unlock flow
    (which cancels the budget).
    """
    if not plan.budget_id or plan.budget is None:
        return False
    return plan.budget.status != "cancelled"


class TreatmentPlanService:
    """Service for treatment plan operations."""

    # -------------------------------------------------------------------------
    # Plan Number Generation
    # -------------------------------------------------------------------------

    @staticmethod
    async def generate_plan_number(db: AsyncSession, clinic_id: UUID) -> str:
        """Generate a unique plan number for the clinic."""
        year = datetime.now(UTC).year

        # Count existing plans for this year
        result = await db.execute(
            select(func.count(TreatmentPlan.id)).where(
                TreatmentPlan.clinic_id == clinic_id,
                TreatmentPlan.plan_number.like(f"PLAN-{year}-%"),
            )
        )
        count = result.scalar_one()

        return f"PLAN-{year}-{count + 1:04d}"

    # -------------------------------------------------------------------------
    # CRUD Operations
    # -------------------------------------------------------------------------

    @staticmethod
    async def list(
        db: AsyncSession,
        clinic_id: UUID,
        page: int = 1,
        page_size: int = 20,
        patient_id: UUID | None = None,
        status: str | list[str] | None = None,
    ) -> tuple[list[TreatmentPlan], int]:
        """List treatment plans with pagination and filters."""
        page_size = min(max(page_size, 1), 100)
        page = max(page, 1)
        offset = (page - 1) * page_size

        # Base query - exclude deleted
        base_where = [
            TreatmentPlan.clinic_id == clinic_id,
            TreatmentPlan.deleted_at.is_(None),
        ]

        if patient_id:
            base_where.append(TreatmentPlan.patient_id == patient_id)

        if status:
            statuses = [status] if isinstance(status, str) else list(status)
            if len(statuses) == 1:
                base_where.append(TreatmentPlan.status == statuses[0])
            else:
                base_where.append(TreatmentPlan.status.in_(statuses))

        # Count
        count_result = await db.execute(select(func.count(TreatmentPlan.id)).where(*base_where))
        total = count_result.scalar_one()

        # Query with relationships. The inner ``items → treatment``
        # chain was previously declared twice — once with
        # ``Treatment.teeth`` and once with ``Treatment.catalog_item``
        # — making SQLAlchemy issue two extra batch queries per page
        # instead of one. Collapsed into a single chain that loads
        # both grandchildren in the same step.
        query = (
            select(TreatmentPlan)
            .where(*base_where)
            .options(
                selectinload(TreatmentPlan.patient),
                selectinload(TreatmentPlan.budget),
                selectinload(TreatmentPlan.items)
                .selectinload(PlannedTreatmentItem.treatment)
                .options(
                    selectinload(Treatment.teeth),
                    selectinload(Treatment.catalog_item),
                ),
                selectinload(TreatmentPlan.items).selectinload(PlannedTreatmentItem.sessions),
            )
            .order_by(TreatmentPlan.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        result = await db.execute(query)
        items = list(result.scalars().all())

        return items, total

    @staticmethod
    async def get(
        db: AsyncSession,
        clinic_id: UUID,
        plan_id: UUID,
    ) -> TreatmentPlan | None:
        """Get a single treatment plan with all relationships."""
        result = await db.execute(
            select(TreatmentPlan)
            .where(
                TreatmentPlan.id == plan_id,
                TreatmentPlan.clinic_id == clinic_id,
                TreatmentPlan.deleted_at.is_(None),
            )
            .options(
                selectinload(TreatmentPlan.patient),
                selectinload(TreatmentPlan.budget),
                selectinload(TreatmentPlan.items)
                .selectinload(PlannedTreatmentItem.treatment)
                .selectinload(Treatment.teeth),
                selectinload(TreatmentPlan.items)
                .selectinload(PlannedTreatmentItem.treatment)
                .selectinload(Treatment.catalog_item),
                selectinload(TreatmentPlan.items).selectinload(PlannedTreatmentItem.sessions),
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def create(
        db: AsyncSession,
        clinic_id: UUID,
        user_id: UUID,
        data: dict,
    ) -> TreatmentPlan:
        """Create a new treatment plan."""
        # Validate patient exists in clinic
        patient_id = data.get("patient_id")
        patient = await db.get(Patient, patient_id)
        if not patient or patient.clinic_id != clinic_id:
            raise ValueError("Invalid patient")

        plan_number = await TreatmentPlanService.generate_plan_number(db, clinic_id)

        plan = TreatmentPlan(
            clinic_id=clinic_id,
            patient_id=patient_id,
            plan_number=plan_number,
            title=data.get("title"),
            assigned_professional_id=data.get("assigned_professional_id"),
            diagnosis_notes=data.get("diagnosis_notes"),
            internal_notes=data.get("internal_notes"),
            created_by=user_id,
        )
        db.add(plan)
        await db.flush()

        # Load patient relationship for response serialization
        await db.refresh(plan, ["patient"])

        # Publish event
        await event_bus.publish(
            "treatment_plan.created",
            {
                "plan_id": str(plan.id),
                "patient_id": str(plan.patient_id),
                "clinic_id": str(clinic_id),
                "created_by": str(user_id),
                "plan_number": plan.plan_number,
                "plan_name": plan.title,
            },
        )

        return plan

    @staticmethod
    async def update(
        db: AsyncSession,
        clinic_id: UUID,
        plan_id: UUID,
        data: dict,
    ) -> TreatmentPlan | None:
        """Update a treatment plan."""
        plan = await TreatmentPlanService.get(db, clinic_id, plan_id)
        if not plan:
            return None

        # Pull the cascade flag out before generic setattr — it is a
        # write-only directive, not a column on TreatmentPlan.
        reassign_pending = bool(data.pop("reassign_pending_items", False))
        old_professional_id = plan.assigned_professional_id
        new_professional_id = data.get("assigned_professional_id", old_professional_id)

        if new_professional_id is not None and new_professional_id != old_professional_id:
            await _validate_professional_in_clinic(db, clinic_id, new_professional_id)

        for key, value in data.items():
            if value is not None and hasattr(plan, key):
                setattr(plan, key, value)

        # Cascade is opt-in. Only pending items still pointing at the previous
        # plan-doctor are reassigned; explicit overrides (other doctor) and
        # completed items are intentionally left alone.
        if (
            reassign_pending
            and old_professional_id is not None
            and new_professional_id is not None
            and old_professional_id != new_professional_id
        ):
            await db.execute(
                update(PlannedTreatmentItem)
                .where(
                    PlannedTreatmentItem.treatment_plan_id == plan_id,
                    PlannedTreatmentItem.clinic_id == clinic_id,
                    PlannedTreatmentItem.status == "pending",
                    PlannedTreatmentItem.assigned_professional_id == old_professional_id,
                )
                .values(assigned_professional_id=new_professional_id)
            )

        return plan

    @staticmethod
    async def update_status(
        db: AsyncSession,
        clinic_id: UUID,
        plan_id: UUID,
        new_status: str,
        user_id: UUID,
    ) -> TreatmentPlan | None:
        """Update treatment plan status with validation."""
        plan = await TreatmentPlanService.get(db, clinic_id, plan_id)
        if not plan:
            return None

        old_status = plan.status
        if old_status == new_status:
            return plan

        if new_status not in VALID_PLAN_TRANSITIONS.get(old_status, set()):
            raise ValueError(f"Invalid status transition from {old_status} to {new_status}")

        # Cannot activate plan without items
        if new_status == "active" and not plan.items:
            raise ValueError("Cannot activate plan without treatments")

        plan.status = new_status

        # Terminal transitions drop the plan's hold on its planned Treatments — clean
        # up any that become orphaned so the odontogram reflects reality.
        if new_status in ("closed", "archived"):
            await TreatmentPlanService._cleanup_orphan_planned_treatments(
                db, clinic_id, plan, user_id
            )

        # Publish event
        await event_bus.publish(
            "treatment_plan.status_changed",
            {
                "plan_id": str(plan.id),
                "old_status": old_status,
                "new_status": new_status,
                "clinic_id": str(clinic_id),
            },
        )

        return plan

    @staticmethod
    async def delete(
        db: AsyncSession,
        clinic_id: UUID,
        plan_id: UUID,
        user_id: UUID,
    ) -> bool:
        """Soft delete (archive) a treatment plan.

        Also runs orphan cleanup: planned Treatments that only lived inside this
        plan are soft-deleted so they disappear from the odontogram. `performed`
        Treatments are always preserved as clinical history.
        """
        plan = await TreatmentPlanService.get(db, clinic_id, plan_id)
        if not plan:
            return False

        await TreatmentPlanService._cleanup_orphan_planned_treatments(db, clinic_id, plan, user_id)
        plan.deleted_at = datetime.now(UTC)
        return True

    @staticmethod
    async def _cleanup_orphan_planned_treatments(
        db: AsyncSession,
        clinic_id: UUID,
        plan: TreatmentPlan,
        user_id: UUID,
    ) -> None:
        """Soft-delete Treatments that become orphaned when `plan` goes terminal.

        For every Treatment referenced by this plan's items, check whether any
        *other* non-terminal plan still references it. If not, and the Treatment
        is still `planned` (never performed), soft-delete it so the odontogram
        stops showing it. Performed Treatments are left alone (clinical history).
        """
        from app.modules.odontogram.service import TreatmentService

        treatment_ids = {item.treatment_id for item in plan.items if item.treatment_id}
        if not treatment_ids:
            return

        for treatment_id in treatment_ids:
            # Count references from OTHER plans that are still "live" (non-terminal,
            # non-deleted). We exclude this plan explicitly — its items stay in DB
            # as history but no longer count as a live reference.
            result = await db.execute(
                select(func.count(PlannedTreatmentItem.id))
                .join(
                    TreatmentPlan,
                    TreatmentPlan.id == PlannedTreatmentItem.treatment_plan_id,
                )
                .where(
                    PlannedTreatmentItem.treatment_id == treatment_id,
                    PlannedTreatmentItem.clinic_id == clinic_id,
                    PlannedTreatmentItem.treatment_plan_id != plan.id,
                    TreatmentPlan.deleted_at.is_(None),
                    TreatmentPlan.status.notin_(("archived", "cancelled")),
                )
            )
            if (result.scalar_one() or 0) > 0:
                continue

            treatment = await db.get(Treatment, treatment_id)
            if treatment and treatment.deleted_at is None and treatment.status == "planned":
                await TreatmentService.delete(db, clinic_id, treatment_id, user_id)

    # -------------------------------------------------------------------------
    # Item Operations
    # -------------------------------------------------------------------------

    @staticmethod
    async def add_item(
        db: AsyncSession,
        clinic_id: UUID,
        plan_id: UUID,
        data: dict,
    ) -> PlannedTreatmentItem:
        """Add a Treatment to the plan as a new item."""
        plan = await TreatmentPlanService.get(db, clinic_id, plan_id)
        if not plan:
            raise ValueError("Treatment plan not found")

        if plan.status not in ("draft", "active"):
            raise ValueError("Cannot add items to a completed/cancelled plan")

        if _is_plan_locked(plan):
            raise PlanLockedError("Plan is locked by an active budget")

        treatment_id = data.get("treatment_id")
        if treatment_id is None:
            raise ValueError("treatment_id is required")

        # Validate the Treatment exists for this clinic/patient.
        treatment = await db.get(Treatment, treatment_id)
        if (
            not treatment
            or treatment.clinic_id != clinic_id
            or treatment.patient_id != plan.patient_id
            or treatment.deleted_at is not None
        ):
            raise ValueError("Invalid treatment for this plan")

        sequence_order = data.get("sequence_order")
        if sequence_order is None:
            result = await db.execute(
                select(func.max(PlannedTreatmentItem.sequence_order)).where(
                    PlannedTreatmentItem.treatment_plan_id == plan_id
                )
            )
            max_order = result.scalar_one() or 0
            sequence_order = max_order + 1

        # Inherit the plan's doctor unless the caller passes an explicit value.
        # Snapshot semantics: once stored on the item it stays put even if the
        # plan's doctor changes later (cascade is opt-in on plan update).
        assigned_professional_id = data.get("assigned_professional_id")
        if assigned_professional_id is None:
            assigned_professional_id = plan.assigned_professional_id
        if assigned_professional_id is not None:
            await _validate_professional_in_clinic(db, clinic_id, assigned_professional_id)

        item = PlannedTreatmentItem(
            clinic_id=clinic_id,
            treatment_plan_id=plan_id,
            treatment_id=treatment_id,
            sequence_order=sequence_order,
            notes=data.get("notes"),
            assigned_professional_id=assigned_professional_id,
        )
        db.add(item)
        await db.flush()

        # Pre-load the catalog template before snapshotting sessions.
        from app.modules.catalog.models import TreatmentCatalogItem

        treatment_full = await db.execute(
            select(Treatment)
            .options(
                selectinload(Treatment.teeth),
                selectinload(Treatment.catalog_item).selectinload(TreatmentCatalogItem.sessions),
            )
            .where(Treatment.id == treatment_id)
        )
        treatment_loaded = treatment_full.scalar_one()
        for session_row in _snapshot_sessions_from_catalog(item, treatment_loaded):
            session_row.plan_item_id = item.id
            db.add(session_row)
        await db.flush()

        # Re-fetch with eager-loaded treatment.teeth / .catalog_item for the response.
        reloaded = await db.execute(
            select(PlannedTreatmentItem)
            .options(
                selectinload(PlannedTreatmentItem.treatment).selectinload(Treatment.teeth),
                selectinload(PlannedTreatmentItem.treatment).selectinload(Treatment.catalog_item),
                selectinload(PlannedTreatmentItem.sessions),
            )
            .where(PlannedTreatmentItem.id == item.id)
        )
        item = reloaded.scalar_one()

        # Snapshot payload — see ADR 0003. The budget module subscribes
        # without importing treatment_plan/odontogram models.
        treatment = item.treatment
        primary_tooth = treatment.teeth[0].tooth_number if treatment and treatment.teeth else None
        primary_surfaces = treatment.teeth[0].surfaces if treatment and treatment.teeth else None
        await event_bus.publish(
            "treatment_plan.treatment_added",
            {
                "plan_id": str(plan_id),
                "item_id": str(item.id),
                "treatment_id": str(treatment_id),
                "clinic_id": str(clinic_id),
                "patient_id": str(plan.patient_id),
                "budget_id": str(plan.budget_id) if plan.budget_id else None,
                "catalog_item_id": (
                    str(treatment.catalog_item_id)
                    if treatment and treatment.catalog_item_id
                    else None
                ),
                "tooth_number": primary_tooth,
                "surfaces": primary_surfaces,
                "unit_price": (
                    str(treatment.price_snapshot)
                    if treatment and treatment.price_snapshot is not None
                    else None
                ),
                "assigned_professional_id": (
                    str(item.assigned_professional_id) if item.assigned_professional_id else None
                ),
            },
        )

        return item

    @staticmethod
    async def update_item(
        db: AsyncSession,
        clinic_id: UUID,
        plan_id: UUID,
        item_id: UUID,
        data: dict,
    ) -> PlannedTreatmentItem | None:
        """Update scheduling metadata on a planned treatment item."""
        plan = await TreatmentPlanService.get(db, clinic_id, plan_id)
        if not plan:
            return None

        # The plan-lock guard protects the patient-facing contract: items,
        # prices, sequence. Reassigning who performs a treatment doesn't
        # change that contract, so doctor-only updates skip the guard —
        # clinicians need to swap responsibility even after the plan is
        # validated. Any other field still respects the lock.
        non_doctor_keys = {k for k in data if k != "assigned_professional_id"}
        if non_doctor_keys and _is_plan_locked(plan):
            raise PlanLockedError("Plan is locked by an active budget")

        result = await db.execute(
            select(PlannedTreatmentItem)
            .where(
                PlannedTreatmentItem.id == item_id,
                PlannedTreatmentItem.treatment_plan_id == plan_id,
                PlannedTreatmentItem.clinic_id == clinic_id,
            )
            .options(*_item_with_sessions_loader())
        )
        item = result.scalar_one_or_none()
        if not item:
            return None

        # Completed/cancelled items preserve the doctor that was responsible
        # at the time. ``completed_by`` is the source of truth for "who did
        # it" once an item is done — don't let later edits rewrite history.
        if "assigned_professional_id" in data and item.status != "pending":
            raise ValueError("Cannot change the assigned doctor on a non-pending item")

        # ``assigned_professional_id`` is nullable on purpose — the caller may
        # want to clear it. The router passes ``model_dump(exclude_unset=True)``
        # so a missing key means "do not touch", while ``None`` means "unset".
        if "assigned_professional_id" in data:
            new_professional_id = data.pop("assigned_professional_id")
            if new_professional_id is not None:
                await _validate_professional_in_clinic(db, clinic_id, new_professional_id)
            item.assigned_professional_id = new_professional_id

        for key, value in data.items():
            if value is not None and hasattr(item, key):
                setattr(item, key, value)

        return item

    @staticmethod
    async def reorder_items(
        db: AsyncSession,
        clinic_id: UUID,
        plan_id: UUID,
        item_ids: list[UUID],
    ) -> list[PlannedTreatmentItem] | None:
        """Set `sequence_order` of items to match the position in `item_ids`.

        Validates that `item_ids` covers exactly the plan's items (no missing, no
        extras). Returns the reordered items or None if the plan does not exist.
        Raises ValueError on validation failure.
        """
        # Load plan to confirm ownership (with budget for lock check).
        plan_q = await db.execute(
            select(TreatmentPlan)
            .where(
                TreatmentPlan.id == plan_id,
                TreatmentPlan.clinic_id == clinic_id,
                TreatmentPlan.deleted_at.is_(None),
            )
            .options(selectinload(TreatmentPlan.budget))
        )
        plan = plan_q.scalar_one_or_none()
        if not plan:
            return None
        if _is_plan_locked(plan):
            raise PlanLockedError("Plan is locked by an active budget")

        # Load current items.
        items_q = await db.execute(
            select(PlannedTreatmentItem).where(
                PlannedTreatmentItem.treatment_plan_id == plan_id,
                PlannedTreatmentItem.clinic_id == clinic_id,
            )
        )
        current = {i.id: i for i in items_q.scalars().all()}

        # Validate set equality — no missing or extra IDs.
        requested = list(item_ids)
        if len(requested) != len(set(requested)):
            raise ValueError("Duplicate item ids not allowed")
        if set(requested) != set(current.keys()):
            raise ValueError("item_ids must cover exactly the plan's current items")

        # Apply new order.
        for index, item_id in enumerate(requested):
            current[item_id].sequence_order = index

        await db.flush()

        await event_bus.publish(
            EventType.TREATMENT_PLAN_ITEMS_REORDERED,
            {
                "clinic_id": str(clinic_id),
                "plan_id": str(plan_id),
                "item_ids": [str(i) for i in requested],
            },
        )

        return [current[i] for i in requested]

    @staticmethod
    async def remove_item(
        db: AsyncSession,
        clinic_id: UUID,
        plan_id: UUID,
        item_id: UUID,
        user_id: UUID,
    ) -> bool:
        """Remove an item from the plan.

        Orphan rule: if the removed item was the last active PlannedTreatmentItem
        referencing its Treatment and that Treatment is still `planned`, soft-delete
        the Treatment so the odontogram reflects the removal. `performed` Treatments
        are kept (clinical history).
        """
        plan = await TreatmentPlanService.get(db, clinic_id, plan_id)
        if not plan:
            return False
        if _is_plan_locked(plan):
            raise PlanLockedError("Plan is locked by an active budget")

        result = await db.execute(
            select(PlannedTreatmentItem).where(
                PlannedTreatmentItem.id == item_id,
                PlannedTreatmentItem.treatment_plan_id == plan_id,
                PlannedTreatmentItem.clinic_id == clinic_id,
            )
        )
        item = result.scalar_one_or_none()
        if not item:
            return False

        treatment_id = item.treatment_id
        await db.delete(item)
        await db.flush()

        # Orphan check — any other active item still referencing the Treatment?
        other_refs = await db.execute(
            select(func.count(PlannedTreatmentItem.id)).where(
                PlannedTreatmentItem.treatment_id == treatment_id,
                PlannedTreatmentItem.clinic_id == clinic_id,
            )
        )
        remaining = other_refs.scalar_one() or 0
        if remaining == 0:
            treatment = await db.get(Treatment, treatment_id)
            if treatment and treatment.deleted_at is None and treatment.status == "planned":
                from app.modules.odontogram.service import TreatmentService

                await TreatmentService.delete(db, clinic_id, treatment_id, user_id)

        # Snapshot payload — budget needs ``budget_id`` to find the
        # matching line without importing treatment_plan models.
        await event_bus.publish(
            "treatment_plan.treatment_removed",
            {
                "plan_id": str(plan_id),
                "item_id": str(item_id),
                "treatment_id": str(treatment_id),
                "clinic_id": str(clinic_id),
                "budget_id": str(plan.budget_id) if plan.budget_id else None,
            },
        )

        return True

    @staticmethod
    async def _load_item_with_sessions(
        db: AsyncSession, clinic_id: UUID, plan_id: UUID, item_id: UUID
    ) -> PlannedTreatmentItem | None:
        result = await db.execute(
            select(PlannedTreatmentItem)
            .where(
                PlannedTreatmentItem.id == item_id,
                PlannedTreatmentItem.treatment_plan_id == plan_id,
                PlannedTreatmentItem.clinic_id == clinic_id,
            )
            .options(*_item_with_sessions_loader())
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def complete_session(
        db: AsyncSession,
        clinic_id: UUID,
        plan_id: UUID,
        item_id: UUID,
        session_id: UUID,
        user_id: UUID,
        completed_without_appointment: bool = False,
        notes: str | None = None,
    ) -> PlannedTreatmentItem | None:
        """Mark one session of a plan item as completed.

        Publishes ``treatment_plan.item_session_completed`` (consumed by
        payments → earned ledger). When this is the last non-pending
        session, the parent item is finalized: status flips to
        ``completed``, the Treatment is performed, and the existing
        ``treatment_plan.treatment_completed`` audit/recall path runs.
        """
        item = await TreatmentPlanService._load_item_with_sessions(db, clinic_id, plan_id, item_id)
        if not item:
            return None

        session = next((s for s in item.sessions if s.id == session_id), None)
        if not session:
            raise ValueError("Session not found")
        if session.status != "pending":
            raise ValueError("Session is not pending")

        session.status = "completed"
        session.completed_at = datetime.now(UTC)
        session.completed_by = user_id
        if notes:
            session.notes = notes

        await db.flush()

        patient_id_str: str | None = None
        if item.treatment:
            patient_id_str = str(item.treatment.patient_id)

        await event_bus.publish(
            EventType.TREATMENT_PLAN_ITEM_SESSION_COMPLETED,
            {
                "clinic_id": str(clinic_id),
                "plan_id": str(plan_id),
                "item_id": str(item_id),
                "session_id": str(session.id),
                "sequence": session.sequence,
                "label": session.label,
                "amount": str(session.amount),
                "treatment_id": str(item.treatment_id),
                "patient_id": patient_id_str,
                "completed_by": str(user_id),
                "occurred_at": session.completed_at.isoformat(),
            },
        )

        # Item finalizes when every session is in a terminal state and at
        # least one was actually completed (otherwise an all-cancelled
        # set would silently mark the item done).
        terminal_states = {"completed", "cancelled"}
        all_terminal = all(s.status in terminal_states for s in item.sessions)
        any_completed = any(s.status == "completed" for s in item.sessions)
        if all_terminal and any_completed and item.status != "completed":
            await TreatmentPlanService._finalize_item(
                db,
                clinic_id=clinic_id,
                plan_id=plan_id,
                item=item,
                user_id=user_id,
                completed_without_appointment=completed_without_appointment,
                notes=notes,
            )

        return item

    @staticmethod
    async def _finalize_item(
        db: AsyncSession,
        *,
        clinic_id: UUID,
        plan_id: UUID,
        item: PlannedTreatmentItem,
        user_id: UUID,
        completed_without_appointment: bool,
        notes: str | None,
    ) -> None:
        """Flip the item to completed and run the legacy completion path.

        Performs the Treatment, publishes ``treatment_completed`` (recalls /
        odontogram) and the audit hint. Does NOT publish earned events —
        those flow per-session via ``item_session_completed``.
        """
        item.status = "completed"
        item.completed_at = datetime.now(UTC)
        item.completed_by = user_id
        item.completed_without_appointment = completed_without_appointment
        if notes and not item.notes:
            item.notes = notes

        from app.modules.odontogram.service import TreatmentService

        await TreatmentService.perform(
            db=db,
            clinic_id=clinic_id,
            treatment_id=item.treatment_id,
            user_id=user_id,
            notes=notes,
        )

        item_name: str | None = None
        patient_id_str: str | None = None
        treatment_category_key: str | None = None
        if item.treatment:
            patient_id_str = str(item.treatment.patient_id)
            if item.treatment.catalog_item:
                names = item.treatment.catalog_item.names or {}
                item_name = names.get("es") or names.get("en") or names.get("fr")
                if item.treatment.catalog_item.category:
                    treatment_category_key = item.treatment.catalog_item.category.key

        await event_bus.publish(
            "treatment_plan.treatment_completed",
            {
                "plan_id": str(plan_id),
                "item_id": str(item.id),
                "treatment_id": str(item.treatment_id),
                "clinic_id": str(clinic_id),
                "patient_id": patient_id_str,
                "completed_by": str(user_id),
                "item_name": item_name,
                "occurred_at": item.completed_at.isoformat() if item.completed_at else None,
                "treatment_category_key": treatment_category_key,
            },
        )

        await event_bus.publish(
            EventType.TREATMENT_PLAN_ITEM_COMPLETED_WITHOUT_NOTE,
            {
                "clinic_id": str(clinic_id),
                "patient_id": patient_id_str,
                "plan_id": str(plan_id),
                "plan_item_id": str(item.id),
                "user_id": str(user_id),
                "item_name": item_name,
                "occurred_at": item.completed_at.isoformat() if item.completed_at else None,
            },
        )

        await TreatmentPlanService._check_and_complete_plan(db, clinic_id, plan_id)

    @staticmethod
    async def complete_item(
        db: AsyncSession,
        clinic_id: UUID,
        plan_id: UUID,
        item_id: UUID,
        user_id: UUID,
        completed_without_appointment: bool = True,
        notes: str | None = None,
    ) -> PlannedTreatmentItem | None:
        """Back-compat shim: complete the next pending session of an item.

        Items always have ≥1 session post-migration (tp_0006 backfill).
        For single-session items this behaves like the legacy flow. For
        multi-session items it advances one session per call — callers
        targeting a specific session should use ``complete_session``.
        """
        item = await TreatmentPlanService._load_item_with_sessions(db, clinic_id, plan_id, item_id)
        if not item:
            return None
        if item.status == "completed":
            return item

        next_session = next(
            (s for s in sorted(item.sessions, key=lambda x: x.sequence) if s.status == "pending"),
            None,
        )
        if next_session is None:
            raise ValueError("No pending sessions to complete")

        return await TreatmentPlanService.complete_session(
            db,
            clinic_id=clinic_id,
            plan_id=plan_id,
            item_id=item_id,
            session_id=next_session.id,
            user_id=user_id,
            completed_without_appointment=completed_without_appointment,
            notes=notes,
        )

    @staticmethod
    async def cancel_session(
        db: AsyncSession,
        clinic_id: UUID,
        plan_id: UUID,
        item_id: UUID,
        session_id: UUID,
        user_id: UUID,
        notes: str | None = None,
    ) -> PlannedTreatmentItem | None:
        """Mark a pending session as cancelled (no earned entry generated)."""
        item = await TreatmentPlanService._load_item_with_sessions(db, clinic_id, plan_id, item_id)
        if not item:
            return None
        session = next((s for s in item.sessions if s.id == session_id), None)
        if not session:
            raise ValueError("Session not found")
        if session.status != "pending":
            raise ValueError("Only pending sessions can be cancelled")

        session.status = "cancelled"
        session.completed_at = datetime.now(UTC)
        session.completed_by = user_id
        if notes:
            session.notes = notes
        await db.flush()

        # Finalize if cancellation leaves the item with no pending work and
        # at least one completed session.
        terminal_states = {"completed", "cancelled"}
        all_terminal = all(s.status in terminal_states for s in item.sessions)
        any_completed = any(s.status == "completed" for s in item.sessions)
        if all_terminal and any_completed and item.status != "completed":
            await TreatmentPlanService._finalize_item(
                db,
                clinic_id=clinic_id,
                plan_id=plan_id,
                item=item,
                user_id=user_id,
                completed_without_appointment=False,
                notes=None,
            )
        return item

    @staticmethod
    async def update_session(
        db: AsyncSession,
        clinic_id: UUID,
        plan_id: UUID,
        item_id: UUID,
        session_id: UUID,
        data: dict,
    ) -> PlannedTreatmentItem | None:
        """Edit a pending session's label/amount/notes."""
        item = await TreatmentPlanService._load_item_with_sessions(db, clinic_id, plan_id, item_id)
        if not item:
            return None
        session = next((s for s in item.sessions if s.id == session_id), None)
        if not session:
            raise ValueError("Session not found")
        if session.status != "pending":
            raise ValueError("Cannot edit a non-pending session")

        if "label" in data:
            session.label = data["label"]
        if "amount" in data and data["amount"] is not None:
            session.amount = Decimal(str(data["amount"]))
        if "notes" in data:
            session.notes = data["notes"]
        return item

    @staticmethod
    async def add_session_manual(
        db: AsyncSession,
        clinic_id: UUID,
        plan_id: UUID,
        item_id: UUID,
        data: dict,
    ) -> PlannedTreatmentItem | None:
        """Append a new session row at the next sequence number."""
        item = await TreatmentPlanService._load_item_with_sessions(db, clinic_id, plan_id, item_id)
        if not item:
            return None
        next_seq = (max((s.sequence for s in item.sessions), default=0)) + 1
        amount = data.get("amount")
        if amount is None:
            raise ValueError("amount is required")
        item.sessions.append(
            PlannedTreatmentItemSession(
                sequence=next_seq,
                label=data.get("label"),
                amount=Decimal(str(amount)),
                status="pending",
            )
        )
        return item

    @staticmethod
    async def delete_session(
        db: AsyncSession,
        clinic_id: UUID,
        plan_id: UUID,
        item_id: UUID,
        session_id: UUID,
    ) -> PlannedTreatmentItem | None:
        """Remove a pending session. Refuses on completed/cancelled sessions."""
        item = await TreatmentPlanService._load_item_with_sessions(db, clinic_id, plan_id, item_id)
        if not item:
            return None
        session = next((s for s in item.sessions if s.id == session_id), None)
        if not session:
            raise ValueError("Session not found")
        if session.status != "pending":
            raise ValueError("Cannot delete a non-pending session")
        if (
            len([s for s in item.sessions if s.status == "pending"]) <= 1
            and len(item.sessions) == 1
        ):
            raise ValueError("Cannot delete the only session of an item")
        item.sessions.remove(session)
        await db.flush()
        return item

    @staticmethod
    async def _check_and_complete_plan(
        db: AsyncSession,
        clinic_id: UUID,
        plan_id: UUID,
    ) -> None:
        """Check if all items completed and auto-complete the plan if so."""
        plan = await TreatmentPlanService.get(db, clinic_id, plan_id)
        if not plan or plan.status != "active":
            return

        # Check if any non-completed items remain
        has_pending = any(item.status != "completed" for item in plan.items)
        if has_pending:
            return

        # All items completed - auto-complete the plan
        old_status = plan.status
        plan.status = "completed"

        await event_bus.publish(
            "treatment_plan.status_changed",
            {
                "plan_id": str(plan.id),
                "old_status": old_status,
                "new_status": "completed",
                "clinic_id": str(clinic_id),
            },
        )

        logger.info(
            "Auto-completed treatment plan %s (all items completed)",
            plan.id,
        )

    # -------------------------------------------------------------------------
    # Budget Integration
    # -------------------------------------------------------------------------

    @staticmethod
    async def link_budget(
        db: AsyncSession,
        clinic_id: UUID,
        plan_id: UUID,
        budget_id: UUID,
    ) -> TreatmentPlan | None:
        """Link an existing budget to the plan."""
        from app.modules.budget.models import Budget

        plan = await TreatmentPlanService.get(db, clinic_id, plan_id)
        if not plan:
            return None

        # Verify budget exists and belongs to same clinic/patient
        budget = await db.get(Budget, budget_id)
        if not budget or budget.clinic_id != clinic_id:
            raise ValueError("Invalid budget")

        if budget.patient_id != plan.patient_id:
            raise ValueError("Budget belongs to different patient")

        plan.budget_id = budget_id

        return plan

    @staticmethod
    async def request_budget_sync(
        db: AsyncSession,
        clinic_id: UUID,
        plan_id: UUID,
    ) -> bool:
        """Request budget module to sync items.

        Builds a denormalized items snapshot so the budget handler can
        reconcile without importing treatment_plan / odontogram models
        (ADR 0003).
        """
        plan = await TreatmentPlanService.get(db, clinic_id, plan_id)
        if not plan or not plan.budget_id:
            return False

        plan_items = await db.execute(
            select(PlannedTreatmentItem)
            .options(selectinload(PlannedTreatmentItem.treatment).selectinload(Treatment.teeth))
            .where(
                PlannedTreatmentItem.treatment_plan_id == plan_id,
                PlannedTreatmentItem.clinic_id == clinic_id,
            )
        )
        items_payload = []
        for plan_item in plan_items.scalars().all():
            treatment = plan_item.treatment
            if not treatment or not treatment.catalog_item_id:
                continue
            primary_tooth = treatment.teeth[0].tooth_number if treatment.teeth else None
            primary_surfaces = treatment.teeth[0].surfaces if treatment.teeth else None
            items_payload.append(
                {
                    "item_id": str(plan_item.id),
                    "treatment_id": str(treatment.id),
                    "catalog_item_id": str(treatment.catalog_item_id),
                    "tooth_number": primary_tooth,
                    "surfaces": primary_surfaces,
                    "unit_price": (
                        str(treatment.price_snapshot)
                        if treatment.price_snapshot is not None
                        else None
                    ),
                }
            )

        await event_bus.publish(
            "treatment_plan.budget_sync_requested",
            {
                "plan_id": str(plan_id),
                "budget_id": str(plan.budget_id),
                "clinic_id": str(clinic_id),
                "items": items_payload,
            },
        )

        return True

    # -------------------------------------------------------------------------
    # Bandeja de planes (cross-module pipeline view)
    # -------------------------------------------------------------------------

    @staticmethod
    async def list_pipeline(
        db: AsyncSession,
        clinic_id: UUID,
        tab: str,
        page: int = 1,
        page_size: int = 20,
        doctor_id: UUID | None = None,
        search: str | None = None,
    ) -> tuple[list[dict], int]:
        """Pipeline bandeja query — joins plans + budgets + appointments.

        Returns ``(rows, total)`` with rows shaped as ``PipelineRow``
        dicts ready to be returned by FastAPI. The query is implemented
        with raw SQL because the JOIN spans three modules
        (treatment_plan + budget + agenda) and `treatment_plan`'s
        manifest declares the dependency on both. Splitting into ORM
        round-trips would be N+1; doing it in one statement is fastest
        and pageable.
        """
        from sqlalchemy import text as sa_text

        # ----- per-tab WHERE clause ------------------------------------
        # Five tabs documented in docs/workflows/plan-budget-flow.md §5.
        if tab == "por_presupuestar":
            tab_where = "p.status = 'pending' AND b.status = 'draft'"
            order_by = "COALESCE(p.confirmed_at, p.created_at) DESC"
        elif tab == "esperando_paciente":
            tab_where = "p.status = 'pending' AND b.status IN ('sent', 'expired')"
            order_by = "COALESCE(p.confirmed_at, p.created_at) ASC"  # oldest first
        elif tab == "sin_cita":
            tab_where = (
                "p.status = 'active' "
                "AND COALESCE(appt.future_count, 0) = 0 "
                "AND COALESCE(appt.past_count, 0) = 0"
            )
            order_by = "p.updated_at DESC"
        elif tab == "sin_proxima_cita":
            tab_where = (
                "p.status = 'active' "
                "AND COALESCE(appt.future_count, 0) = 0 "
                "AND COALESCE(appt.past_count, 0) > 0 "
                "AND COALESCE(items.pending_count, 0) > 0"
            )
            order_by = "appt.last_past_at DESC NULLS LAST"
        elif tab == "cerrados":
            tab_where = "p.status = 'closed' AND p.closed_at >= (NOW() - INTERVAL '90 days')"
            order_by = "p.closed_at DESC"
        else:
            raise ValueError(f"Unknown pipeline tab '{tab}'")

        params: dict[str, object] = {"clinic_id": clinic_id}
        extra_where = ""
        if doctor_id is not None:
            extra_where += " AND p.assigned_professional_id = :doctor_id"
            params["doctor_id"] = doctor_id
        if search:
            extra_where += (
                " AND (p.plan_number ILIKE :q OR pat.first_name ILIKE :q OR pat.last_name ILIKE :q)"
            )
            params["q"] = f"%{search}%"

        # ----- shared SELECT --------------------------------------------
        base_sql = f"""
            WITH item_counts AS (
                SELECT
                    treatment_plan_id AS plan_id,
                    COUNT(*) AS total_count,
                    COUNT(*) FILTER (WHERE status = 'completed') AS completed_count,
                    COUNT(*) FILTER (WHERE status = 'pending') AS pending_count
                FROM planned_treatment_items
                WHERE clinic_id = :clinic_id
                GROUP BY treatment_plan_id
            ),
            plan_appts AS (
                SELECT
                    pti.treatment_plan_id AS plan_id,
                    COUNT(*) FILTER (
                        WHERE a.start_time >= NOW()
                          AND a.status NOT IN ('cancelled', 'no_show')
                    ) AS future_count,
                    COUNT(*) FILTER (
                        WHERE a.start_time < NOW()
                          AND a.status NOT IN ('cancelled', 'no_show')
                    ) AS past_count,
                    MAX(a.start_time) FILTER (
                        WHERE a.start_time < NOW()
                          AND a.status NOT IN ('cancelled', 'no_show')
                    ) AS last_past_at,
                    MIN(a.start_time) FILTER (
                        WHERE a.start_time >= NOW()
                          AND a.status NOT IN ('cancelled', 'no_show')
                    ) AS next_future_at
                FROM planned_treatment_items pti
                JOIN appointment_treatments at ON at.planned_treatment_item_id = pti.id
                JOIN appointments a ON a.id = at.appointment_id
                WHERE pti.clinic_id = :clinic_id
                GROUP BY pti.treatment_plan_id
            ),
            next_appt AS (
                SELECT DISTINCT ON (pti.treatment_plan_id)
                    pti.treatment_plan_id AS plan_id,
                    a.id AS id,
                    a.start_time AS start_at,
                    a.cabinet_id AS cabinet_id,
                    a.professional_id AS professional_id
                FROM planned_treatment_items pti
                JOIN appointment_treatments at ON at.planned_treatment_item_id = pti.id
                JOIN appointments a ON a.id = at.appointment_id
                WHERE pti.clinic_id = :clinic_id
                  AND a.start_time >= NOW()
                  AND a.status NOT IN ('cancelled', 'no_show')
                ORDER BY pti.treatment_plan_id, a.start_time ASC
            )
            SELECT
                p.id AS plan_id,
                p.plan_number,
                p.title AS plan_title,
                p.status AS plan_status,
                p.closure_reason,
                p.confirmed_at,
                p.closed_at,
                p.updated_at,
                pat.id AS patient_id,
                pat.first_name,
                pat.last_name,
                pat.phone,
                COALESCE(items.total_count, 0) AS items_total,
                COALESCE(items.completed_count, 0) AS items_completed,
                b.id AS budget_id,
                b.status AS budget_status,
                b.total AS budget_total,
                b.valid_until,
                b.last_reminder_sent_at,
                b.viewed_at,
                na.id AS next_appt_id,
                na.start_at AS next_appt_start_at,
                na.cabinet_id AS next_appt_cabinet,
                na.professional_id AS next_appt_professional
            FROM treatment_plans p
            JOIN patients pat ON pat.id = p.patient_id
            LEFT JOIN budgets b ON b.id = p.budget_id
            LEFT JOIN item_counts items ON items.plan_id = p.id
            LEFT JOIN plan_appts appt ON appt.plan_id = p.id
            LEFT JOIN next_appt na ON na.plan_id = p.id
            WHERE p.clinic_id = :clinic_id
              AND p.deleted_at IS NULL
              AND ({tab_where})
              {extra_where}
        """

        # ----- count + page ---------------------------------------------
        count_result = await db.execute(
            sa_text(f"SELECT COUNT(*) AS total FROM ({base_sql}) sub"),
            params,
        )
        total = count_result.scalar() or 0

        page_params = dict(params)
        page_params["limit"] = page_size
        page_params["offset"] = (page - 1) * page_size
        rows_result = await db.execute(
            sa_text(f"{base_sql} ORDER BY {order_by} LIMIT :limit OFFSET :offset"),
            page_params,
        )

        # ----- shape rows -----------------------------------------------
        now = datetime.now(UTC)
        out: list[dict] = []
        for r in rows_result.mappings().all():
            anchor = r["confirmed_at"] or r["closed_at"] or r["updated_at"]
            days_in_status = (now - anchor).days if anchor is not None else 0
            patient_brief = {
                "id": r["patient_id"],
                "first_name": r["first_name"],
                "last_name": r["last_name"],
                "phone": r["phone"],
            }
            budget_brief = None
            if r["budget_id"]:
                budget_brief = {
                    "id": r["budget_id"],
                    "status": r["budget_status"],
                    "total": float(r["budget_total"]) if r["budget_total"] is not None else None,
                    "valid_until": r["valid_until"],
                    "last_reminder_sent_at": r["last_reminder_sent_at"],
                    "viewed_at": r["viewed_at"],
                }
            next_appt = None
            if r["next_appt_id"]:
                next_appt = {
                    "id": r["next_appt_id"],
                    "start_at": r["next_appt_start_at"],
                    "cabinet_id": r["next_appt_cabinet"],
                    "professional_id": r["next_appt_professional"],
                }
            out.append(
                {
                    "plan_id": r["plan_id"],
                    "plan_number": r["plan_number"],
                    "plan_title": r["plan_title"],
                    "plan_status": r["plan_status"],
                    "days_in_status": max(days_in_status, 0),
                    "closure_reason": r["closure_reason"],
                    "items_total": r["items_total"],
                    "items_completed": r["items_completed"],
                    "patient": patient_brief,
                    "budget": budget_brief,
                    "next_appointment": next_appt,
                }
            )
        return out, total

    # -------------------------------------------------------------------------
    # Workflow Transitions (confirm / close / reactivate)
    # -------------------------------------------------------------------------

    @staticmethod
    def _build_plan_snapshot(plan: TreatmentPlan, patient: Patient | None) -> dict:
        """Build the snapshot payload used for cross-module events."""
        items_payload = []
        total_estimated = 0.0
        for item in plan.items:
            treatment = item.treatment
            if treatment is None:
                continue
            primary_tooth = treatment.teeth[0].tooth_number if treatment.teeth else None
            primary_surfaces = treatment.teeth[0].surfaces if treatment.teeth else None
            unit_price = (
                str(treatment.price_snapshot) if treatment.price_snapshot is not None else None
            )
            if unit_price is not None:
                try:
                    total_estimated += float(unit_price)
                except (TypeError, ValueError):
                    pass
            items_payload.append(
                {
                    "item_id": str(item.id),
                    "treatment_id": str(treatment.id),
                    "catalog_item_id": (
                        str(treatment.catalog_item_id) if treatment.catalog_item_id else None
                    ),
                    "tooth_number": primary_tooth,
                    "surfaces": primary_surfaces,
                    "unit_price": unit_price,
                }
            )
        patient_full_name = None
        if patient is not None:
            parts = [patient.first_name, patient.last_name]
            patient_full_name = " ".join(p for p in parts if p) or None
        return {
            "plan_id": str(plan.id),
            "plan_number": plan.plan_number,
            "clinic_id": str(plan.clinic_id),
            "patient_id": str(plan.patient_id),
            "patient_full_name": patient_full_name,
            "items": items_payload,
            "total_estimated": str(total_estimated),
        }

    @staticmethod
    async def confirm(
        db: AsyncSession,
        clinic_id: UUID,
        plan_id: UUID,
        user_id: UUID,
    ) -> TreatmentPlan:
        """Doctor confirmation: ``draft`` → ``pending``.

        Side effects:

        - Sets ``confirmed_at`` and increments the workflow timestamp.
        - Calls ``BudgetService.create_from_plan`` to provision a draft
          budget reusing the plan items as a snapshot. Atomicity is
          guaranteed: if budget creation fails, the whole transaction
          rolls back. ``treatment_plan`` declares ``budget`` in its
          ``manifest.depends`` so the direct call respects the module
          contract.
        - Publishes ``treatment_plan.confirmed`` with a snapshot
          payload so subscribers (patient_timeline, future hooks) do
          not need to import treatment_plan models.
        """
        plan = await TreatmentPlanService.get(db, clinic_id, plan_id)
        if not plan:
            raise ValueError("Plan not found")

        if plan.status != "draft":
            raise ValueError(f"Cannot confirm plan in status '{plan.status}'")
        if not plan.items:
            raise ValueError("Cannot confirm plan without treatments")

        # Atomic transition.
        plan.status = "pending"
        plan.confirmed_at = datetime.now(UTC)

        # Resolve patient for the snapshot. The relationship is OK to
        # use — patients is in our depends.
        patient = await db.get(Patient, plan.patient_id)
        snapshot = TreatmentPlanService._build_plan_snapshot(plan, patient)
        snapshot["confirmed_at"] = plan.confirmed_at.isoformat()
        snapshot["confirmed_by_user_id"] = str(user_id)

        # Create the draft budget alongside the transition. budget is in
        # treatment_plan.manifest.depends so the direct service call is
        # allowed (see treatment_plan/CLAUDE.md "Plan→budget direct
        # call carve-out"). Budget creation is idempotent: if a budget
        # already exists for the plan, BudgetService skips creation.
        from app.modules.budget.service import BudgetService

        budget = await BudgetService.create_from_plan_snapshot(
            db,
            clinic_id=clinic_id,
            user_id=user_id,
            snapshot=snapshot,
        )
        if budget is not None and plan.budget_id is None:
            plan.budget_id = budget.id

        await db.flush()

        await event_bus.publish(EventType.TREATMENT_PLAN_CONFIRMED, snapshot)
        await event_bus.publish(
            EventType.TREATMENT_PLAN_STATUS_CHANGED,
            {
                "plan_id": str(plan.id),
                "old_status": "draft",
                "new_status": "pending",
                "clinic_id": str(clinic_id),
            },
        )
        return plan

    @staticmethod
    async def reopen(
        db: AsyncSession,
        clinic_id: UUID,
        plan_id: UUID,
        user_id: UUID,
    ) -> TreatmentPlan:
        """Reopen a confirmed plan back to ``draft``.

        Cancels the linked budget if there is one (so reception can
        edit items again). The companion budget event is published by
        ``BudgetWorkflowService.cancel_budget``.
        """
        plan = await TreatmentPlanService.get(db, clinic_id, plan_id)
        if not plan:
            raise ValueError("Plan not found")
        if plan.status != "pending":
            raise ValueError(f"Cannot reopen plan in status '{plan.status}'")

        # Cancel linked budget if one exists. The plan ↔ budget unlock
        # is the established carve-out (treatment_plan depends on
        # budget) — see ADR 0003.
        if plan.budget_id and plan.budget is not None and plan.budget.status != "cancelled":
            from app.modules.budget.workflow import BudgetWorkflowService

            await BudgetWorkflowService.cancel_budget(
                db,
                plan.budget,
                user_id,
                reason="Plan reopened for editing",
            )

        plan.status = "draft"
        plan.confirmed_at = None
        await db.flush()

        await event_bus.publish(
            EventType.TREATMENT_PLAN_STATUS_CHANGED,
            {
                "plan_id": str(plan.id),
                "old_status": "pending",
                "new_status": "draft",
                "clinic_id": str(clinic_id),
            },
        )
        return plan

    @staticmethod
    async def close(
        db: AsyncSession,
        clinic_id: UUID,
        plan_id: UUID,
        user_id: UUID,
        closure_reason: str,
        closure_note: str | None = None,
    ) -> TreatmentPlan:
        """Move the plan to terminal ``closed`` state.

        Allowed from ``draft``, ``pending`` or ``active``. The reason
        must be one of the catalogue keys in ``VALID_CLOSURE_REASONS``
        — free-text detail belongs in ``closure_note``.
        """
        if closure_reason not in VALID_CLOSURE_REASONS:
            raise ValueError(f"Unknown closure_reason '{closure_reason}'")

        plan = await TreatmentPlanService.get(db, clinic_id, plan_id)
        if not plan:
            raise ValueError("Plan not found")
        if "closed" not in VALID_PLAN_TRANSITIONS.get(plan.status, set()):
            raise ValueError(f"Cannot close plan in status '{plan.status}'")

        previous_status = plan.status
        plan.status = "closed"
        plan.closure_reason = closure_reason
        plan.closure_note = closure_note
        plan.closed_at = datetime.now(UTC)

        # Drop the plan's hold on its planned Treatments.
        await TreatmentPlanService._cleanup_orphan_planned_treatments(db, clinic_id, plan, user_id)
        await db.flush()

        await event_bus.publish(
            EventType.TREATMENT_PLAN_CLOSED,
            {
                "plan_id": str(plan.id),
                "clinic_id": str(clinic_id),
                "patient_id": str(plan.patient_id),
                "closure_reason": closure_reason,
                "closure_note": closure_note,
                "closed_at": plan.closed_at.isoformat(),
                "closed_by_user_id": str(user_id),
                "previous_status": previous_status,
            },
        )
        await event_bus.publish(
            EventType.TREATMENT_PLAN_STATUS_CHANGED,
            {
                "plan_id": str(plan.id),
                "old_status": previous_status,
                "new_status": "closed",
                "clinic_id": str(clinic_id),
            },
        )
        return plan

    @staticmethod
    async def reactivate(
        db: AsyncSession,
        clinic_id: UUID,
        plan_id: UUID,
        user_id: UUID,
    ) -> TreatmentPlan:
        """Revive a closed plan back to ``draft`` for a new cycle."""
        plan = await TreatmentPlanService.get(db, clinic_id, plan_id)
        if not plan:
            raise ValueError("Plan not found")
        if plan.status != "closed":
            raise ValueError(f"Cannot reactivate plan in status '{plan.status}'")

        previous_reason = plan.closure_reason
        plan.status = "draft"
        plan.closure_reason = None
        plan.closure_note = None
        plan.closed_at = None
        plan.confirmed_at = None
        await db.flush()

        await event_bus.publish(
            EventType.TREATMENT_PLAN_REACTIVATED,
            {
                "plan_id": str(plan.id),
                "clinic_id": str(clinic_id),
                "patient_id": str(plan.patient_id),
                "previous_closure_reason": previous_reason,
                "reactivated_at": datetime.now(UTC).isoformat(),
                "reactivated_by_user_id": str(user_id),
            },
        )
        await event_bus.publish(
            EventType.TREATMENT_PLAN_STATUS_CHANGED,
            {
                "plan_id": str(plan.id),
                "old_status": "closed",
                "new_status": "draft",
                "clinic_id": str(clinic_id),
            },
        )
        return plan

    @staticmethod
    async def accept_from_budget(
        db: AsyncSession,
        clinic_id: UUID,
        plan_id: UUID,
    ) -> TreatmentPlan | None:
        """``pending`` → ``active`` triggered by ``budget.accepted``.

        Idempotent: if the plan is already active or closed, returns the
        current plan without raising.
        """
        plan = await TreatmentPlanService.get(db, clinic_id, plan_id)
        if not plan:
            return None
        if plan.status == "active":
            return plan
        if plan.status != "pending":
            logger.warning(
                "Ignoring budget.accepted for plan %s in status '%s'",
                plan_id,
                plan.status,
            )
            return plan

        plan.status = "active"
        await db.flush()

        await event_bus.publish(
            EventType.TREATMENT_PLAN_STATUS_CHANGED,
            {
                "plan_id": str(plan.id),
                "old_status": "pending",
                "new_status": "active",
                "clinic_id": str(clinic_id),
            },
        )
        return plan

    @staticmethod
    async def reject_from_budget(
        db: AsyncSession,
        clinic_id: UUID,
        plan_id: UUID,
        rejection_note: str | None = None,
    ) -> TreatmentPlan | None:
        """Close the plan in response to ``budget.rejected``.

        Sets ``closure_reason='rejected_by_patient'``. Idempotent: if
        the plan is already closed or beyond pending, no-op.
        """
        plan = await TreatmentPlanService.get(db, clinic_id, plan_id)
        if not plan:
            return None
        if plan.status == "closed":
            return plan
        if plan.status != "pending":
            logger.warning(
                "Ignoring budget.rejected for plan %s in status '%s'",
                plan_id,
                plan.status,
            )
            return plan

        previous_status = plan.status
        plan.status = "closed"
        plan.closure_reason = "rejected_by_patient"
        plan.closure_note = rejection_note
        plan.closed_at = datetime.now(UTC)
        await db.flush()

        await event_bus.publish(
            EventType.TREATMENT_PLAN_CLOSED,
            {
                "plan_id": str(plan.id),
                "clinic_id": str(clinic_id),
                "patient_id": str(plan.patient_id),
                "closure_reason": "rejected_by_patient",
                "closure_note": rejection_note,
                "closed_at": plan.closed_at.isoformat(),
                "closed_by_user_id": None,
                "previous_status": previous_status,
            },
        )
        await event_bus.publish(
            EventType.TREATMENT_PLAN_STATUS_CHANGED,
            {
                "plan_id": str(plan.id),
                "old_status": previous_status,
                "new_status": "closed",
                "clinic_id": str(clinic_id),
            },
        )
        return plan
