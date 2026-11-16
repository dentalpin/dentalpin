"""Treatment plan module Pydantic schemas."""

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

# ---------------------------------------------------------------------------
# Nested brief schemas
# ---------------------------------------------------------------------------


class PatientBrief(BaseModel):
    """Brief patient info."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    first_name: str
    last_name: str


class BudgetBrief(BaseModel):
    """Brief budget info."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    budget_number: str
    status: str
    total: float


class TreatmentToothBrief(BaseModel):
    """Per-tooth member of a Treatment, embedded in plan items."""

    model_config = ConfigDict(from_attributes=True)

    tooth_number: int
    role: str | None = None
    surfaces: list[str] | None = None


class CatalogItemBrief(BaseModel):
    """Brief catalog item info."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    internal_code: str
    names: dict
    default_price: float | None = None
    default_duration_minutes: int | None = None


class TreatmentBrief(BaseModel):
    """Brief Treatment info (header + teeth)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    clinical_type: str
    scope: str
    arch: str | None = None
    status: str
    catalog_item_id: UUID | None = None
    catalog_item: CatalogItemBrief | None = None
    price_snapshot: Decimal | None = None
    notes: str | None = None
    teeth: list[TreatmentToothBrief] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Treatment Plan schemas
# ---------------------------------------------------------------------------


class TreatmentPlanCreate(BaseModel):
    """Create a treatment plan."""

    patient_id: UUID
    title: str | None = Field(default=None, max_length=200)
    assigned_professional_id: UUID | None = None
    diagnosis_notes: str | None = None
    internal_notes: str | None = None


class TreatmentPlanUpdate(BaseModel):
    """Update a treatment plan."""

    title: str | None = Field(default=None, max_length=200)
    assigned_professional_id: UUID | None = None
    diagnosis_notes: str | None = None
    internal_notes: str | None = None
    # Write-only directive. When ``True`` and the doctor of the plan changes,
    # pending items still pointing at the previous doctor are reassigned in
    # the same transaction. Items with an explicit override (different doctor)
    # and completed items are never touched.
    reassign_pending_items: bool = False


class TreatmentPlanStatusUpdate(BaseModel):
    """Change plan status."""

    status: str = Field(..., pattern="^(draft|pending|active|completed|archived|closed)$")


class ClosePlanRequest(BaseModel):
    """Body for ``POST /treatment-plans/{id}/close``."""

    closure_reason: str = Field(
        ...,
        pattern=("^(rejected_by_patient|expired|cancelled_by_clinic|patient_abandoned|other)$"),
    )
    closure_note: str | None = Field(default=None, max_length=2000)


class ContactLogRequest(BaseModel):
    """Body for ``POST /treatment-plans/{id}/contact-log``.

    Records a non-state-changing reception touchpoint with the patient
    so the bandeja can sort by ``last_contact``.
    """

    channel: str = Field(..., pattern="^(call|whatsapp|email|in_person|other)$")
    note: str | None = Field(default=None, max_length=1000)


class PipelineBudgetBrief(BaseModel):
    """Budget metadata embedded in a pipeline row."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    status: str
    total: float | None = None
    valid_until: date | None = None
    last_reminder_sent_at: datetime | None = None
    viewed_at: datetime | None = None


class PipelineNextAppointment(BaseModel):
    """Compact representation of the next scheduled appointment."""

    id: UUID
    start_at: datetime
    cabinet_id: UUID | None = None
    professional_id: UUID | None = None


class PipelineRow(BaseModel):
    """One row in the bandeja de planes (``GET /pipeline``)."""

    plan_id: UUID
    plan_number: str
    plan_title: str | None = None
    plan_status: str
    days_in_status: int
    closure_reason: str | None = None
    items_total: int
    items_completed: int
    patient: PatientBrief
    budget: PipelineBudgetBrief | None = None
    next_appointment: PipelineNextAppointment | None = None


class TreatmentPlanResponse(BaseModel):
    """Response for treatment plan list."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    clinic_id: UUID
    patient_id: UUID
    plan_number: str
    title: str | None
    status: str
    budget_id: UUID | None
    assigned_professional_id: UUID | None
    created_by: UUID
    created_at: datetime
    updated_at: datetime
    item_count: int = 0
    completed_count: int = 0
    total: float = 0.0
    # Closure metadata — set while ``status == "closed"``; the reactivate
    # dialog shows the previous reason.
    closure_reason: str | None = None
    closure_note: str | None = None
    closed_at: datetime | None = None
    patient: PatientBrief | None = None
    budget: BudgetBrief | None = None


class TreatmentPlanDetailResponse(TreatmentPlanResponse):
    """Detailed response with nested items."""

    diagnosis_notes: str | None = None
    internal_notes: str | None = None
    items: list["PlannedTreatmentItemResponse"] = []


# ---------------------------------------------------------------------------
# Planned treatment item schemas
# ---------------------------------------------------------------------------


class PlannedTreatmentItemCreate(BaseModel):
    """Add a treatment to a plan by Treatment id."""

    treatment_id: UUID
    sequence_order: int | None = None
    notes: str | None = None
    # When omitted, the service inherits the plan's ``assigned_professional_id``.
    # Pass an explicit value to override at creation time.
    assigned_professional_id: UUID | None = None


class PlannedTreatmentItemUpdate(BaseModel):
    """Update a planned treatment item (scheduling metadata only)."""

    sequence_order: int | None = None
    notes: str | None = None
    # Nullable: passing ``None`` explicitly clears the assignment. The router
    # serializes with ``exclude_unset=True`` so omitting the field leaves the
    # item untouched.
    assigned_professional_id: UUID | None = None


class PlannedItemSessionResponse(BaseModel):
    """One billing / execution step inside a plan item."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    sequence: int
    label: str | None
    amount: Decimal
    status: str  # pending|completed|cancelled
    completed_at: datetime | None
    completed_by: UUID | None
    notes: str | None


class PlannedTreatmentItemResponse(BaseModel):
    """Response for planned treatment item."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    clinic_id: UUID
    treatment_plan_id: UUID
    treatment_id: UUID
    sequence_order: int
    status: str
    completed_without_appointment: bool
    completed_at: datetime | None
    completed_by: UUID | None
    assigned_professional_id: UUID | None
    notes: str | None
    created_at: datetime
    updated_at: datetime

    # Embedded Treatment + optional catalog item.
    treatment: TreatmentBrief | None = None
    catalog_item: CatalogItemBrief | None = None
    sessions: list[PlannedItemSessionResponse] = Field(default_factory=list)


class SessionInput(BaseModel):
    """Manual session input — used when adding/editing sessions on a plan item.

    ``sequence`` may be omitted (server assigns by array position).
    """

    sequence: int | None = Field(default=None, ge=1)
    label: str | None = Field(default=None, max_length=120)
    amount: Decimal = Field(ge=0)


class CompleteSessionRequest(BaseModel):
    """Mark one session of a plan item as completed."""

    completed_without_appointment: bool = False
    notes: str | None = None


class UpdateSessionRequest(BaseModel):
    """Edit a pending session (label / amount / notes)."""

    label: str | None = Field(default=None, max_length=120)
    amount: Decimal | None = Field(default=None, ge=0)
    notes: str | None = None


class CompleteItemRequest(BaseModel):
    """Mark an item as completed.

    Clinical-note capture moved to the ``clinical_notes`` module: the client
    POSTs the note via ``/api/v1/clinical_notes/notes`` after a successful
    completion. ``notes`` (free-text annotation on the item itself) stays —
    it's the legacy one-line memo, not a clinical_notes entry.
    """

    completed_without_appointment: bool = True
    notes: str | None = None


class ReorderItemsRequest(BaseModel):
    """Reorder all items of a plan in a single atomic update.

    `item_ids` MUST cover exactly the plan's current items — no missing, no extras.
    `sequence_order` is rewritten as 0, 1, 2, ... in the given order.
    """

    item_ids: list[UUID]


# ---------------------------------------------------------------------------
# Budget integration schemas
# ---------------------------------------------------------------------------


class LinkBudgetRequest(BaseModel):
    budget_id: UUID


class GenerateBudgetResponse(BaseModel):
    budget_id: UUID
    budget_number: str


# Media attachment schemas live in the ``media`` module since issue #55 —
# call ``POST /api/v1/media/attachments`` with ``owner_type='plan_item'``
# instead of the previous ``POST /treatment-plans/items/{id}/media``.
#
# Clinical-note schemas moved to the ``clinical_notes`` module — see issue #60.

TreatmentPlanDetailResponse.model_rebuild()
