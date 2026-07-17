"""Agent tools for the inventory module. Thin wrappers over InventoryService."""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field

from app.core.agents import AgentContext, Tool, ToolCategory

from .schemas import InventoryAdjust, InventoryCategory
from .service import InventoryService


class ListInventoryArgs(BaseModel):
    category: InventoryCategory | None = None
    low_stock_only: bool = False
    limit: int = Field(default=20, ge=1, le=100)


class AdjustInventoryArgs(BaseModel):
    item_id: UUID
    delta: Decimal
    note: str | None = None


def _item_summary(item) -> dict:
    return {
        "id": str(item.id),
        "name": item.name,
        "category": item.category,
        "unit": item.unit,
        "quantity_on_hand": item.quantity_on_hand,
        "low_stock_threshold": item.low_stock_threshold,
        "is_low_stock": item.is_low_stock,
    }


async def _list_inventory(ctx: AgentContext, params: ListInventoryArgs) -> dict:
    items, total = await InventoryService.list_items(
        ctx.db,
        ctx.clinic_id,
        category=params.category,
        low_stock_only=params.low_stock_only,
        page=1,
        page_size=params.limit,
    )
    return {"total": total, "items": [_item_summary(i) for i in items]}


async def _adjust_inventory(ctx: AgentContext, params: AdjustInventoryArgs) -> dict:
    item = await InventoryService.adjust_quantity(
        ctx.db,
        ctx.clinic_id,
        params.item_id,
        InventoryAdjust(delta=params.delta, note=params.note),
    )
    return _item_summary(item)


def get_tools() -> list[Tool]:
    return [
        Tool(
            name="list_inventory",
            description="List stock items, optionally filtered by category or low-stock only.",
            parameters=ListInventoryArgs,
            handler=_list_inventory,
            permissions=["inventory.read"],
            category=ToolCategory.READ,
        ),
        Tool(
            name="adjust_inventory",
            description="Adjust a stock item's quantity on hand by a signed amount (negative to consume, positive to restock).",
            parameters=AdjustInventoryArgs,
            handler=_adjust_inventory,
            permissions=["inventory.write"],
            category=ToolCategory.WRITE,
        ),
    ]
