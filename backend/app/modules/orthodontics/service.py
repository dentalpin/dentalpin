"""Orthodontics service (issue #270).

Slice-a: clinical tracking. Slice-b: optional treatment-plan link
(one quote, monthly collection via plan sessions), recall upsert,
appointment link, session audit pointer. No money is ever written
here — collection stays in the payments screen (ADR 0010).
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.events import EventType, event_bus
from app.modules.agenda.models import Appointment
from app.modules.patients.models import Patient
from app.modules.recalls.service import RecallService
from app.modules.treatment_plan.service import TreatmentPlanService

from .defaults import DEFAULT_PROCEDURES, DEFAULT_WIRES
from .models import CASE_STATUSES, OrthoCase, OrthoControl, OrthoSettings
from .schemas import (
    OrthoCaseCreate,
    OrthoCaseUpdate,
    OrthoControlCreate,
    OrthoControlUpdate,
)

TERMINAL_STATUSES = ("finished", "transferred_out")

# Explicit status machine (issue #505 review): every transition not listed
# here is refused. ``finished`` reopens only to ``active`` (patients come
# back); ``transferred_out`` is terminal (the patient left the practice).
# Same-status is accepted as a note update, not a transition.
VALID_TRANSITIONS: dict[str, list[str]] = {
    "active": ["paused", "finished", "transferred_out"],
    "paused": ["active", "finished", "transferred_out"],
    "finished": ["active"],
    "transferred_out": [],
}


def can_transition(current_status: str, new_status: str) -> bool:
    """Check if a status transition is valid (same-status is a note update)."""
    if new_status == current_status:
        return True
    return new_status in VALID_TRANSITIONS.get(current_status, [])


async def _require_patient(db: AsyncSession, clinic_id: UUID, patient_id: UUID) -> Patient:
    result = await db.execute(
        select(Patient).where(Patient.id == patient_id, Patient.clinic_id == clinic_id)
    )
    patient = result.scalar_one_or_none()
    if patient is None:
        raise LookupError("Patient not found in this clinic")
    return patient


async def _require_professional_member(db: AsyncSession, clinic_id: UUID, user_id: UUID) -> None:
    """The case's named treating orthodontist must be a professional
    member (L32: check clinic_memberships, never bare users)."""
    from app.core.auth.models import ClinicMembership

    result = await db.execute(
        select(ClinicMembership.id).where(
            ClinicMembership.clinic_id == clinic_id,
            ClinicMembership.user_id == user_id,
            ClinicMembership.is_professional.is_(True),
        )
    )
    if result.scalar_one_or_none() is None:
        raise ValueError("Invalid professional for this clinic")


async def _require_member(db: AsyncSession, clinic_id: UUID, user_id: UUID) -> None:
    """Control authors must belong to the clinic; the permission gate
    (controls.write) already decides who may register, so an admin
    without the professional flag is accepted."""
    from app.core.auth.models import ClinicMembership

    result = await db.execute(
        select(ClinicMembership.id).where(
            ClinicMembership.clinic_id == clinic_id,
            ClinicMembership.user_id == user_id,
        )
    )
    if result.scalar_one_or_none() is None:
        raise ValueError("Invalid member for this clinic")


async def _require_linked_session(
    db: AsyncSession, clinic_id: UUID, case: OrthoCase, session_id: UUID
) -> None:
    """The control's session pointer must name a session of the case's
    linked plan item — never an arbitrary (or another clinic's) UUID."""
    if case.treatment_plan_id is None or case.plan_item_id is None:
        raise ValueError("Link a treatment plan item before pointing at its sessions")
    plan = await TreatmentPlanService.get(db, clinic_id, case.treatment_plan_id)
    if plan is None:
        raise LookupError("Linked treatment plan not found")
    item = next((i for i in plan.items or [] if i.id == case.plan_item_id), None)
    if item is None:
        raise LookupError("Linked plan item not found")
    if all(s.id != session_id for s in item.sessions or []):
        raise ValueError("Session does not belong to the linked plan item")


async def _require_appointment(
    db: AsyncSession, clinic_id: UUID, patient_id: UUID, appointment_id: UUID
) -> None:
    result = await db.execute(
        select(Appointment.id).where(
            Appointment.id == appointment_id,
            Appointment.clinic_id == clinic_id,
            Appointment.patient_id == patient_id,
        )
    )
    if result.scalar_one_or_none() is None:
        raise ValueError("Invalid appointment for this patient and clinic")


async def _require_plan_item(
    db: AsyncSession, clinic_id: UUID, patient_id: UUID, plan_id: UUID, item_id: UUID
) -> None:
    """The linked plan must belong to the case's patient; the item must
    belong to the plan. Read through TreatmentPlanService so plan-side
    invariants (deleted_at, scoping) stay in one place."""
    plan = await TreatmentPlanService.get(db, clinic_id, plan_id)
    if plan is None or plan.patient_id != patient_id:
        raise ValueError("Invalid treatment plan for this patient and clinic")
    if all(item.id != item_id for item in plan.items or []):
        raise ValueError("Item does not belong to the treatment plan")


async def _get_case(db: AsyncSession, clinic_id: UUID, case_id: UUID) -> OrthoCase | None:
    result = await db.execute(
        select(OrthoCase).where(OrthoCase.id == case_id, OrthoCase.clinic_id == clinic_id)
    )
    return result.scalar_one_or_none()


def _control_next_due(control: OrthoControl) -> date | None:
    if control.next_control_weeks is None:
        return None
    return (control.performed_at + timedelta(weeks=control.next_control_weeks)).date()


def _installment_label(installment_labels: list[str] | None, month: int) -> str:
    """Caller-provided (translated) label, else the legacy English one."""
    if installment_labels:
        return installment_labels[month - 1]
    return f"Installment {month}"


async def _annotate_cases(db: AsyncSession, cases: list[OrthoCase]) -> list[dict]:
    """Control stats + patient name for a batch of cases (two queries total)."""
    if not cases:
        return []
    ids = [c.id for c in cases]
    clinic_id = cases[0].clinic_id
    controls = (
        await db.execute(
            select(OrthoControl)
            .where(OrthoControl.case_id.in_(ids), OrthoControl.clinic_id == clinic_id)
            .order_by(OrthoControl.performed_at)
        )
    ).scalars()
    by_case: dict[UUID, list[OrthoControl]] = {}
    for control in controls:
        by_case.setdefault(control.case_id, []).append(control)
    patients = await db.execute(
        select(Patient.id, Patient.first_name, Patient.last_name).where(
            Patient.id.in_({c.patient_id for c in cases}), Patient.clinic_id == clinic_id
        )
    )
    names = {pid: f"{first} {last}" for pid, first, last in patients.all()}
    out = []
    for case in cases:
        rows = by_case.get(case.id, [])
        last = rows[-1] if rows else None
        out.append(
            {
                "patient_name": names.get(case.patient_id),
                "control_count": len(rows),
                "last_control_at": last.performed_at if last else None,
                "next_due": _control_next_due(last) if last else None,
                "plan_close_suggested": False,
            }
        )
    return out


async def _annotate_case(db: AsyncSession, case: OrthoCase) -> dict:
    return (await _annotate_cases(db, [case]))[0]


class OrthoCaseService:
    @staticmethod
    async def create(
        db: AsyncSession, clinic_id: UUID, data: OrthoCaseCreate, created_by: UUID | None = None
    ) -> tuple[OrthoCase, dict]:
        await _require_patient(db, clinic_id, data.patient_id)
        if data.professional_id is not None:
            await _require_professional_member(db, clinic_id, data.professional_id)
        case = OrthoCase(
            clinic_id=clinic_id,
            patient_id=data.patient_id,
            appliance_type=data.appliance_type,
            status="active",
            start_date=data.start_date,
            estimated_months=data.estimated_months,
            professional_id=data.professional_id,
            diagnosis_notes=data.diagnosis_notes,
        )
        db.add(case)
        await db.flush()
        await event_bus.publish(
            EventType.ORTHODONTICS_CASE_CREATED,
            {
                "case_id": str(case.id),
                "clinic_id": str(clinic_id),
                "patient_id": str(case.patient_id),
                "appliance_type": case.appliance_type,
            },
        )
        return case, await _annotate_case(db, case)

    @staticmethod
    async def get(
        db: AsyncSession, clinic_id: UUID, case_id: UUID
    ) -> tuple[OrthoCase, dict] | None:
        case = await _get_case(db, clinic_id, case_id)
        if case is None:
            return None
        return case, await _annotate_case(db, case)

    @staticmethod
    async def list_for_patient(
        db: AsyncSession, clinic_id: UUID, patient_id: UUID
    ) -> list[tuple[OrthoCase, dict]]:
        result = await db.execute(
            select(OrthoCase)
            .where(OrthoCase.clinic_id == clinic_id, OrthoCase.patient_id == patient_id)
            .order_by(OrthoCase.start_date.desc())
        )
        cases = list(result.scalars().all())
        return list(zip(cases, await _annotate_cases(db, cases), strict=True))

    @staticmethod
    async def list_active(
        db: AsyncSession, clinic_id: UUID, status: str | None = None
    ) -> list[tuple[OrthoCase, dict]]:
        query = select(OrthoCase).where(OrthoCase.clinic_id == clinic_id)
        if status is not None:
            if status not in CASE_STATUSES:
                raise ValueError(f"Unknown status '{status}'")
            query = query.where(OrthoCase.status == status)
        query = query.order_by(OrthoCase.start_date.desc())
        result = await db.execute(query)
        cases = list(result.scalars().all())
        return list(zip(cases, await _annotate_cases(db, cases), strict=True))

    @staticmethod
    async def list_overdue(db: AsyncSession, clinic_id: UUID) -> list[tuple[OrthoCase, dict]]:
        """Active/paused cases whose latest next-due date is past."""
        rows = await OrthoCaseService.list_active(db, clinic_id)
        today = date.today()
        return [
            (case, annotation)
            for case, annotation in rows
            if case.status in ("active", "paused")
            and annotation["next_due"] is not None
            and annotation["next_due"] < today
        ]

    @staticmethod
    async def update(
        db: AsyncSession, clinic_id: UUID, case_id: UUID, data: OrthoCaseUpdate
    ) -> tuple[OrthoCase, dict] | None:
        case = await _get_case(db, clinic_id, case_id)
        if case is None:
            return None
        patch = data.model_dump(exclude_unset=True)
        if patch.get("professional_id") is not None:
            await _require_professional_member(db, clinic_id, patch["professional_id"])
        for key, value in patch.items():
            setattr(case, key, value)
        await db.flush()
        return case, await _annotate_case(db, case)

    @staticmethod
    async def change_status(
        db: AsyncSession, clinic_id: UUID, case_id: UUID, status: str, note: str | None
    ) -> tuple[OrthoCase, dict] | None:
        if status not in CASE_STATUSES:
            raise ValueError(f"Unknown status '{status}'")
        case = await _get_case(db, clinic_id, case_id)
        if case is None:
            return None
        previous = case.status
        if not can_transition(previous, status):
            raise ValueError(f"Cannot move case from '{previous}' to '{status}'")
        previous_finished_at = case.finished_at
        case.status = status
        case.status_note = note
        if status in TERMINAL_STATUSES and previous not in TERMINAL_STATUSES:
            # finished_at is never cleared: a reopen keeps it (the reopen is
            # stamped below) and a later re-finish moves it to the real end;
            # the value it replaces travels in the event.
            case.finished_at = datetime.now(UTC)
        if previous == "finished" and status == "active":
            # Explicit reopen path: stamps the reopen, keeps finished_at.
            case.reopened_at = datetime.now(UTC)
        await db.flush()
        await event_bus.publish(
            EventType.ORTHODONTICS_CASE_STATUS_CHANGED,
            {
                "case_id": str(case.id),
                "clinic_id": str(clinic_id),
                "patient_id": str(case.patient_id),
                "previous_status": previous,
                "status": status,
                "previous_finished_at": (
                    previous_finished_at.isoformat() if previous_finished_at is not None else None
                ),
            },
        )
        annotation = await _annotate_case(db, case)
        # transferred_out with a linked plan: prompt (don't force) the
        # plan close — the plan is the financial record (Q3).
        annotation["plan_close_suggested"] = bool(
            status == "transferred_out" and case.treatment_plan_id is not None
        )
        return case, annotation

    @staticmethod
    async def link_plan(
        db: AsyncSession, clinic_id: UUID, case_id: UUID, plan_id: UUID, item_id: UUID
    ) -> tuple[OrthoCase, dict] | None:
        case = await _get_case(db, clinic_id, case_id)
        if case is None:
            return None
        await _require_plan_item(db, clinic_id, case.patient_id, plan_id, item_id)
        case.treatment_plan_id = plan_id
        case.plan_item_id = item_id
        await db.flush()
        return case, await _annotate_case(db, case)

    @staticmethod
    async def unlink_plan(
        db: AsyncSession, clinic_id: UUID, case_id: UUID
    ) -> tuple[OrthoCase, dict] | None:
        case = await _get_case(db, clinic_id, case_id)
        if case is None:
            return None
        case.treatment_plan_id = None
        case.plan_item_id = None
        await db.flush()
        return case, await _annotate_case(db, case)

    @staticmethod
    async def generate_schedule(
        db: AsyncSession,
        clinic_id: UUID,
        case_id: UUID,
        down_payment: Decimal,
        months: int,
        monthly_amount: Decimal,
        down_payment_label: str | None = None,
        installment_labels: list[str] | None = None,
    ) -> dict:
        """Build the installment schedule through the plan's session
        API — never raw rows — so the plan-owns-lines (#176) and
        repricing (#243) invariants hold. Money is booked later, one
        session at a time, from the payments screen (ADR 0010).

        The new sessions REPLACE the item's pending ones (added first,
        then the old pending rows removed via ``delete_session``), so a
        real item — which always ships a default session worth the full
        line price — never ends up double-counted. The new total must
        equal the pending amount (#270, 5.2); completed sessions refuse
        the whole operation rather than being silently rewritten.
        """
        case = await _get_case(db, clinic_id, case_id)
        if case is None:
            raise LookupError("Case not found in this clinic")
        if case.treatment_plan_id is None or case.plan_item_id is None:
            raise ValueError("Link a treatment plan item before generating installments")
        plan = await TreatmentPlanService.get(db, clinic_id, case.treatment_plan_id)
        if plan is None:
            raise LookupError("Linked treatment plan not found")
        item = next((i for i in plan.items or [] if i.id == case.plan_item_id), None)
        if item is None:
            raise LookupError("Linked plan item not found")
        if any(s.status == "completed" for s in item.sessions or []):
            raise ValueError("Item already has completed sessions")
        if installment_labels is not None and len(installment_labels) != months:
            raise ValueError("installment_labels must hold exactly one label per month")
        pending = [s for s in item.sessions or [] if s.status == "pending"]
        pending_total = sum((s.amount for s in pending), Decimal("0"))
        new_total = down_payment + months * monthly_amount
        if new_total != pending_total:
            raise ValueError(
                f"Schedule total {new_total} does not match pending amount {pending_total}"
            )
        await TreatmentPlanService.add_session_manual(
            db,
            clinic_id,
            case.treatment_plan_id,
            case.plan_item_id,
            {"label": down_payment_label or "Down payment", "amount": down_payment},
        )
        for month in range(1, months + 1):
            await TreatmentPlanService.add_session_manual(
                db,
                clinic_id,
                case.treatment_plan_id,
                case.plan_item_id,
                {
                    "label": _installment_label(installment_labels, month),
                    "amount": monthly_amount,
                },
            )
        for old in pending:
            await TreatmentPlanService.delete_session(
                db, clinic_id, case.treatment_plan_id, case.plan_item_id, old.id
            )
        await db.flush()
        return await OrthoCaseService.installments(db, clinic_id, case_id)

    @staticmethod
    async def installments(db: AsyncSession, clinic_id: UUID, case_id: UUID) -> dict:
        case = await _get_case(db, clinic_id, case_id)
        if case is None:
            raise LookupError("Case not found in this clinic")
        if case.treatment_plan_id is None or case.plan_item_id is None:
            raise ValueError("No treatment plan linked to this case")
        plan = await TreatmentPlanService.get(db, clinic_id, case.treatment_plan_id)
        if plan is None:
            raise LookupError("Linked treatment plan not found")
        item = next((i for i in plan.items or [] if i.id == case.plan_item_id), None)
        if item is None:
            raise LookupError("Linked plan item not found")
        sessions = sorted(item.sessions or [], key=lambda s: s.sequence)
        # Read-only projection: paid/earned diffs are never surfaced
        # (ADR 0010) — counts only, amounts per session row.
        return {
            "treatment_plan_id": case.treatment_plan_id,
            "plan_item_id": case.plan_item_id,
            "sessions": [
                {
                    "id": s.id,
                    "sequence": s.sequence,
                    "label": s.label,
                    "amount": s.amount,
                    "status": s.status,
                }
                for s in sessions
            ],
            "completed_count": sum(1 for s in sessions if s.status == "completed"),
            "pending_count": sum(1 for s in sessions if s.status == "pending"),
        }


async def _refresh_current_wires(db: AsyncSession, case: OrthoCase) -> None:
    """Re-derive "in mouth now" from the latest control that set each arch
    (an edited control may change or clear a wire)."""
    controls = (
        await db.execute(
            select(OrthoControl)
            .where(OrthoControl.case_id == case.id, OrthoControl.clinic_id == case.clinic_id)
            .order_by(OrthoControl.performed_at.desc())
        )
    ).scalars()
    upper = lower = None
    for control in controls:
        upper = upper or control.upper_wire
        lower = lower or control.lower_wire
        if upper and lower:
            break
    case.current_upper_wire = upper
    case.current_lower_wire = lower
    await db.flush()


class OrthoControlService:
    @staticmethod
    async def register(
        db: AsyncSession,
        clinic_id: UUID,
        case_id: UUID,
        data: OrthoControlCreate,
        performed_by: UUID | None = None,
    ) -> OrthoControl:
        case = await _get_case(db, clinic_id, case_id)
        if case is None:
            raise LookupError("Case not found in this clinic")
        if case.status in TERMINAL_STATUSES:
            raise ValueError(f"Cannot register controls on a {case.status} case")
        if performed_by is not None:
            await _require_member(db, clinic_id, performed_by)
        if data.appointment_id is not None:
            await _require_appointment(db, clinic_id, case.patient_id, data.appointment_id)
        if data.session_id is not None:
            await _require_linked_session(db, clinic_id, case, data.session_id)
        control = OrthoControl(
            clinic_id=clinic_id,
            case_id=case.id,
            performed_at=data.performed_at or datetime.now(UTC),
            performed_by=performed_by,
            upper_wire=data.upper_wire,
            lower_wire=data.lower_wire,
            procedures=list(data.procedures),
            procedures_other=data.procedures_other,
            aligner_number=data.aligner_number,
            hygiene=data.hygiene,
            notes=data.notes,
            next_control_weeks=data.next_control_weeks,
            appointment_id=data.appointment_id,
            session_id=data.session_id,
        )
        db.add(control)
        if control.upper_wire is not None:
            case.current_upper_wire = control.upper_wire
        if control.lower_wire is not None:
            case.current_lower_wire = control.lower_wire
        await db.flush()
        # Next-control recall (duplicate-guarded upsert). Paused cases
        # freeze generation (Q3); terminal cases can't register at all.
        if control.next_control_weeks is not None and case.status != "paused":
            due = _control_next_due(control)
            if due is None:
                raise ValueError("Cannot compute the next control date")
            await RecallService.create(
                db,
                clinic_id,
                {
                    "patient_id": case.patient_id,
                    "reason": "ortho_review",
                    "due_month": date(due.year, due.month, 1),
                    "due_date": due,
                    "reason_note": f"Control de ortodoncia ({case.id})",
                    "assigned_professional_id": case.professional_id,
                },
                recommended_by=performed_by,
            )
        await event_bus.publish(
            EventType.ORTHODONTICS_CONTROL_REGISTERED,
            {
                "case_id": str(case.id),
                "control_id": str(control.id),
                "clinic_id": str(clinic_id),
                "patient_id": str(case.patient_id),
                "upper_wire": control.upper_wire,
                "lower_wire": control.lower_wire,
                "procedures": control.procedures,
                "next_due": _control_next_due(control).isoformat()
                if _control_next_due(control)
                else None,
            },
        )
        return control

    @staticmethod
    async def update(
        db: AsyncSession, clinic_id: UUID, control_id: UUID, data: OrthoControlUpdate
    ) -> OrthoControl | None:
        result = await db.execute(
            select(OrthoControl).where(
                OrthoControl.id == control_id, OrthoControl.clinic_id == clinic_id
            )
        )
        control = result.scalar_one_or_none()
        if control is None:
            return None
        for key, value in data.model_dump(exclude_unset=True).items():
            setattr(control, key, value)
        await db.flush()
        case = await _get_case(db, clinic_id, control.case_id)
        if case is not None:
            await _refresh_current_wires(db, case)
        return control

    @staticmethod
    async def list_for_case(
        db: AsyncSession, clinic_id: UUID, case_id: UUID
    ) -> list[OrthoControl] | None:
        case = await _get_case(db, clinic_id, case_id)
        if case is None:
            return None
        result = await db.execute(
            select(OrthoControl)
            .where(OrthoControl.case_id == case.id, OrthoControl.clinic_id == clinic_id)
            .order_by(OrthoControl.performed_at.desc())
        )
        return list(result.scalars().all())


class OrthoSettingsService:
    @staticmethod
    async def get_or_seed(db: AsyncSession, clinic_id: UUID) -> OrthoSettings:
        result = await db.execute(select(OrthoSettings).where(OrthoSettings.clinic_id == clinic_id))
        settings = result.scalar_one_or_none()
        if settings is None:
            settings = OrthoSettings(
                clinic_id=clinic_id,
                wires=list(DEFAULT_WIRES),
                procedures=list(DEFAULT_PROCEDURES),
            )
            db.add(settings)
            await db.flush()
        return settings

    @staticmethod
    async def update(
        db: AsyncSession, clinic_id: UUID, wires: list[str], procedures: list[str]
    ) -> OrthoSettings:
        settings = await OrthoSettingsService.get_or_seed(db, clinic_id)
        settings.wires = [w.strip() for w in wires if w.strip()][:100]
        settings.procedures = [p.strip() for p in procedures if p.strip()][:100]
        await db.flush()
        return settings
