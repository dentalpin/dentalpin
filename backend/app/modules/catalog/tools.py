"""Agent tools for the catalog module.

Thin wrappers over :class:`CatalogService` — no business logic lives
here. Each tool filters by ``ctx.clinic_id`` (multi-tenancy) and declares
the same RBAC string the HTTP routes use, so an agent can never reach
data the calling user couldn't. See
``docs/technical/copilot-agentic-architecture.md`` §3.
"""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field

from app.core.agents import AgentContext, Tool, ToolCategory

from .service import CatalogService


class ListCatalogItemsArgs(BaseModel):
    search: str | None = Field(
        default=None,
        description="Fragmento de nombre o código interno a buscar (opcional).",
    )
    category_id: UUID | None = Field(default=None, description="Filtrar por categoría (opcional).")
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=50)


class GetCatalogItemArgs(BaseModel):
    item_id: UUID


def _name(names: dict | None) -> str | None:
    if not names:
        return None
    return names.get("es") or names.get("en") or names.get("fr") or next(iter(names.values()), None)


def _summary(item) -> dict:
    return {
        "id": item.id,
        "internal_code": item.internal_code,
        "name": _name(item.names),
        "category": _name(item.category.names) if item.category else None,
        "default_price": item.default_price,
        "default_duration_minutes": item.default_duration_minutes,
        "pricing_strategy": item.pricing_strategy,
        "treatment_scope": item.treatment_scope,
        "requires_appointment": item.requires_appointment,
        "is_active": item.is_active,
    }


async def _list_catalog_items(ctx: AgentContext, params: ListCatalogItemsArgs) -> dict:
    items, total = await CatalogService.list_items(
        ctx.db,
        ctx.clinic_id,
        page=params.page,
        page_size=params.page_size,
        category_id=params.category_id,
        search_query=params.search,
    )
    return {"total": total, "items": [_summary(i) for i in items]}


async def _get_catalog_item(ctx: AgentContext, params: GetCatalogItemArgs) -> dict:
    item = await CatalogService.get_item(ctx.db, ctx.clinic_id, params.item_id)
    if item is None:
        return {"error": "not_found"}
    data = _summary(item)
    data["description"] = _name(item.descriptions)
    data["cost_price"] = item.cost_price
    data["billing_mode"] = item.billing_mode
    data["requires_surfaces"] = item.requires_surfaces
    data["is_diagnostic"] = item.is_diagnostic
    return data


def get_tools() -> list[Tool]:
    return [
        Tool(
            name="list_catalog_items",
            description=(
                "Listar el catálogo de tratamientos de la clínica con su nombre, "
                "código, categoría, precio y duración. Filtra por texto o categoría."
            ),
            parameters=ListCatalogItemsArgs,
            handler=_list_catalog_items,
            permissions=["catalog.read"],
            category=ToolCategory.READ,
        ),
        Tool(
            name="get_catalog_item",
            description="Obtener el detalle de un tratamiento del catálogo por su id.",
            parameters=GetCatalogItemArgs,
            handler=_get_catalog_item,
            permissions=["catalog.read"],
            category=ToolCategory.READ,
        ),
    ]
