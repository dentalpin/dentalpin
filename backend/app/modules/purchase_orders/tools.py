"""Agent tools for the purchase_orders module. Thin wrappers over PurchaseOrderService."""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field

from app.core.agents import AgentContext, Tool, ToolCategory

from .schemas import (
    PurchaseOrderCreate,
    PurchaseOrderLineCreate,
    PurchaseReceiptCreate,
    ReceiptLineCreate,
)
from .service import PurchaseOrderService


class ListPurchaseOrdersArgs(BaseModel):
    order_status: str | None = Field(default=None, description="PO status to filter by")
    supplier_id: str | None = Field(default=None, description="UUID of the supplier to filter by")
    limit: int = Field(default=20, ge=1, le=100)


class GetPurchaseOrderArgs(BaseModel):
    order_id: str = Field(description="UUID of the purchase order")


class CreatePurchaseOrderArgs(BaseModel):
    supplier_id: str = Field(description="UUID of the supplier contact")
    expected_date: str | None = Field(default=None, description="ISO date the goods are expected")
    notes: str | None = Field(default=None)
    line_item_ids: list[str] = Field(description="UUIDs of the inventory items to order")
    line_quantities: list[Decimal] = Field(
        description="Ordered quantity per line, parallel to line_item_ids"
    )


class TransitionPurchaseOrderArgs(BaseModel):
    order_id: str = Field(description="UUID of the purchase order")
    status: str = Field(description="Target status: draft, sent, confirmed or cancelled")


class ReceivePurchaseOrderArgs(BaseModel):
    order_id: str = Field(description="UUID of the purchase order")
    line_ids: list[str] = Field(description="UUIDs of the PO lines being delivered")
    quantities: list[Decimal] = Field(
        description="Received quantity per line, parallel to line_ids"
    )
    quality: list[str] = Field(
        default_factory=lambda: [],
        description="Per-line quality verdict: good (moves stock) or rejected",
    )


def _order_summary(response: dict) -> dict:
    """Return native values — jsonify at the registry coerces UUID/datetime/Decimal."""
    return {
        "id": response["id"],
        "supplier_id": response["supplier_id"],
        "supplier_name": response["supplier_name"],
        "status": response["status"],
        "expected_date": response["expected_date"],
        "notes": response["notes"],
        "received_at": response["received_at"],
        "lines": [
            {
                "inventory_item_id": line["inventory_item_id"],
                "item_name": line["item_name"],
                "quantity_ordered": line["quantity_ordered"],
                "quantity_received": line["quantity_received"],
                "unit_price": line["unit_price"],
            }
            for line in response["lines"]
        ],
    }


async def _get_response(ctx: AgentContext, order_id: UUID) -> dict:
    return await PurchaseOrderService.get_order_response(ctx.db, ctx.clinic_id, order_id)


async def _list_purchase_orders(ctx: AgentContext, params: ListPurchaseOrdersArgs) -> dict:
    supplier_id = UUID(params.supplier_id) if params.supplier_id else None
    orders, total = await PurchaseOrderService.list_order_responses(
        ctx.db,
        ctx.clinic_id,
        order_status=params.order_status,
        supplier_id=supplier_id,
        page=1,
        page_size=params.limit,
    )
    return {"total": total, "purchase_orders": [_order_summary(o) for o in orders]}


async def _get_purchase_order(ctx: AgentContext, params: GetPurchaseOrderArgs) -> dict:
    return _order_summary(await _get_response(ctx, UUID(params.order_id)))


async def _create_purchase_order(ctx: AgentContext, params: CreatePurchaseOrderArgs) -> dict:
    if len(params.line_item_ids) != len(params.line_quantities):
        return {"error": "line_quantities must be parallel to line_item_ids"}
    payload = PurchaseOrderCreate(
        supplier_id=UUID(params.supplier_id),
        expected_date=params.expected_date,
        notes=params.notes,
        lines=[
            PurchaseOrderLineCreate(
                inventory_item_id=UUID(item_id),
                quantity_ordered=quantity,
            )
            for item_id, quantity in zip(params.line_item_ids, params.line_quantities)
        ],
    )
    # AgentContext carries no acting user (agent_id/session_id only).
    order = await PurchaseOrderService.create_order(ctx.db, ctx.clinic_id, payload, created_by=None)
    return _order_summary(await _get_response(ctx, order.id))


async def _transition_purchase_order(
    ctx: AgentContext, params: TransitionPurchaseOrderArgs
) -> dict:
    order = await PurchaseOrderService.transition_order(
        ctx.db, ctx.clinic_id, UUID(params.order_id), params
    )
    return _order_summary(await _get_response(ctx, order.id))


async def _receive_purchase_order(ctx: AgentContext, params: ReceivePurchaseOrderArgs) -> dict:
    if not params.line_ids or len(params.line_ids) != len(params.quantities):
        return {"error": "quantities must be parallel to line_ids and non-empty"}
    quality = list(params.quality) if params.quality else ["good"] * len(params.line_ids)
    if len(quality) != len(params.line_ids):
        return {"error": "quality list must be parallel to line_ids"}
    payload = PurchaseReceiptCreate(
        lines=[
            ReceiptLineCreate(
                purchase_order_line_id=UUID(line_id),
                quantity_received=quantity,
                quality=verdict,
            )
            for line_id, quantity, verdict in zip(params.line_ids, params.quantities, quality)
        ]
    )
    order = await PurchaseOrderService.receive_order(
        ctx.db, ctx.clinic_id, UUID(params.order_id), payload, received_by=None
    )
    return _order_summary(await _get_response(ctx, order.id))


def get_all_tools() -> list[Tool]:
    return [
        Tool(
            name="list_purchase_orders",
            description="List purchase orders, optionally filtered by status or supplier",
            category=ToolCategory.READ,
            permissions=["purchase_orders.read"],
            handler=_list_purchase_orders,
            parameters=ListPurchaseOrdersArgs,
            exposes_free_text=True,
        ),
        Tool(
            name="get_purchase_order",
            description="Get a purchase order and its lines by ID",
            category=ToolCategory.READ,
            permissions=["purchase_orders.read"],
            handler=_get_purchase_order,
            parameters=GetPurchaseOrderArgs,
            exposes_free_text=True,
        ),
        Tool(
            name="create_purchase_order",
            description="Create a purchase order (draft) from inventory items",
            category=ToolCategory.WRITE,
            permissions=["purchase_orders.write"],
            handler=_create_purchase_order,
            parameters=CreatePurchaseOrderArgs,
            exposes_free_text=True,
        ),
        Tool(
            name="transition_purchase_order",
            description="Change a purchase order status (draft -> sent -> confirmed, or cancel)",
            category=ToolCategory.WRITE,
            permissions=["purchase_orders.write"],
            handler=_transition_purchase_order,
            parameters=TransitionPurchaseOrderArgs,
            exposes_free_text=True,
        ),
        Tool(
            name="receive_purchase_order",
            description="Receive a delivery against a PO; only good lines move stock",
            category=ToolCategory.WRITE,
            permissions=["purchase_orders.write"],
            handler=_receive_purchase_order,
            parameters=ReceivePurchaseOrderArgs,
            exposes_free_text=True,
        ),
    ]
