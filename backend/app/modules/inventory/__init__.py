"""inventory — stock list with cost tracking, movement ledger and
auto-deduction (roadmap #220 + core upgrade #226).

Per-item minimum quantities, atomic DB-guarded stock changes, an
append-only ``stock_movements`` ledger (the audit trail), ``unit_cost``
with a valuation endpoint, and automatic deduction of linked
consumables when a treatment is performed.

``depends: []`` — treatment_consumables points its FKs *into* this
module, so declaring it back would create a cycle. The auto-deduction
reads the links table fail-soft at runtime instead: absent module →
logged no-op. See docs/technical/inventory/overview.md for the coupling
discussion the roadmap asked for.
"""

from fastapi import APIRouter

from app.core.plugins import BaseModule

from .models import InventoryItem, StockMovement
from .router import router


class InventoryModule(BaseModule):
    """Stock list with movements ledger, costs and auto-deduction."""

    manifest = {
        "name": "inventory",
        "version": "0.2.0",
        "summary": (
            "Stock list with cost tracking, movement ledger, audit trail "
            "and consumable auto-deduction."
        ),
        "author": "lamanji",
        "license": "BSL-1.1",
        "category": "community",
        "depends": [],
        "installable": True,
        # Optional module: ships inactive, the admin activates it from the
        # module admin UI (repo policy for new non-core modules).
        "auto_install": False,
        "removable": True,
        # Stock levels are operational data, not sensitive — the whole team
        # participates (same breadth precedent as patient_relationships).
        "role_permissions": {
            "admin": ["*"],
            "dentist": ["read", "write"],
            "hygienist": ["read", "write"],
            "assistant": ["read", "write"],
            "receptionist": ["read", "write"],
        },
        "frontend": {
            "layer_path": "frontend",
            "navigation": [
                {
                    "label": "nav.inventory",
                    "icon": "i-lucide-package",
                    "to": "/inventory",
                    "permission": "inventory.read",
                    "order": 93,
                },
            ],
        },
    }

    def get_models(self) -> list:
        return [InventoryItem, StockMovement]

    def get_router(self) -> APIRouter:
        return router

    def get_permissions(self) -> list[str]:
        return ["read", "write"]

    def get_tools(self) -> list:
        from . import tools

        return tools.get_tools()

    def get_event_handlers(self) -> dict:
        from app.core.events.types import EventType

        from .events import on_treatment_performed

        # Transactional (the publisher passes db=): deductions commit or
        # roll back together with the treatment performance (ADR 0019).
        return {EventType.ODONTOGRAM_TREATMENT_PERFORMED: on_treatment_performed}
