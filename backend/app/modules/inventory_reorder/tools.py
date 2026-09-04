"""Agent tools for the inventory_reorder module. Thin wrappers over the ReorderService."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field

from app.core.agents import AgentContext, Tool, ToolCategory

from .service import ReorderService


class ListReorderSuggestionsArgs(BaseModel):
    limit: int = Field(default=50, ge=1, le=200)


class GenerateReorderOrdersArgs(BaseModel):
    item_ids: list[str] = Field(
        description="UUIDs of the inventory items whose suggestions become POs"
    )


def _suggestion_summary(suggestion: dict) -> dict:
    """Return native values — jsonify at the registry coerces UUID/Decimal."""
    return {
        "inventory_item_id": suggestion["inventory_item_id"],
        "item_name": suggestion["item_name"],
        "category": suggestion["category"],
        "unit": suggestion["unit"],
        "usage_90d": suggestion["usage_90d"],
        "daily_usage": suggestion["daily_usage"],
        "supplier_id": suggestion["supplier_id"],
        "supplier_name": suggestion["supplier_name"],
        "lead_time_days": suggestion["lead_time_days"],
        "unit_price": suggestion["unit_price"],
        "stock_quantity": suggestion["stock_quantity"],
        "on_order": suggestion["on_order"],
        "reorder_point": suggestion["reorder_point"],
        "suggested_quantity": suggestion["suggested_quantity"],
    }


async def _list_reorder_suggestions(ctx: AgentContext, params: ListReorderSuggestionsArgs) -> dict:
    suggestions = await ReorderService.compute_suggestions(ctx.db, ctx.clinic_id)
    return {"total": len(suggestions), "suggestions": [_suggestion_summary(s) for s in suggestions]}


async def _generate_reorder_orders(ctx: AgentContext, params: GenerateReorderOrdersArgs) -> dict:
    if not params.item_ids:
        return {"error": "item_ids must not be empty"}
    # AgentContext carries no acting user (agent_id/session_id only).
    orders = await ReorderService.generate_orders(
        ctx.db, ctx.clinic_id, [UUID(i) for i in params.item_ids], created_by=None
    )
    return {"total": len(orders), "purchase_orders": orders}


def get_all_tools() -> list[Tool]:
    return [
        Tool(
            name="list_reorder_suggestions",
            description="List reorder suggestions computed from 90-day usage, supplier lead times "
            "and open purchase orders",
            category=ToolCategory.READ,
            permissions=["inventory_reorder.read"],
            handler=_list_reorder_suggestions,
            parameters=ListReorderSuggestionsArgs,
            exposes_free_text=True,
        ),
        Tool(
            name="generate_reorder_orders",
            description="Generate draft purchase orders for the given item suggestions, grouped "
            "one per supplier",
            category=ToolCategory.WRITE,
            permissions=["inventory_reorder.write"],
            handler=_generate_reorder_orders,
            parameters=GenerateReorderOrdersArgs,
            exposes_free_text=True,
        ),
    ]
