"""Agent tools for the budget module.

Thin wrappers over :class:`BudgetService` / :class:`BudgetWorkflowService`.
Every tool filters by ``ctx.clinic_id`` and declares the same RBAC string
as the HTTP routes. Amounts are the budget axis only — never mixed with
payments here. ``send_budget`` is DESTRUCTIVE: it messages the patient
by email or WhatsApp (irreversible external side effect). See
``docs/technical/copilot-agentic-architecture.md`` §3.
"""

from __future__ import annotations

from datetime import date as date_cls
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.core.agents import AgentContext, Tool, ToolCategory

from .schemas import BudgetStatus
from .service import BudgetService
from .workflow import BudgetWorkflowError, BudgetWorkflowService


class ListBudgetsArgs(BaseModel):
    status: list[BudgetStatus] | None = Field(
        default=None, description="Filtrar por estados (p. ej. ['sent'] para pendientes)."
    )
    patient_id: UUID | None = None
    date_from: date_cls | None = None
    date_to: date_cls | None = None
    expired: bool | None = None
    limit: int = Field(default=20, ge=1, le=50)


class GetBudgetArgs(BaseModel):
    budget_id: UUID


class SendBudgetArgs(BaseModel):
    budget_id: UUID
    send_method: Literal["manual", "email", "whatsapp"] | None = Field(
        default=None,
        description=(
            "Canal de envío: 'email' o 'whatsapp' (mensaje por la pasarela), "
            "'manual' para marcar entregado en mano. Si se omite, se usa send_email."
        ),
    )
    send_email: bool = Field(
        default=True,
        description="(Legado) True: enviar por email al paciente. False: marcar entregado en mano.",
    )
    custom_message: str | None = Field(default=None, max_length=500)


def _budget_summary(budget) -> dict:
    patient = budget.patient
    return {
        "id": budget.id,
        "number": budget.budget_number,
        "patient_id": budget.patient_id,
        "patient_name": (
            f"{patient.first_name} {patient.last_name}" if patient is not None else None
        ),
        "status": budget.status,
        "total": budget.total,
        "valid_until": budget.valid_until,
        "created_at": budget.created_at,
    }


async def _list_budgets(ctx: AgentContext, params: ListBudgetsArgs) -> dict:
    items, total = await BudgetService.list_budgets(
        ctx.db,
        ctx.clinic_id,
        page=1,
        page_size=params.limit,
        patient_id=params.patient_id,
        status=list(params.status) if params.status else None,
        date_from=params.date_from,
        date_to=params.date_to,
        expired=params.expired,
    )
    return {"total": total, "budgets": [_budget_summary(b) for b in items]}


async def _get_budget(ctx: AgentContext, params: GetBudgetArgs) -> dict:
    budget = await BudgetService.get_budget(
        ctx.db, ctx.clinic_id, params.budget_id, include_items=True
    )
    if budget is None:
        return {"error": "not_found"}
    data = _budget_summary(budget)
    data["items"] = [
        {"description": i.description, "quantity": i.quantity, "total": i.line_total}
        for i in budget.items
    ]
    return data


async def _send_budget(ctx: AgentContext, params: SendBudgetArgs) -> dict:
    budget = await BudgetService.get_budget(
        ctx.db, ctx.clinic_id, params.budget_id, include_items=True
    )
    if budget is None:
        return {"error": "not_found"}

    send_method = params.send_method or ("email" if params.send_email else "manual")

    recipient_email = None
    if send_method == "email":
        # patient is joinedloaded by get_budget — no cross-module import.
        if budget.patient is None or not budget.patient.email:
            return {
                "error": "no_patient_email",
                "detail": "El paciente no tiene email registrado.",
            }
        recipient_email = budget.patient.email
    elif send_method == "whatsapp":
        if budget.patient is None or not budget.patient.phone:
            return {
                "error": "no_patient_phone",
                "detail": "El paciente no tiene teléfono registrado.",
            }

    try:
        budget = await BudgetWorkflowService.send_budget(
            ctx.db,
            budget,
            sent_by=ctx.supervisor_id,
            send_method=send_method,
            recipient_email=recipient_email,
            custom_message=params.custom_message,
        )
    except BudgetWorkflowError as e:
        return {"error": "workflow_error", "detail": str(e), "status": budget.status}
    return {
        "id": budget.id,
        "status": budget.status,
        "send_method": send_method,
        "recipient_email": recipient_email,
    }


def get_tools() -> list[Tool]:
    return [
        Tool(
            name="list_budgets",
            description=(
                "Listar presupuestos de la clínica: por estado (draft, sent, "
                "accepted, completed, rejected, expired, cancelled), paciente, "
                "fechas o vencidos."
            ),
            parameters=ListBudgetsArgs,
            handler=_list_budgets,
            permissions=["budget.read"],
            category=ToolCategory.READ,
        ),
        Tool(
            name="get_budget",
            description="Detalle de un presupuesto con sus líneas.",
            parameters=GetBudgetArgs,
            handler=_get_budget,
            permissions=["budget.read"],
            category=ToolCategory.READ,
        ),
        Tool(
            name="send_budget",
            description=(
                "Enviar un presupuesto al paciente por email o WhatsApp (o "
                "marcarlo como entregado en mano). Acción irreversible: "
                "requiere confirmación."
            ),
            parameters=SendBudgetArgs,
            handler=_send_budget,
            permissions=["budget.write"],
            category=ToolCategory.DESTRUCTIVE,
        ),
    ]
