"""Agent tools for the prescriptions module.

Thin wrappers over :class:`PrescriptionService` — no business logic here.
Issuing stays human: the agent drafts, a prescriber issues.
"""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field

from app.core.agents import AgentContext, Tool, ToolCategory
from app.core.auth.models import Clinic

from .service import PrescriptionService


class ListPrescriptionsArgs(BaseModel):
    patient_id: UUID


class PrescriptionItemArgs(BaseModel):
    # min_length like the REST PrescriptionItemCreate: no blank lines (#1187).
    medication_name: str = Field(min_length=1, max_length=150)
    dosage: str | None = Field(default=None, max_length=50)
    unit: str | None = Field(default=None, max_length=20)
    route: str | None = Field(default=None, max_length=50)
    frequency: str | None = Field(default=None, max_length=100)
    duration: str | None = Field(default=None, max_length=100)
    instructions: str | None = None


class CreatePrescriptionDraftArgs(BaseModel):
    patient_id: UUID
    notes: str | None = Field(default=None, max_length=2000)
    items: list[PrescriptionItemArgs] = Field(default_factory=list)


def _tool_error(exc) -> dict:
    """Map service HTTP errors to agent error codes (agenda precedent)."""
    from fastapi import HTTPException

    if isinstance(exc, HTTPException):
        if exc.status_code == 404:
            return {"error": "not_found"}
        if exc.status_code == 409:
            return {"error": "conflict"}
        if exc.status_code == 422:
            return {"error": "invalid", "detail": str(exc.detail)}
    raise exc


async def _list_prescriptions(ctx: AgentContext, params: ListPrescriptionsArgs) -> dict:
    from fastapi import HTTPException

    try:
        rows = await PrescriptionService.list_for_patient(ctx.db, ctx.clinic_id, params.patient_id)
    except HTTPException as exc:
        # No rollback: a 404 does not poison the session (agenda/tools.py
        # precedent — rollback only on IntegrityError).
        return _tool_error(exc)
    return {
        "prescriptions": [{"id": r.id, "status": r.status, "issued_at": r.issued_at} for r in rows]
    }


async def _create_prescription_draft(
    ctx: AgentContext, params: CreatePrescriptionDraftArgs
) -> dict:
    from fastapi import HTTPException

    # A tool call carries no UI locale (the REST route gets the user's), so
    # the draft takes the clinic's communication language — the one its
    # patient-facing documents use — instead of a hard-coded "es" (#1187).
    clinic = await ctx.db.get(Clinic, ctx.clinic_id)
    locale = (clinic.settings or {}).get("communication_language") if clinic else None
    try:
        row = await PrescriptionService.create_draft(
            ctx.db,
            ctx.clinic_id,
            ctx.supervisor_id,
            params.patient_id,
            notes=params.notes,
            locale=locale or "es",
            items=[item.model_dump() for item in params.items],
        )
    except HTTPException as exc:
        # No rollback: a 404 does not poison the session (agenda/tools.py
        # precedent — rollback only on IntegrityError).
        return _tool_error(exc)
    return {"id": row.id, "status": row.status}


def get_tools() -> list[Tool]:
    return [
        Tool(
            name="list_prescriptions",
            description="Listar las recetas de un paciente (estado y fecha).",
            parameters=ListPrescriptionsArgs,
            handler=_list_prescriptions,
            permissions=["prescriptions.read"],
            category=ToolCategory.READ,
        ),
        Tool(
            name="create_prescription_draft",
            description=(
                "Crear un borrador de receta con líneas de medicamentos. "
                "Solo borrador: la emisión la hace un prescriptor humano. "
                "Requiere confirmación del usuario."
            ),
            parameters=CreatePrescriptionDraftArgs,
            handler=_create_prescription_draft,
            permissions=["prescriptions.write"],
            category=ToolCategory.WRITE,
        ),
    ]
