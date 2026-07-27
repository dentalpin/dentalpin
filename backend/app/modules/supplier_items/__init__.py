"""supplier_items module — links inventory items to supplier contacts
with per-supplier pricing (Phase 13b).

Depends on `contacts` (validate contact_type == "supplier"),
`inventory` (validate item exists), and `suppliers` (join in
lead_time_days for display) — reads all three, writes to none.
"""

from fastapi import APIRouter

from app.core.plugins import BaseModule

from .models import SupplierItem
from .router import router


class SupplierItemsModule(BaseModule):
    manifest = {
        "name": "supplier_items",
        "version": "0.1.0",
        "summary": "Links inventory items to supplier contacts with per-supplier pricing.",
        "author": "Clinic Custom",
        "license": "BSL-1.1",
        "category": "community",
        "depends": ["contacts", "inventory", "suppliers"],
        "installable": True,
        "auto_install": False,
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
            # No page/nav of its own — surfaced from the inventory
            # item's own actions (a "Suppliers" button opening
            # SupplierItemsModal), same folding-in approach as 13a.
            "navigation": [],
        },
    }

    def get_models(self) -> list:
        return [SupplierItem]

    def get_router(self) -> APIRouter:
        return router

    def get_permissions(self) -> list[str]:
        return ["read", "write"]

    def get_event_handlers(self) -> dict:
        return {}
