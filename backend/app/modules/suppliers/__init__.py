"""Suppliers module — procurement-specific extension of `contacts`
(Phase 13 §5: reuse Contact/contact_type=="supplier" instead of a
separate Supplier model).

Depends on `contacts` to read the underlying Contact row and validate
`contact_type == "supplier"`. Never writes to `contacts` — only to its
own `supplier_profiles` table.
"""

from fastapi import APIRouter

from app.core.plugins import BaseModule

from .models import SupplierProfile
from .router import router


class SuppliersModule(BaseModule):
    manifest = {
        "name": "suppliers",
        "version": "0.1.0",
        "summary": "Procurement fields (website, payment terms, lead time) for supplier contacts.",
        "author": "Clinic Custom",
        "license": "BSL-1.1",
        "category": "community",
        "depends": ["contacts"],
        "installable": True,
        "auto_install": False,
        "removable": True,
        "role_permissions": {"admin": ["*"]},
        "frontend": {
            "layer_path": "frontend",
            # No page/nav of its own — the supplier fields are folded
            # into the existing /contacts page (Phase 13 §5). This
            # module only ships a composable that page imports.
            "navigation": [],
        },
    }

    def get_models(self) -> list:
        return [SupplierProfile]

    def get_router(self) -> APIRouter:
        return router

    def get_permissions(self) -> list[str]:
        # No new permission strings — router reuses contacts.read/write
        # directly (see router.py docstring).
        return []

    def get_event_handlers(self) -> dict:
        return {}
