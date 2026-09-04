"""inventory_reorder - reorder suggestions from 90-day usage and supplier lead times.

Pure computation module (#227-4): no tables of its own. Computes per-item
reorder suggestions (usage in the last 90 days vs. the preferred
supplier's lead time, net of stock on hand and quantity already on open
purchase orders) and can turn a selection of those suggestions into draft
purchase orders, grouped one per supplier. Executes the reorder
"policy"; purchase_orders owns the order lifecycle.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.core.plugins import BaseModule

from .router import router


class InventoryReorderModule(BaseModule):
    """Reorder suggestions + draft PO generation for the procurement suite."""

    manifest = {
        "name": "inventory_reorder",
        "version": "0.1.0",
        "summary": "Reorder suggestions from 90-day usage and supplier lead times; generates draft purchase orders.",
        "author": "lamanji",
        "license": "BSL-1.1",
        "category": "official",
        "depends": ["contacts", "inventory", "suppliers", "supplier_items", "purchase_orders"],
        "installable": True,
        "auto_install": False,
        "removable": True,
        # Same posture as purchase_orders: front-desk and assistants run
        # replenishment; clinicians get read-only visibility.
        "role_permissions": {
            "admin": ["*"],
            "dentist": ["read"],
            "hygienist": ["read"],
            "assistant": ["read", "write"],
            "receptionist": ["read", "write"],
        },
    }

    def get_models(self) -> list:
        # Pure computation — no tables of its own.
        return []

    def get_router(self) -> APIRouter:
        return router

    def get_tools(self) -> list:
        from .tools import get_all_tools

        return get_all_tools()

    def get_permissions(self) -> list[str]:
        return ["read", "write"]
