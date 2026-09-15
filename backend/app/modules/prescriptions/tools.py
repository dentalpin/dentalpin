"""Agent tools for the prescriptions module.

Thin wrappers over :class:`PrescriptionService` — no business logic here.
Issuing stays human: the agent drafts, a prescriber issues.
"""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field

from app.core.agents import AgentContext, Tool, ToolCategory

from .service import PrescriptionService


class ListPrescriptionsArgs(BaseModel):
    patient_id: UUID


class CreatePrescriptionDraftArgs(BaseModel):
    patient_id: UUID
    notes: str | None = Field(default=None, max_length=2000)


async def _list_prescriptions(ctx: AgentContext, params: ListPrescriptionsArgs) -> dict:
    from fastapi import HTTPException

    try:
        rows = await PrescriptionService.list_for_patient(ctx.db, ctx.clinic_id, params.patient_id)
    except HTTPException:
        await ctx.db.rollback()
        return {"error": "not_found"}
    return {
        "prescriptions": [{"id": r.id, "status": r.status, "issued_at": r.issued_at} for r in rows]
    }


async def _create_prescription_draft(
    ctx: AgentContext, params: CreatePrescriptionDraftArgs
) -> dict:
    from fastapi import HTTPException

    try:
        row = await PrescriptionService.create_draft(
            ctx.db,
            ctx.clinic_id,
            ctx.supervisor_id,
            params.patient_id,
            notes=params.notes,
            locale="es",
            items=[],
        )
    except HTTPException:
        await ctx.db.rollback()
        return {"error": "not_found"}
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
                "Crear un borrador de receta vacío. Solo borrador: la emisión "
                "la hace un prescriptor humano. Requiere confirmación del usuario."
            ),
            parameters=CreatePrescriptionDraftArgs,
            handler=_create_prescription_draft,
            permissions=["prescriptions.write"],
            category=ToolCategory.WRITE,
        ),
    ]
