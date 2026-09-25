"""Pydantic schemas for the agenda module.

Moved from ``app.modules.clinical.schemas`` in Fase B.2 chunk 1.
Patient-related schemas come from ``app.modules.patients.schemas``.
"""

from datetime import date, datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.modules.patients.schemas import PatientBrief

AppointmentStatus = Literal[
    "scheduled",
    "confirmed",
    "checked_in",
    "in_treatment",
    "completed",
    "cancelled",
    "no_show",
]

# --- Professional brief -------------------------------------------------


class ProfessionalBrief(BaseModel):
    """Brief professional info for appointment references."""

    id: UUID
    first_name: str
    last_name: str

    model_config = ConfigDict(from_attributes=True)


class AppointmentTreatmentNoteUpdate(BaseModel):
    """PATCH body for updating visit-level clinical notes."""

    notes: str | None = None
    completed_in_appointment: bool | None = None


class CheckinTokenResponse(BaseModel):
    """Minted QR check-in token (15-minute TTL, single appointment).

    ``url`` is the patient-facing link, built server-side — the
    frontend copies it verbatim and builds no check-in URLs itself.
    """

    token: str
    expires_at: datetime
    url: str


class CheckinResultResponse(BaseModel):
    """Outcome of a public check-in (minimal PII by design)."""

    appointment_id: UUID
    status: str


class AppointmentTreatmentResponse(BaseModel):
    """Response for a single AppointmentTreatment (visit bridge row)."""

    id: UUID
    appointment_id: UUID
    planned_treatment_item_id: UUID | None = None
    catalog_item_id: UUID | None = None
    display_order: int = 0
    completed_in_appointment: bool = False
    notes: str | None = None
    created_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


# --- Treatment brief ----------------------------------------------------


class AppointmentTreatmentBrief(BaseModel):
    """Brief treatment info for appointment responses.

    Includes data from the planned treatment item and its catalog item.
    """

    id: UUID
    planned_item_id: UUID
    planned_item_status: str  # pending, completed, cancelled
    catalog_item_id: UUID | None = None
    internal_code: str
    names: dict[str, str]
    default_price: float | None = None
    default_duration_minutes: int | None = None
    # Dental context from planned item
    tooth_number: int | None = None
    surfaces: list[str] | None = None
    is_global: bool = False
    # Plan info
    plan_id: UUID | None = None
    plan_number: str | None = None
    # Completion tracking
    completed_in_appointment: bool = False

    @classmethod
    def from_appointment_treatment(cls, apt_treatment: "Any") -> "AppointmentTreatmentBrief":
        """Create from AppointmentTreatment with planned_item + catalog_item loaded."""
        planned_item = apt_treatment.planned_item
        catalog_item = apt_treatment.catalog_item

        treatment = planned_item.treatment if planned_item else None

        if not catalog_item and treatment:
            catalog_item = treatment.catalog_item

        tooth_number = None
        surfaces = None
        is_global = True
        if treatment and treatment.teeth:
            primary = treatment.teeth[0]
            tooth_number = primary.tooth_number
            surfaces = primary.surfaces
            is_global = False

        price: float | None = None
        if treatment and treatment.price_snapshot is not None:
            price = float(treatment.price_snapshot)
        elif catalog_item and catalog_item.default_price is not None:
            price = float(catalog_item.default_price)

        return cls(
            id=apt_treatment.id,
            planned_item_id=apt_treatment.planned_treatment_item_id,
            planned_item_status=planned_item.status if planned_item else "pending",
            catalog_item_id=catalog_item.id if catalog_item else None,
            internal_code=catalog_item.internal_code if catalog_item else "",
            names=catalog_item.names if catalog_item else {},
            default_price=price,
            default_duration_minutes=catalog_item.default_duration_minutes
            if catalog_item
            else None,
            tooth_number=tooth_number,
            surfaces=surfaces,
            is_global=is_global,
            plan_id=planned_item.treatment_plan_id if planned_item else None,
            plan_number=planned_item.treatment_plan.plan_number
            if planned_item and planned_item.treatment_plan
            else None,
            completed_in_appointment=apt_treatment.completed_in_appointment,
        )


# --- Appointment CRUD ---------------------------------------------------


class AppointmentCreate(BaseModel):
    patient_id: UUID | None = None
    professional_id: UUID
    # Callers may send either cabinet_id (preferred) or cabinet name;
    # the service resolves the other side.
    cabinet_id: UUID | None = None
    cabinet: str | None = Field(default=None, min_length=1, max_length=50)
    start_time: datetime
    end_time: datetime
    treatment_type: str | None = Field(default=None, max_length=100)  # Legacy field
    planned_item_ids: list[UUID] | None = None
    color: str | None = Field(default=None, max_length=7)


class AppointmentUpdate(BaseModel):
    patient_id: UUID | None = None
    professional_id: UUID | None = None
    cabinet_id: UUID | None = None
    cabinet: str | None = Field(default=None, min_length=1, max_length=50)
    start_time: datetime | None = None
    end_time: datetime | None = None
    treatment_type: str | None = Field(default=None, max_length=100)
    planned_item_ids: list[UUID] | None = None
    status: str | None = None
    color: str | None = Field(default=None, max_length=7)


class AppointmentStatusTransition(BaseModel):
    """Request body for ``POST /appointments/{id}/transitions``."""

    to_status: AppointmentStatus
    note: str | None = Field(default=None, max_length=500)


class AppointmentCabinetAssignment(BaseModel):
    """Request body for ``PATCH /appointments/{id}/cabinet``.

    ``cabinet_id = None`` unassigns the cabinet (the patient moves back to
    Sala de espera). Supplying the same id currently on the appointment
    is a no-op.
    """

    cabinet_id: UUID | None = None
    note: str | None = Field(default=None, max_length=500)


class AppointmentCabinetEventResponse(BaseModel):
    """Audit trail entry for a cabinet (re)assignment."""

    id: UUID
    from_cabinet_id: UUID | None
    from_cabinet_name: str | None = None
    to_cabinet_id: UUID | None
    to_cabinet_name: str | None = None
    changed_at: datetime
    changed_by: UUID | None
    changed_by_name: str | None = None
    note: str | None

    @model_validator(mode="before")
    @classmethod
    def derive_names(cls, data: Any) -> Any:
        if hasattr(data, "id"):
            from_cab = getattr(data, "from_cabinet", None)
            to_cab = getattr(data, "to_cabinet", None)
            actor = getattr(data, "actor", None)
            actor_name = None
            if actor is not None:
                actor_name = f"{actor.first_name} {actor.last_name}".strip()
            return {
                "id": data.id,
                "from_cabinet_id": data.from_cabinet_id,
                "from_cabinet_name": from_cab.name if from_cab else None,
                "to_cabinet_id": data.to_cabinet_id,
                "to_cabinet_name": to_cab.name if to_cab else None,
                "changed_at": data.changed_at,
                "changed_by": data.changed_by,
                "changed_by_name": actor_name,
                "note": data.note,
            }
        return data

    model_config = ConfigDict(from_attributes=True)


class AppointmentStatusEventResponse(BaseModel):
    """Audit trail entry for an appointment status transition."""

    id: UUID
    from_status: str | None
    to_status: str
    changed_at: datetime
    changed_by: UUID | None
    changed_by_name: str | None = None
    note: str | None

    @model_validator(mode="before")
    @classmethod
    def derive_actor_name(cls, data: Any) -> Any:
        if hasattr(data, "id"):
            actor = getattr(data, "actor", None)
            name = None
            if actor is not None:
                name = f"{actor.first_name} {actor.last_name}".strip()
            return {
                "id": data.id,
                "from_status": data.from_status,
                "to_status": data.to_status,
                "changed_at": data.changed_at,
                "changed_by": data.changed_by,
                "changed_by_name": name,
                "note": data.note,
            }
        return data

    model_config = ConfigDict(from_attributes=True)


class AppointmentResponse(BaseModel):
    id: UUID
    clinic_id: UUID
    patient_id: UUID | None
    professional_id: UUID
    cabinet: str | None = None  # Denormalized name for legacy UI callers.
    cabinet_id: UUID | None = None
    cabinet_assigned_at: datetime | None = None
    cabinet_assigned_by: UUID | None = None
    start_time: datetime
    end_time: datetime
    treatment_type: str | None
    status: str
    current_status_since: datetime
    color: str | None
    created_at: datetime
    updated_at: datetime
    patient: PatientBrief | None = None
    professional: ProfessionalBrief | None = None
    treatments: list[AppointmentTreatmentBrief] = []
    # Only populated on detail endpoints (GET /appointments/{id}) to keep
    # list responses lean. List endpoints leave these as None.
    history: list[AppointmentStatusEventResponse] | None = None
    cabinet_history: list[AppointmentCabinetEventResponse] | None = None

    @model_validator(mode="before")
    @classmethod
    def convert_treatments(cls, data: Any) -> Any:
        """Convert AppointmentTreatment models to AppointmentTreatmentBrief."""
        if hasattr(data, "treatments"):
            treatments_raw = data.treatments
            treatments_list = []
            if treatments_raw:
                for t in treatments_raw:
                    if t.planned_treatment_item_id:
                        treatments_list.append(
                            AppointmentTreatmentBrief.from_appointment_treatment(t)
                        )
            return {
                "id": data.id,
                "clinic_id": data.clinic_id,
                "patient_id": data.patient_id,
                "professional_id": data.professional_id,
                "cabinet": data.cabinet,
                "cabinet_id": data.cabinet_id,
                "cabinet_assigned_at": data.cabinet_assigned_at,
                "cabinet_assigned_by": data.cabinet_assigned_by,
                "start_time": data.start_time,
                "end_time": data.end_time,
                "treatment_type": data.treatment_type,
                "status": data.status,
                "current_status_since": data.current_status_since,
                "color": data.color,
                "created_at": data.created_at,
                "updated_at": data.updated_at,
                "patient": data.patient,
                "professional": data.professional,
                "treatments": treatments_list,
                "history": None,
                "cabinet_history": None,
            }
        return data

    model_config = ConfigDict(from_attributes=True)


# --- Cabinets ----------------------------------------------------------


class CabinetBase(BaseModel):
    name: str = Field(min_length=1, max_length=50)
    color: str = Field(min_length=4, max_length=7, pattern=r"^#[0-9A-Fa-f]{3,6}$")


class CabinetCreate(CabinetBase):
    display_order: int | None = None
    is_active: bool | None = None


class CabinetUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=50)
    color: str | None = Field(
        default=None, min_length=4, max_length=7, pattern=r"^#[0-9A-Fa-f]{3,6}$"
    )
    display_order: int | None = None
    is_active: bool | None = None


class CabinetResponse(CabinetBase):
    id: UUID
    clinic_id: UUID
    display_order: int = 0
    is_active: bool = True

    model_config = ConfigDict(from_attributes=True)


# --- Kanban day (issue #51) --------------------------------------------


ProfessionalState = Literal["free", "in_treatment", "on_break", "off"]


class KanbanProfessionalState(BaseModel):
    """A single pill on the professionals strip of the kanban board."""

    id: UUID
    first_name: str
    last_name: str
    state: ProfessionalState
    current_appointment_id: UUID | None = None
    current_cabinet_id: UUID | None = None


class KanbanDaySnapshot(BaseModel):
    """One-day operational snapshot for the kanban board header."""

    date: date
    clinic_id: UUID
    professionals: list[KanbanProfessionalState]
