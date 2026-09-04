"""supplier_items - links inventory items to their suppliers.

Supports the "multiple vendors per item" model: an inventory item can be
sourced from several suppliers, each with its own SKU and unit price.
Feeds purchase_orders (#227-3) and inventory_reorder (#227-4).
"""

from __future__ import annotations

from fastapi import APIRouter

from app.core.plugins import BaseModule

from .models import SupplierItem
from .router import router


class SupplierItemsModule(BaseModule):
    """Supplier<->inventory link table with per-vendor SKU and price."""

    manifest = {
        "name": "supplier_items",
        "version": "0.1.0",
        "summary": "Links inventory items to suppliers (multi-vendor, SKU and price).",
        "author": "lamanji",
        "license": "BSL-1.1",
        "category": "official",
        # Direct imports: Supplier and InventoryItem models. contacts is
        # declared for the Contact.name join used to denormalize supplier
        # names in list/detail responses.
        "depends": ["contacts", "inventory", "suppliers"],
        "installable": True,
        "auto_install": False,
        "removable": True,
        # Same role matrix as suppliers: front-desk maintains the vendor
        # directory and its item links.
        "role_permissions": {
            "admin": ["*"],
            "dentist": ["read"],
            "hygienist": ["read"],
            "assistant": ["read", "write"],
            "receptionist": ["read", "write"],
        },
    }

    def get_models(self) -> list:
        return [SupplierItem]

    def get_router(self) -> APIRouter:
        return router

    def get_tools(self) -> list:
        from .tools import get_all_tools

        return get_all_tools()

    def get_permissions(self) -> list[str]:
        return ["read", "write"]
