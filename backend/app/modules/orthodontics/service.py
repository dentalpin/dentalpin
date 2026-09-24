"""Orthodontics service (issue #270, slice-a: clinical tracking, no money code)."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.events import EventType, event_bus
from app.modules.patients.models import Patient

from .defaults import DEFAULT_PROCEDURES, DEFAULT_WIRES
from .models import CASE_STATUSES, HYGIENE_LEVELS, OrthoCase, OrthoControl, OrthoSettings
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


async def _get_case(db: AsyncSession, clinic_id: UUID, case_id: UUID) -> OrthoCase | None:
    result = await db.execute(
        select(OrthoCase).where(OrthoCase.id == case_id, OrthoCase.clinic_id == clinic_id)
    )
    return result.scalar_one_or_none()


def _control_next_due(control: OrthoControl) -> date | None:
    if control.next_control_weeks is None:
        return None
    return (control.performed_at + timedelta(weeks=control.next_control_weeks)).date()


async def _annotate_case(db: AsyncSession, case: OrthoCase) -> dict:
    # Explicit query — never touch the ``controls`` relationship here:
    # after flush the attribute is expired and lazy-load raises
    # MissingGreenlet in async context.
    result = await db.execute(
        select(OrthoControl)
        .where(OrthoControl.case_id == case.id, OrthoControl.clinic_id == case.clinic_id)
        .order_by(OrthoControl.performed_at)
    )
    controls = list(result.scalars().all())
    last = controls[-1] if controls else None
    return {
        "control_count": len(controls),
        "last_control_at": last.performed_at if last else None,
        "next_due": _control_next_due(last) if last else None,
    }


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
        return [(c, await _annotate_case(db, c)) for c in result.scalars().all()]

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
        return [(c, await _annotate_case(db, c)) for c in result.scalars().all()]

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
        if status in TERMINAL_STATUSES and case.finished_at is None:
            # finished_at is set once and never cleared: the record of when
            # treatment ended survives any later reopen.
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
        return case, await _annotate_case(db, case)


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
        )
        db.add(control)
        if control.upper_wire is not None:
            case.current_upper_wire = control.upper_wire
        if control.lower_wire is not None:
            case.current_lower_wire = control.lower_wire
        await db.flush()
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
    async def seed_count(db: AsyncSession) -> int:
        result = await db.execute(select(func.count(OrthoSettings.id)))
        return result.scalar_one()


async def validate_wire(db: AsyncSession, clinic_id: UUID, wire: str | None) -> None:
    """Wire names should come from the clinic catalog; unknown names are
    allowed (free-text escape hatch) — the UI chips are the guide, not a gate."""
    if wire is None:
        return
    settings = await OrthoSettingsService.get_or_seed(db, clinic_id)
    if wire not in settings.wires and len(wire) > 40:
        raise ValueError("Wire label too long")


async def validate_hygiene(hygiene: str | None) -> None:
    if hygiene is not None and hygiene not in HYGIENE_LEVELS:
        raise ValueError(f"Unknown hygiene level '{hygiene}'")
