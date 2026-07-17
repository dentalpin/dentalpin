"""Agent tools for the lab_orders module. Thin wrappers over LabOrderService."""

from __future__ import annotations

from datetime import date as date_cls
from uuid import UUID

from pydantic import BaseModel, Field

from app.core.agents import AgentContext, Tool, ToolCategory

from .schemas import LabOrderCreate, OrderStatus, WorkType
from .service import LabOrderService


class ListLabOrdersArgs(BaseModel):
    patient_id: UUID | None = None
    order_status: OrderStatus | None = None
    limit: int = Field(default=20, ge=1, le=100)


class CreateLabOrderArgs(BaseModel):
    patient_id: UUID
    lab_contact_id: UUID
    work_type: WorkType
    tooth_reference: str | None = None
    sent_date: date_cls
    expected_date: date_cls | None = None
    notes: str | None = None


class UpdateLabOrderStatusArgs(BaseModel):
    order_id: UUID
    status: OrderStatus


def _order_summary(order) -> dict:
    return {
        "id": str(order.id),
        "patient_id": str(order.patient_id),
        "lab_contact_id": str(order.lab_contact_id),
        "work_type": order.work_type,
        "status": order.status,
        "sent_date": order.sent_date,
        "expected_date": order.expected_date,
    }


async def _list_lab_orders(ctx: AgentContext, params: ListLabOrdersArgs) -> dict:
    items, total = await LabOrderService.list_orders(
        ctx.db,
        ctx.clinic_id,
        patient_id=params.patient_id,
        order_status=params.order_status,
        page=1,
        page_size=params.limit,
    )
    return {"total": total, "lab_orders": [_order_summary(o) for o in items]}


async def _create_lab_order(ctx: AgentContext, params: CreateLabOrderArgs) -> dict:
    payload = LabOrderCreate(
        patient_id=params.patient_id,
        lab_contact_id=params.lab_contact_id,
        work_type=params.work_type,
        tooth_reference=params.tooth_reference,
        sent_date=params.sent_date,
        expected_date=params.expected_date,
        notes=params.notes,
    )
    order = await LabOrderService.create_order(ctx.db, ctx.clinic_id, payload, ctx.user_id)
    return _order_summary(order)


async def _update_lab_order_status(ctx: AgentContext, params: UpdateLabOrderStatusArgs) -> dict:
    from .schemas import LabOrderUpdate

    order = await LabOrderService.update_order(
        ctx.db, ctx.clinic_id, params.order_id, LabOrderUpdate(status=params.status)
    )
    return _order_summary(order)


def get_tools() -> list[Tool]:
    return [
        Tool(
            name="list_lab_orders",
            description="List lab work orders, optionally filtered by patient or status.",
            parameters=ListLabOrdersArgs,
            handler=_list_lab_orders,
            permissions=["lab_orders.read"],
            category=ToolCategory.READ,
        ),
        Tool(
            name="create_lab_order",
            description="Send a new lab work order for a patient (crown, bridge, denture, etc.).",
            parameters=CreateLabOrderArgs,
            handler=_create_lab_order,
            permissions=["lab_orders.write"],
            category=ToolCategory.WRITE,
        ),
        Tool(
            name="update_lab_order_status",
            description="Update the status of a lab order (sent, in_progress, ready, received, cancelled).",
            parameters=UpdateLabOrderStatusArgs,
            handler=_update_lab_order_status,
            permissions=["lab_orders.write"],
            category=ToolCategory.WRITE,
        ),
    ]
