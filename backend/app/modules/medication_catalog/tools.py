"""Agent tools for the medication catalog. Thin wrappers over the service."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.core.agents import AgentContext, Tool, ToolCategory

from .service import MedicationCatalogService


class ListMedicationsArgs(BaseModel):
    q: str | None = Field(default=None, max_length=150)
    form: str | None = None
    is_active: bool | None = None
    limit: int = Field(default=20, ge=1, le=100)


async def _list_medications(ctx: AgentContext, params: ListMedicationsArgs) -> dict:
    items, total = await MedicationCatalogService.list_items(
        ctx.db,
        ctx.clinic_id,
        q=params.q,
        form=params.form,
        is_active=params.is_active,
        page=1,
        page_size=params.limit,
    )
    return {
        "total": total,
        "medications": [
            {
                "id": m.id,  # native UUID — the registry's jsonify coerces
                "name": m.name,
                "dose": m.dose,
                "unit": m.unit,
                "form": m.form,
                "requires_prescription": m.requires_prescription,
                "is_active": m.is_active,
            }
            for m in items
        ],
    }


def get_tools() -> list[Tool]:
    return [
        Tool(
            name="list_medications",
            description=(
                "List the clinic's medications (name, dose, unit, form), optionally "
                "filtered by name search, pharmaceutical form or active status."
            ),
            parameters=ListMedicationsArgs,
            handler=_list_medications,
            permissions=["medication_catalog.read"],
            category=ToolCategory.READ,
            # Structured reference data only — no free prose returned, so it
            # stays cloud-eligible under redaction.
        ),
    ]
