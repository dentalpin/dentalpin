"""Agent tool for treatment_consumables. Thin wrapper over the service."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel

from app.core.agents import AgentContext, Tool, ToolCategory

from .service import TreatmentConsumablesService


class GetTreatmentConsumablesArgs(BaseModel):
    treatment_id: UUID


async def _get_treatment_consumables(
    ctx: AgentContext, params: GetTreatmentConsumablesArgs
) -> dict:
    links, total = await TreatmentConsumablesService.list_links(
        ctx.db, ctx.clinic_id, catalog_item_id=params.treatment_id, page=1, page_size=100
    )
    detailed = await TreatmentConsumablesService.detailed_links(ctx.db, ctx.clinic_id, links)
    return {
        "total": total,
        "consumables": [
            {
                "inventory_item_id": d["inventory_item_id"],  # native UUID
                "item_name": d["item_name"],
                "quantity": d["quantity"],
                "note": d["note"],
            }
            for d in detailed
        ],
    }


def get_tools() -> list[Tool]:
    return [
        Tool(
            name="get_treatment_consumables",
            description=(
                "List the inventory items a catalog treatment consumes, with the quantity per link."
            ),
            parameters=GetTreatmentConsumablesArgs,
            handler=_get_treatment_consumables,
            permissions=["treatment_consumables.read"],
            category=ToolCategory.READ,
            # Structured mapping data only — cloud-eligible.
        ),
    ]
