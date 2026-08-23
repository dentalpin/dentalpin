"""Agent tools for the inventory module.

Thin wrappers over :class:`InventoryItemService` — no business logic
here.  Every tool filters by ``ctx.clinic_id`` and declares the same
RBAC string as the HTTP routes.

Atomic stock adjustment uses the DB-level guard (issue #153):
``UPDATE … SET quantity = quantity + :delta WHERE quantity + :delta >= 0``.
"""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field

from app.core.agents import AgentContext, Tool, ToolCategory

from .service import InventoryItemService

# --- Argument models ------------------------------------------------------


class ListInventoryArgs(BaseModel):
    search: str | None = Field(default=None, description="Buscar por código, nombre o proveedor.")
    category_id: UUID | None = None
    low_stock: bool = Field(default=False, description="Solo artículos bajo mínimo.")
    limit: int = Field(default=30, ge=1, le=100)


class GetInventoryItemArgs(BaseModel):
    item_id: UUID


class CreateInventoryItemArgs(BaseModel):
    code: str = Field(max_length=50, description="Código único del artículo.")
    name: str = Field(max_length=200, description="Nombre del artículo.")
    category_id: UUID | None = None
    description: str | None = None
    quantity: int = 0
    min_quantity: int = 0
    unit: str = Field(default="units", max_length=20)
    location: str | None = Field(default=None, max_length=200)
    supplier: str | None = Field(default=None, max_length=200)


class AdjustStockArgs(BaseModel):
    item_id: UUID
    delta: int = Field(description="Positivo para añadir, negativo para restar.")
    reason: str | None = Field(default=None, max_length=500)


# --- Helpers --------------------------------------------------------------


def _item_summary(item) -> dict:
    return {
        "id": item.id,
        "code": item.code,
        "name": item.name,
        "quantity": item.quantity,
        "min_quantity": item.min_quantity,
        "unit": item.unit,
        "is_low_stock": item.is_low_stock,
        "status": item.status,
    }


# --- Handlers -------------------------------------------------------------


async def _list_inventory(ctx: AgentContext, params: ListInventoryArgs) -> dict:
    from .service import ItemFilters

    filters = ItemFilters(
        search=params.search,
        category_id=params.category_id,
        low_stock=params.low_stock,
    )
    items, total = await InventoryItemService.list(
        ctx.db, ctx.clinic_id, filters, page=1, page_size=params.limit
    )
    return {"total": total, "items": [_item_summary(i) for i in items]}


async def _get_inventory_item(ctx: AgentContext, params: GetInventoryItemArgs) -> dict:
    item = await InventoryItemService.get(ctx.db, ctx.clinic_id, params.item_id)
    if item is None:
        return {"error": "not_found"}
    return _item_summary(item)


async def _create_inventory_item(ctx: AgentContext, params: CreateInventoryItemArgs) -> dict:
    item = await InventoryItemService.create(
        ctx.db, ctx.clinic_id, params.model_dump(exclude_none=True)
    )
    return {"id": item.id, "code": item.code, "name": item.name, "quantity": item.quantity}


async def _adjust_stock(ctx: AgentContext, params: AdjustStockArgs) -> dict:
    item = await InventoryItemService.adjust_stock(
        ctx.db, ctx.clinic_id, params.item_id, params.delta
    )
    if item is None:
        return {"error": "rejected", "reason": "insufficient_stock_or_not_found"}
    return {
        "id": item.id,
        "code": item.code,
        "quantity": item.quantity,
        "is_low_stock": item.is_low_stock,
    }


def get_tools() -> list[Tool]:
    return [
        Tool(
            name="list_inventory",
            description=(
                "Listar artículos del inventario de la clínica: por nombre, "
                "código, categoría, o solo los que están bajo mínimo de stock."
            ),
            parameters=ListInventoryArgs,
            handler=_list_inventory,
            permissions=["inventory.read"],
            category=ToolCategory.READ,
        ),
        Tool(
            name="get_inventory_item",
            description="Detalle de un artículo del inventario.",
            parameters=GetInventoryItemArgs,
            handler=_get_inventory_item,
            permissions=["inventory.read"],
            category=ToolCategory.READ,
        ),
        Tool(
            name="create_inventory_item",
            description=("Crear un artículo en el inventario. Requiere confirmación del usuario."),
            parameters=CreateInventoryItemArgs,
            handler=_create_inventory_item,
            permissions=["inventory.write"],
            category=ToolCategory.WRITE,
        ),
        Tool(
            name="adjust_stock",
            description=(
                "Ajustar el stock de un artículo (positivo = añadir, "
                "negativo = restar). No permite stock negativo. "
                "Requiere confirmación del usuario."
            ),
            parameters=AdjustStockArgs,
            handler=_adjust_stock,
            permissions=["inventory.write"],
            category=ToolCategory.WRITE,
        ),
    ]
