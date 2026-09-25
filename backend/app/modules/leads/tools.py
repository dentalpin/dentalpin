"""Agent tools for the leads module.

Thin wrappers over LeadService / LeadIntakeService — no business logic
here. Every tool filters by ctx.clinic_id and declares the same RBAC
string as the HTTP route it mirrors.

Deliberate exception to "expose every mutating service method": the
intake key is **not** exposed, neither rotation nor the active toggle.
An LLM that decides to "fix intake" by rotating the key silently breaks
the clinic's website form until a human pastes the new key in, with no
undo — and the clinic would not know why the form went quiet. The right
answer is not to expose it at all, not to expose it as DESTRUCTIVE.
"""

from __future__ import annotations

from datetime import date
from uuid import UUID

from pydantic import BaseModel, Field

from app.core.agents import AgentContext, Tool, ToolCategory

from .schemas import AvailabilitySlot, DayOfWeek, LeadStatus
from .service import LeadIntakeService, LeadService, LeadSettingsService


class ListLeadsArgs(BaseModel):
    status: list[LeadStatus] | None = Field(
        default=None, description="Filtra por estado. Sin valor: todos."
    )
    search: str | None = Field(
        default=None, max_length=200, description="Nombre, teléfono o email."
    )
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=50)
    sort: str | None = Field(
        default=None, description="created_at:desc | full_name:asc | status:asc"
    )


class GetLeadArgs(BaseModel):
    lead_id: UUID


class CreateLeadArgs(BaseModel):
    full_name: str = Field(min_length=1, max_length=200)
    phone: str = Field(min_length=1, max_length=32)
    email: str | None = Field(default=None, max_length=255)
    motive: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=4000)
    availability_days: list[DayOfWeek] | None = Field(
        default=None, max_length=7, description="Días en que se le puede llamar (mon..sun)."
    )
    availability_slot: AvailabilitySlot | None = Field(
        default=None, description="Franja preferida: morning | afternoon | evening."
    )


class UpdateLeadArgs(BaseModel):
    lead_id: UUID
    full_name: str | None = Field(default=None, min_length=1, max_length=200)
    phone: str | None = Field(default=None, min_length=1, max_length=32)
    email: str | None = Field(default=None, max_length=255)
    motive: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=4000)
    availability_days: list[DayOfWeek] | None = Field(default=None, max_length=7)
    availability_slot: AvailabilitySlot | None = None
    status: LeadStatus | None = None


class ConvertLeadArgs(BaseModel):
    lead_id: UUID
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    phone: str | None = Field(default=None, max_length=32)
    email: str | None = Field(default=None, max_length=255)
    national_id: str | None = Field(default=None, max_length=50)
    date_of_birth: date | None = None
    notes: str | None = Field(default=None, max_length=4000)


class UpdateIntakeSettingsArgs(BaseModel):
    daily_cap: int = Field(
        ge=0,
        le=5000,
        description="Máximo de solicitudes aceptadas al día. 0 = sin límite.",
    )


def _lead_summary(lead) -> dict:
    """Row summary — deliberately **without enquirer prose**.

    ``motive`` and ``description`` are free text typed by anyone on the
    internet through the public form, so they must not ride along in a tool
    result: an unflagged tool result is sent to the cloud LLM, and this text
    is both PHI-ish and a prompt-injection surface ("ignore previous
    instructions…" in a description would reach the assistant the next time
    someone asks it to summarise the lead queue).

    Only ``get_lead`` returns it, and only because it declares
    ``exposes_free_text=True``, which keeps that tool off the cloud path under
    redaction. Adding a prose field here re-opens the leak in *five* tools at
    once — `test_tools.py` guards the shape.
    """
    return {
        "id": lead.id,
        "full_name": lead.full_name,
        "phone": lead.phone,
        "email": lead.email,
        "availability_days": lead.availability_days,
        "availability_slot": lead.availability_slot,
        "status": lead.status,
        "patient_id": lead.patient_id,
        "converted_at": lead.converted_at,
        "created_at": lead.created_at,
    }


async def _list_leads(ctx: AgentContext, params: ListLeadsArgs) -> dict:
    items, total = await LeadService.list_leads(
        ctx.db,
        ctx.clinic_id,
        status=params.status,
        search=params.search,
        page=params.page,
        page_size=params.page_size,
        sort=params.sort,
    )
    return {"total": total, "leads": [_lead_summary(lead) for lead in items]}


async def _get_lead(ctx: AgentContext, params: GetLeadArgs) -> dict:
    """The one tool that returns the enquirer's own words.

    It is flagged ``exposes_free_text=True`` below, which is what keeps it off
    the cloud LLM path — the flag and this function have to stay in step.
    """
    lead = await LeadService.get_lead(ctx.db, ctx.clinic_id, params.lead_id)
    if lead is None:
        return {"error": "not_found"}
    data = _lead_summary(lead)
    data["motive"] = lead.motive
    data["description"] = lead.description
    return data


async def _create_lead(ctx: AgentContext, params: CreateLeadArgs) -> dict:
    """Route, never insert blindly.

    A phone/email that already belongs to a patient must not create the
    duplicate lead a human is not allowed to create — it queues a
    call-back instead, and the caller has to say so.
    """
    result = await LeadIntakeService.route(
        ctx.db,
        ctx.clinic_id,
        params.model_dump(),
        recommended_by=ctx.supervisor_id,
    )
    if result.outcome == "lead_created" and result.lead is not None:
        return {"outcome": "lead_created", "lead": _lead_summary(result.lead)}

    first = result.recalled_patients[0] if result.recalled_patients else None
    return {
        "outcome": "recall_queued",
        "recalled_patient": (
            {
                "id": first.id,
                "full_name": f"{first.first_name} {first.last_name}",
                "phone": first.phone,
            }
            if first is not None
            else None
        ),
    }


async def _update_lead(ctx: AgentContext, params: UpdateLeadArgs) -> dict:
    lead = await LeadService.get_lead(ctx.db, ctx.clinic_id, params.lead_id)
    if lead is None:
        return {"error": "not_found"}
    data = params.model_dump(exclude_unset=True, exclude={"lead_id"}, exclude_none=True)
    lead = await LeadService.update_lead(ctx.db, lead, data)
    return _lead_summary(lead)


async def _convert_lead_to_patient(ctx: AgentContext, params: ConvertLeadArgs) -> dict:
    lead = await LeadService.get_lead(ctx.db, ctx.clinic_id, params.lead_id)
    if lead is None:
        return {"error": "not_found"}
    if lead.status == "converted":
        return {"error": "already_converted"}
    patient_data = params.model_dump(exclude={"lead_id"})
    lead, patient = await LeadService.convert(ctx.db, ctx.clinic_id, lead, patient_data)
    return {
        "lead": _lead_summary(lead),
        "patient": {
            "id": patient.id,
            "full_name": f"{patient.first_name} {patient.last_name}",
            "phone": patient.phone,
        },
    }


async def _update_intake_settings(ctx: AgentContext, params: UpdateIntakeSettingsArgs) -> dict:
    settings = await LeadSettingsService.update(
        ctx.db, ctx.clinic_id, {"daily_cap": params.daily_cap}
    )
    return {
        "daily_cap": settings.daily_cap,
        "day_count": settings.day_count,
        "day_count_date": settings.day_count_date,
    }


def get_tools() -> list[Tool]:
    return [
        Tool(
            name="list_leads",
            description=(
                "Listar solicitudes entrantes (leads) de la clínica: por estado, "
                "búsqueda por nombre/teléfono/email, paginadas. No incluye las "
                "solicitudes de pacientes que ya existen: esas van a Recalls."
            ),
            parameters=ListLeadsArgs,
            handler=_list_leads,
            permissions=["leads.read"],
            category=ToolCategory.READ,
        ),
        Tool(
            name="get_lead",
            description="Detalle de una solicitud entrante, incluida su descripción.",
            parameters=GetLeadArgs,
            handler=_get_lead,
            permissions=["leads.read"],
            category=ToolCategory.READ,
            # description is free prose written by the enquirer.
            exposes_free_text=True,
        ),
        Tool(
            name="create_lead",
            description=(
                "Registrar una solicitud entrante. IMPORTANTE: si el teléfono o el "
                "email ya pertenecen a un paciente de la clínica NO se crea ninguna "
                "solicitud; se añade una llamada a Recalls y el resultado es "
                "outcome=recall_queued. En ese caso di al usuario que ya es paciente "
                "y que se ha añadido una llamada, nunca que se ha creado una "
                "solicitud. Requiere confirmación del usuario."
            ),
            parameters=CreateLeadArgs,
            handler=_create_lead,
            permissions=["leads.write"],
            category=ToolCategory.WRITE,
        ),
        Tool(
            name="update_lead",
            description=(
                "Editar una solicitud entrante (corregir teléfono, marcar como "
                "contactada o descartada). Requiere confirmación del usuario."
            ),
            parameters=UpdateLeadArgs,
            handler=_update_lead,
            permissions=["leads.write"],
            category=ToolCategory.WRITE,
        ),
        Tool(
            name="convert_lead_to_patient",
            description=(
                "Convertir una solicitud en paciente: crea la ficha del paciente y "
                "la enlaza con la solicitud. Requiere confirmación del usuario."
            ),
            parameters=ConvertLeadArgs,
            handler=_convert_lead_to_patient,
            permissions=["leads.write"],
            category=ToolCategory.WRITE,
        ),
        Tool(
            name="update_intake_settings",
            description=(
                "Cambiar el límite diario de solicitudes del formulario web "
                "(0 = sin límite). Requiere confirmación del usuario."
            ),
            parameters=UpdateIntakeSettingsArgs,
            handler=_update_intake_settings,
            permissions=["leads.settings.write"],
            category=ToolCategory.WRITE,
        ),
    ]
