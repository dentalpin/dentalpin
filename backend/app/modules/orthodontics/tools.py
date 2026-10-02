"""Agent tools for the orthodontics module (issue #270, follow-up Q5).

Thin wrappers over the case/control services — no business logic
here. Every tool filters by ``ctx.clinic_id`` and declares the same
RBAC string as the HTTP routes. ``register_ortho_control`` is
WRITE (it also drives the recall upsert); the two readers omit
free-text notes so they stay cloud-eligible under redaction.
"""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field

from app.core.agents import AgentContext, Tool, ToolCategory

from .schemas import OrthoControlCreate
from .service import OrthoCaseService, OrthoControlService


class GetOrthoCaseStatusArgs(BaseModel):
    case_id: UUID


class ListOverdueOrthoControlsArgs(BaseModel):
    limit: int = Field(default=30, ge=1, le=50)


class RegisterOrthoControlArgs(BaseModel):
    case_id: UUID
    upper_wire: str | None = Field(default=None, max_length=40)
    lower_wire: str | None = Field(default=None, max_length=40)
    procedures: list[str] = Field(default_factory=list, max_length=50)
    procedures_other: str | None = Field(default=None, max_length=2000)
    aligner_number: int | None = Field(default=None, ge=1)
    hygiene: str | None = None
    notes: str | None = Field(default=None, max_length=5000)
    next_control_weeks: int | None = Field(default=None, ge=1, le=52)
    appointment_id: UUID | None = None


def _case_summary(case, annotation: dict) -> dict:
    return {
        "id": case.id,
        "patient_id": case.patient_id,
        "appliance_type": case.appliance_type,
        "status": case.status,
        "current_upper_wire": case.current_upper_wire,
        "current_lower_wire": case.current_lower_wire,
        "control_count": annotation["control_count"],
        "last_control_at": annotation["last_control_at"],
        "next_due": annotation["next_due"],
    }


async def _get_ortho_case_status(ctx: AgentContext, params: GetOrthoCaseStatusArgs) -> dict:
    found = await OrthoCaseService.get(ctx.db, ctx.clinic_id, params.case_id)
    if found is None:
        return {"error": "not_found"}
    case, annotation = found
    return _case_summary(case, annotation)


async def _list_overdue_ortho_controls(
    ctx: AgentContext, params: ListOverdueOrthoControlsArgs
) -> dict:
    rows = await OrthoCaseService.list_overdue(ctx.db, ctx.clinic_id)
    total = len(rows)
    rows = rows[: params.limit]
    return {
        "total": total,
        "cases": [_case_summary(case, annotation) for case, annotation in rows],
    }


async def _register_ortho_control(ctx: AgentContext, params: RegisterOrthoControlArgs) -> dict:
    data = OrthoControlCreate(**params.model_dump(exclude={"case_id"}))
    try:
        control = await OrthoControlService.register(
            ctx.db,
            ctx.clinic_id,
            params.case_id,
            data,
            performed_by=ctx.supervisor_id,
        )
    except LookupError:
        return {"error": "not_found"}
    except ValueError as exc:
        return {"error": "invalid", "detail": str(exc)}
    return {
        "id": control.id,
        "case_id": control.case_id,
        "performed_at": control.performed_at,
        "procedures": control.procedures,
    }


def get_tools() -> list[Tool]:
    return [
        Tool(
            name="get_ortho_case_status",
            description=(
                "Estado de un caso de ortodoncia: aparato, arcos en boca, "
                "progreso de controles y próximo control."
            ),
            parameters=GetOrthoCaseStatusArgs,
            handler=_get_ortho_case_status,
            permissions=["orthodontics.cases.read"],
            category=ToolCategory.READ,
        ),
        Tool(
            name="list_overdue_ortho_controls",
            description=("Casos de ortodoncia activos con el próximo control vencido."),
            parameters=ListOverdueOrthoControlsArgs,
            handler=_list_overdue_ortho_controls,
            permissions=["orthodontics.cases.read"],
            category=ToolCategory.READ,
        ),
        Tool(
            name="register_ortho_control",
            description=(
                "Registrar un control de ortodoncia (arcos, procedimientos, "
                "higiene, próximo control). También programa el recordatorio. "
                "Requiere confirmación del usuario."
            ),
            parameters=RegisterOrthoControlArgs,
            handler=_register_ortho_control,
            permissions=["orthodontics.controls.write"],
            category=ToolCategory.WRITE,
        ),
    ]
