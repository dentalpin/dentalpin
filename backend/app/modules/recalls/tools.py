"""Agent tools for the recalls module.

Thin wrappers over :class:`RecallService` — no business logic here.
Every tool filters by ``ctx.clinic_id`` and declares the same RBAC
string as the HTTP routes. ``list_due_recalls`` keeps the service's
default exclusions (archived patients, ``do_not_contact``) and omits
``reason_note`` so the result stays cloud-eligible under redaction;
``get_recall`` returns the free-text notes and is therefore marked
``exposes_free_text=True``. See
``docs/technical/copilot-agentic-architecture.md`` §3.
"""

from __future__ import annotations

from datetime import date as date_cls
from uuid import UUID

from pydantic import BaseModel, Field

from app.core.agents import AgentContext, Tool, ToolCategory

from .schemas import Channel, Outcome, Priority, Reason, Status
from .service import RecallClosedError, RecallFilters, RecallService


class ListDueRecallsArgs(BaseModel):
    month: date_cls | None = Field(
        default=None, description="Cualquier día del mes objetivo (se normaliza a mes)."
    )
    overdue: bool = Field(
        default=False, description="Solo recalls activos vencidos (mes anterior al actual)."
    )
    status: Status | None = None
    priority: Priority | None = None
    patient_id: UUID | None = None
    limit: int = Field(default=30, ge=1, le=50)


class GetRecallArgs(BaseModel):
    recall_id: UUID


class CreateRecallArgs(BaseModel):
    patient_id: UUID
    reason: Reason
    due_month: date_cls = Field(description="Mes objetivo (cualquier día del mes).")
    priority: Priority | None = None
    reason_note: str | None = Field(default=None, max_length=500)
    assigned_professional_id: UUID | None = None


class LogContactAttemptArgs(BaseModel):
    recall_id: UUID
    channel: Channel
    outcome: Outcome
    note: str | None = Field(default=None, max_length=500)
    linked_appointment_id: UUID | None = Field(
        default=None, description="Cita creada a raíz de la llamada (outcome=scheduled)."
    )


class SnoozeRecallArgs(BaseModel):
    recall_id: UUID
    months: int = Field(ge=1, le=24)
    reason_note: str | None = Field(default=None, max_length=500)


class CompleteRecallArgs(BaseModel):
    recall_id: UUID


def _recall_summary(recall) -> dict:
    patient = getattr(recall, "patient", None)
    return {
        "id": recall.id,
        "patient_id": recall.patient_id,
        "patient_name": (
            f"{patient.first_name} {patient.last_name}" if patient is not None else None
        ),
        "phone": patient.phone if patient is not None else None,
        "due_month": recall.due_month,
        "reason": recall.reason,
        "priority": recall.priority,
        "status": recall.status,
        "contact_attempt_count": recall.contact_attempt_count,
        "last_contact_attempt_at": recall.last_contact_attempt_at,
    }


async def _list_due_recalls(ctx: AgentContext, params: ListDueRecallsArgs) -> dict:
    filters = RecallFilters(
        month=params.month,
        overdue=params.overdue,
        status=params.status,
        priority=params.priority,
        patient_id=params.patient_id,
    )
    items, total = await RecallService.list(
        ctx.db, ctx.clinic_id, filters, page=1, page_size=params.limit
    )
    return {"total": total, "recalls": [_recall_summary(r) for r in items]}


async def _get_recall(ctx: AgentContext, params: GetRecallArgs) -> dict:
    recall, attempts = await RecallService.get_with_attempts(
        ctx.db, ctx.clinic_id, params.recall_id
    )
    if recall is None:
        return {"error": "not_found"}
    data = _recall_summary(recall)
    data["reason_note"] = recall.reason_note
    data["linked_appointment_id"] = recall.linked_appointment_id
    data["attempts"] = [
        {
            "attempted_at": a.attempted_at,
            "channel": a.channel,
            "outcome": a.outcome,
            "note": a.note,
        }
        for a in attempts
    ]
    return data


async def _create_recall(ctx: AgentContext, params: CreateRecallArgs) -> dict:
    recall, created = await RecallService.create(
        ctx.db,
        ctx.clinic_id,
        params.model_dump(exclude_none=True),
        recommended_by=ctx.supervisor_id,
    )
    return {
        "id": recall.id,
        "created": created,
        "due_month": recall.due_month,
        "status": recall.status,
    }


async def _log_contact_attempt(ctx: AgentContext, params: LogContactAttemptArgs) -> dict:
    try:
        result = await RecallService.log_attempt(
            ctx.db,
            ctx.clinic_id,
            params.recall_id,
            {
                "channel": params.channel,
                "outcome": params.outcome,
                "note": params.note,
                "linked_appointment_id": params.linked_appointment_id,
            },
            by_user=ctx.supervisor_id,
        )
    except RecallClosedError:
        return {"error": "recall_closed"}
    if result is None:
        return {"error": "not_found"}
    recall, _attempt = result
    return {
        "id": recall.id,
        "status": recall.status,
        "contact_attempt_count": recall.contact_attempt_count,
    }


async def _snooze_recall(ctx: AgentContext, params: SnoozeRecallArgs) -> dict:
    try:
        recall = await RecallService.snooze(
            ctx.db,
            ctx.clinic_id,
            params.recall_id,
            months=params.months,
            reason_note=params.reason_note,
            by_user=ctx.supervisor_id,
        )
    except RecallClosedError:
        return {"error": "recall_closed"}
    if recall is None:
        return {"error": "not_found"}
    return {"id": recall.id, "due_month": recall.due_month, "status": recall.status}


async def _complete_recall(ctx: AgentContext, params: CompleteRecallArgs) -> dict:
    try:
        recall = await RecallService.mark_done(
            ctx.db, ctx.clinic_id, params.recall_id, by_user=ctx.supervisor_id
        )
    except RecallClosedError:
        return {"error": "recall_closed"}
    if recall is None:
        return {"error": "not_found"}
    return {"id": recall.id, "status": recall.status}


def get_tools() -> list[Tool]:
    return [
        Tool(
            name="list_due_recalls",
            description=(
                "Listar recalls (rellamadas a pacientes) pendientes: por mes, "
                "vencidos, por estado/prioridad o por paciente. Excluye "
                "pacientes archivados y con do_not_contact."
            ),
            parameters=ListDueRecallsArgs,
            handler=_list_due_recalls,
            permissions=["recalls.read"],
            category=ToolCategory.READ,
        ),
        Tool(
            name="get_recall",
            description="Detalle de un recall, incluidas notas e intentos de contacto.",
            parameters=GetRecallArgs,
            handler=_get_recall,
            permissions=["recalls.read"],
            category=ToolCategory.READ,
            exposes_free_text=True,
        ),
        Tool(
            name="create_recall",
            description=(
                "Crear un recall (rellamada futura) para un paciente. Si ya "
                "existe uno activo con el mismo motivo, se actualiza ese "
                "(created=false). Requiere confirmación del usuario."
            ),
            parameters=CreateRecallArgs,
            handler=_create_recall,
            permissions=["recalls.write"],
            category=ToolCategory.WRITE,
        ),
        Tool(
            name="log_contact_attempt",
            description=(
                "Registrar un intento de contacto de un recall (canal + "
                "resultado). Con outcome=scheduled enlaza la cita creada. "
                "Requiere confirmación del usuario."
            ),
            parameters=LogContactAttemptArgs,
            handler=_log_contact_attempt,
            permissions=["recalls.write"],
            category=ToolCategory.WRITE,
        ),
        Tool(
            name="snooze_recall",
            description="Posponer un recall N meses. Requiere confirmación del usuario.",
            parameters=SnoozeRecallArgs,
            handler=_snooze_recall,
            permissions=["recalls.write"],
            category=ToolCategory.WRITE,
        ),
        Tool(
            name="complete_recall",
            description="Marcar un recall como completado. Requiere confirmación del usuario.",
            parameters=CompleteRecallArgs,
            handler=_complete_recall,
            permissions=["recalls.write"],
            category=ToolCategory.WRITE,
        ),
    ]
