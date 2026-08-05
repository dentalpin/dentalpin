"""inventory_reorder module — Phase 13e. Computes reorder suggestions
from inventory usage history + supplier lead times (13a/13b), and can
generate draft purchase orders (13c) from a chosen set of them.

Pure analytics + one write action — no models of its own; suggestions
are always computed fresh, never stored. Depends on `inventory`
(usage history, item thresholds), `suppliers` (lead_time_days),
`supplier_items` (per-item pricing/preferred supplier), and
`purchase_orders` (to actually create the draft POs). None of those
four depend back on this module, so no dependency cycle.
"""

from fastapi import APIRouter

from app.core.plugins import BaseModule

from .router import router


class InventoryReorderModule(BaseModule):
    manifest = {
        "name": "inventory_reorder",
        "version": "0.1.0",
        "summary": "Reorder suggestions from usage history, and one-click draft PO generation.",
        "author": "Clinic Custom",
        "license": "BSL-1.1",
        "category": "community",
        "depends": ["inventory", "suppliers", "supplier_items", "purchase_orders"],
        "installable": True,
        "auto_install": False,
        "removable": True,
        "role_permissions": {
            "admin": ["*"],
            "assistant": ["read", "write"],
            "receptionist": ["read", "write"],
        },
        "frontend": {
            "layer_path": "frontend",
            "navigation": [
                {
                    "label": "nav.reorderSuggestions",
                    "icon": "i-lucide-refresh-cw",
                    "to": "/reorder-suggestions",
                    "permission": "inventory_reorder.read",
                    "order": 100,
                },
            ],
        },
    }

    def get_models(self) -> list:
        return []

    def get_router(self) -> APIRouter:
        return router

    def get_permissions(self) -> list[str]:
        return ["read", "write"]

    def get_event_handlers(self) -> dict:
        return {}
