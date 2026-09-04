"""supplier_ratings - automatic delivery/quality metrics + manual 1-5 communication rating.

Last module of the supplier & procurement suite (#227). Computes per
supplier on-time delivery and quality rejection metrics on demand from
purchase order history, and stores a manual 1-5 communication score
(one per supplier, editable). Metrics are derived - no tables besides
the reviews one - so nothing needs event-driven recomputation.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.core.plugins import BaseModule

from .models import SupplierReview
from .router import router


class SupplierRatingsModule(BaseModule):
    """Supplier ratings: PO-derived delivery/quality metrics + manual score."""

    manifest = {
        "name": "supplier_ratings",
        "version": "0.1.0",
        "summary": "Automatic delivery/quality metrics from PO history plus a manual 1-5 communication rating per supplier.",
        "author": "lamanji",
        "license": "BSL-1.1",
        "category": "official",
        "depends": ["contacts", "purchase_orders"],
        "installable": True,
        "auto_install": False,
        "removable": True,
        # Same posture as the rest of the suite: front-desk and assistants
        # manage vendor ratings; clinicians get read-only visibility.
        "role_permissions": {
            "admin": ["*"],
            "dentist": ["read"],
            "hygienist": ["read"],
            "assistant": ["read", "write"],
            "receptionist": ["read", "write"],
        },
    }

    def get_models(self) -> list:
        return [SupplierReview]

    def get_router(self) -> APIRouter:
        return router

    def get_tools(self) -> list:
        from .tools import get_all_tools

        return get_all_tools()

    def get_permissions(self) -> list[str]:
        return ["read", "write"]
