"""Inventory module — simple stock-on-hand list with low-stock alerts.

Standalone module: no dependency on any other module.
"""

from fastapi import APIRouter

from app.core.plugins import BaseModule

from .models import InventoryItem
from .router import router


class InventoryModule(BaseModule):
    """Simple stock list: item, quantity on hand, low-stock threshold."""

    manifest = {
        "name": "inventory",
        "version": "0.1.0",
        "summary": "Simple stock list with quantity on hand and low-stock alerts.",
        "author": "Clinic Custom",
        "license": "BSL-1.1",
        "category": "community",
        "depends": [],
        "installable": True,
        "auto_install": True,
        "removable": True,
        "role_permissions": {
            "admin": ["*"],
            "dentist": ["read"],
            "hygienist": ["read"],
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
        return [InventoryItem]

    def get_router(self) -> APIRouter:
        return router

    def get_permissions(self) -> list[str]:
        return ["read", "write"]

    def get_tools(self) -> list:
        from . import tools

        return tools.get_tools()
