"""Agent tools for the supplier_items module. Thin wrappers over SupplierItemService."""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field

from app.core.agents import AgentContext, Tool, ToolCategory

from .schemas import SupplierItemCreate, SupplierItemUpdate
from .service import SupplierItemService


class ListSupplierItemsArgs(BaseModel):
    supplier_id: str | None = Field(default=None, description="UUID of the supplier to filter by")
    inventory_item_id: str | None = Field(
        default=None, description="UUID of the inventory item to filter by"
    )
    limit: int = Field(default=20, ge=1, le=100)


class GetSupplierItemArgs(BaseModel):
    link_id: str = Field(description="UUID of the supplier-item link")


class CreateSupplierItemArgs(BaseModel):
    supplier_id: str = Field(description="UUID of the supplier")
    inventory_item_id: str = Field(description="UUID of the inventory item")
    supplier_sku: str | None = Field(
        default=None, max_length=100, description="Supplier's SKU for the item"
    )
    price: Decimal | None = Field(default=None, ge=0, description="Unit price this supplier quotes")


class UpdateSupplierItemArgs(BaseModel):
    link_id: str = Field(description="UUID of the supplier-item link")
    supplier_sku: str | None = Field(default=None, max_length=100)
    price: Decimal | None = Field(default=None, ge=0)


def _link_summary(link, supplier_name: str, item_name: str) -> dict:
    """Return native values — jsonify at the registry coerces UUID/datetime/Decimal."""
    return {
        "id": link.id,
        "supplier_id": link.supplier_id,
        "supplier_name": supplier_name,
        "inventory_item_id": link.inventory_item_id,
        "item_name": item_name,
        "supplier_sku": link.supplier_sku,
        "price": link.price,
    }


async def _list_supplier_items(ctx: AgentContext, params: ListSupplierItemsArgs) -> dict:
    supplier_id = UUID(params.supplier_id) if params.supplier_id else None
    item_id = UUID(params.inventory_item_id) if params.inventory_item_id else None
    items, total = await SupplierItemService.list_links(
        ctx.db,
        ctx.clinic_id,
        supplier_id=supplier_id,
        inventory_item_id=item_id,
        page=1,
        page_size=params.limit,
    )
    return {
        "total": total,
        "supplier_items": [_link_summary(link, sname, iname) for link, sname, iname in items],
    }


async def _get_supplier_item(ctx: AgentContext, params: GetSupplierItemArgs) -> dict:
    result = await SupplierItemService.get_link(ctx.db, ctx.clinic_id, UUID(params.link_id))
    if not result:
        return {"error": "Supplier item link not found"}
    link, sname, iname = result
    return _link_summary(link, sname, iname)


async def _create_supplier_item(ctx: AgentContext, params: CreateSupplierItemArgs) -> dict:
    payload = SupplierItemCreate(
        supplier_id=UUID(params.supplier_id),
        inventory_item_id=UUID(params.inventory_item_id),
        supplier_sku=params.supplier_sku,
        price=params.price,
    )
    link, sname, iname = await SupplierItemService.create_link(ctx.db, ctx.clinic_id, payload)
    return _link_summary(link, sname, iname)


async def _update_supplier_item(ctx: AgentContext, params: UpdateSupplierItemArgs) -> dict:
    result = await SupplierItemService.get_link(ctx.db, ctx.clinic_id, UUID(params.link_id))
    if not result:
        return {"error": "Supplier item link not found"}
    link, sname, iname = result

    # M4: forward ONLY the fields the agent set, so an omitted price/SKU is
    # not wiped to None on the existing link.
    payload = SupplierItemUpdate(**params.model_dump(exclude_unset=True, exclude={"link_id"}))
    link = await SupplierItemService.update_link(ctx.db, link, payload)
    return _link_summary(link, sname, iname)


def get_all_tools() -> list[Tool]:
    return [
        Tool(
            name="list_supplier_items",
            description="List supplier-item links, optionally filtered by supplier or inventory item",
            category=ToolCategory.READ,
            permissions=["supplier_items.read"],
            handler=_list_supplier_items,
            parameters=ListSupplierItemsArgs,
            # Item/supplier names are user-entered prose that may name
            # people or brands — keep off the cloud LLM path under redaction.
            exposes_free_text=True,
        ),
        Tool(
            name="get_supplier_item",
            description="Get a single supplier-item link (SKU and price) by ID",
            category=ToolCategory.READ,
            permissions=["supplier_items.read"],
            handler=_get_supplier_item,
            parameters=GetSupplierItemArgs,
            exposes_free_text=True,
        ),
        Tool(
            name="create_supplier_item",
            description="Link an inventory item to a supplier with SKU and price",
            category=ToolCategory.WRITE,
            permissions=["supplier_items.write"],
            handler=_create_supplier_item,
            parameters=CreateSupplierItemArgs,
            exposes_free_text=True,
        ),
        Tool(
            name="update_supplier_item",
            description="Update the SKU or price on an existing supplier-item link",
            category=ToolCategory.WRITE,
            permissions=["supplier_items.write"],
            handler=_update_supplier_item,
            parameters=UpdateSupplierItemArgs,
            exposes_free_text=True,
        ),
    ]
