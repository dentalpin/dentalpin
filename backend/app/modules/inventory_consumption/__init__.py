"""inventory_consumption — connects `treatment_consumables` to `inventory`.

Phase 12b. Pure glue, same shape as `recall_reminders` (Phase 6): no
models, no UI, no API surface of its own. It exists as a THIRD module
rather than adding "treatment_consumables" to `inventory`'s own
`depends`, because `treatment_consumables` already depends on
`["catalog", "inventory"]` — a direct two-way dependency would be
circular and would very likely break module install-order resolution
at startup. This module depends on both and sits between them instead.

Subscribes to `treatment_plan.treatment_completed` (published as a
literal string in treatment_plan/service.py, not via the EventType
constant — same value, `EventType.TREATMENT_PLAN_TREATMENT_COMPLETED`,
so subscribing via the constant still matches). For every
TreatmentConsumable row linked to the completed treatment's catalog
item, records a "used" InventoryMovement (negative delta) via
InventoryService.record_movement — which already publishes
INVENTORY_MOVEMENT_RECORDED, so nothing extra is needed for that part.
"""

from fastapi import APIRouter

from app.core.plugins import BaseModule


class InventoryConsumptionModule(BaseModule):
    manifest = {
        "name": "inventory_consumption",
        "version": "0.1.0",
        "summary": "Auto-deducts consumed inventory items when a planned treatment is completed.",
        "author": "Clinic Custom",
        "license": "BSL-1.1",
        "category": "community",
        "depends": ["inventory", "treatment_consumables"],
        "installable": True,
        "auto_install": False,
        "removable": True,
        "role_permissions": {"admin": ["*"]},
        "frontend": {
            "layer_path": "frontend",
            "navigation": [],  # pure backend glue, nothing to show
        },
    }

    def get_models(self) -> list:
        return []

    def get_router(self) -> APIRouter:
        return APIRouter()

    def get_permissions(self) -> list[str]:
        return []

    def get_event_handlers(self) -> dict:
        # Official extension point only (bug #4) — a manual subscribe()
        # in __init__ double-fires under DENTALPIN_DEV_MODULE_SCAN's
        # filesystem-scan fallback.
        from .handlers import _on_treatment_completed
        from app.core.events import EventType

        return {EventType.TREATMENT_PLAN_TREATMENT_COMPLETED: _on_treatment_completed}
