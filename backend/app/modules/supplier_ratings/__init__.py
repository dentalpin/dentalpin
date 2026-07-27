"""supplier_ratings module — Phase 13e. Delivery-time and quality
metrics computed on the fly from purchase_orders/receiving data
(13c/13d); communication is the one dimension with no data trail, so
it's a manual periodic entry. Price is shown computed (average paid),
not subjectively rated.

Depends on `contacts` (validate supplier) and `purchase_orders` (the
actual metrics source) — reads both, writes only to its own table.
No new page/nav — folded into the existing /contacts page's supplier
section, same pattern as 13a/13b.
"""

from fastapi import APIRouter

from app.core.plugins import BaseModule

from .models import SupplierRating
from .router import router


class SupplierRatingsModule(BaseModule):
    manifest = {
        "name": "supplier_ratings",
        "version": "0.1.0",
        "summary": "Supplier performance dashboard (delivery, quality, price, communication).",
        "author": "Clinic Custom",
        "license": "BSL-1.1",
        "category": "community",
        "depends": ["contacts", "purchase_orders"],
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
            "navigation": [],
        },
    }

    def get_models(self) -> list:
        return [SupplierRating]

    def get_router(self) -> APIRouter:
        return router

    def get_permissions(self) -> list[str]:
        return ["read", "write"]

    def get_event_handlers(self) -> dict:
        return {}
