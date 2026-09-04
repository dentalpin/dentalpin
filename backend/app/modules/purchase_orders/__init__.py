"""purchase_orders - procurement purchase orders with receiving.

Full PO lifecycle (draft -> sent -> confirmed -> cancelled) plus batch
receiving with partial deliveries and quality checks: only "good" received
quantities update stock. Feeds supplier_ratings (#227-5) and
inventory_reorder (#227-4).
"""

from __future__ import annotations

from fastapi import APIRouter

from app.core.plugins import BaseModule

from .models import PurchaseOrder, PurchaseOrderLine, PurchaseReceipt, PurchaseReceiptLine
from .router import router


class PurchaseOrdersModule(BaseModule):
    """Purchase orders: the procurement execution layer for #227."""

    manifest = {
        "name": "purchase_orders",
        "version": "0.1.0",
        "summary": "Purchase orders with receiving, quality checks and PDF export.",
        "author": "lamanji",
        "license": "BSL-1.1",
        "category": "official",
        "depends": ["contacts", "inventory", "suppliers"],
        "installable": True,
        "auto_install": False,
        "removable": True,
        # Front-desk and assistants run procurement; clinicians get
        # read-only visibility into stock replenishment.
        "role_permissions": {
            "admin": ["*"],
            "dentist": ["read"],
            "hygienist": ["read"],
            "assistant": ["read", "write"],
            "receptionist": ["read", "write"],
        },
    }

    def get_models(self) -> list:
        return [PurchaseOrder, PurchaseOrderLine, PurchaseReceipt, PurchaseReceiptLine]

    def get_router(self) -> APIRouter:
        return router

    def get_tools(self) -> list:
        from .tools import get_all_tools

        return get_all_tools()

    def get_permissions(self) -> list[str]:
        return ["read", "write"]
