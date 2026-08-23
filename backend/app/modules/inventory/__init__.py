"""Inventory module — stock list with low-stock alerts.

Issue #220. Standalone, optional, removable.  No module dependencies.

The module owns inventory categories, items and a low-stock alert
query.  Base version only — cost tracking, stock movements and
auto-deduction come later in the inventory core upgrade (issue #226).

Race condition guard (from #153): stock adjustments use an atomic
``UPDATE … SET quantity = quantity + :delta WHERE quantity + :delta >= 0``
at the DB level.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.core.plugins import BaseModule

from .models import InventoryCategory, InventoryItem
from .router import router


class InventoryModule(BaseModule):
    manifest = {
        "name": "inventory",
        "version": "0.1.0",
        "summary": (
            "Clinic stock list: item tracking, categories, low-stock "
            "alerts, and atomic stock adjustments."
        ),
        "author": "DentalPin Core Team",
        "license": "BSL-1.1",
        "category": "official",
        "depends": [],
        "installable": True,
        "auto_install": False,
        "removable": True,
        "role_permissions": {
            "admin": ["*"],
            "dentist": ["read"],
            "hygienist": ["read"],
            "assistant": ["read"],
            "receptionist": ["read"],
        },
        "frontend": {
            "layer_path": "frontend",
            "navigation": [
                {
                    "label": "nav.inventory",
                    "icon": "i-lucide-package",
                    "to": "/inventory",
                    "permission": "inventory.read",
                    "order": 95,
                },
            ],
        },
    }

    def get_models(self) -> list:
        return [InventoryCategory, InventoryItem]

    def get_router(self) -> APIRouter:
        return router

    def get_permissions(self) -> list[str]:
        return ["read", "write", "delete"]

    def get_event_handlers(self) -> dict:
        return {}

    def get_tools(self) -> list:
        from .tools import get_tools

        return get_tools()
