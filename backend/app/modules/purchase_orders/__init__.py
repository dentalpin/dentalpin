"""purchase_orders module — Phase 13c (lifecycle, PDF, email) + Phase
13d (receiving: partial deliveries, per-line quality check, stock
update via InventoryMovement, derived partially_received/fully_received
status).

Depends on `contacts` (validate supplier), `inventory` (validate line
items, and — new in 13d — record stock movements for received "good"
quantities), and `suppliers` (declared for the same procurement-chain
reasons as 13a/13b) — reads all three, writes only to `inventory`
(via its own public `InventoryService.record_movement`, never
touching inventory's tables directly).
"""

from fastapi import APIRouter

from app.core.plugins import BaseModule

from .models import PurchaseOrder, PurchaseOrderItem, PurchaseOrderReceipt, PurchaseOrderReceiptLine
from .router import router


class PurchaseOrdersModule(BaseModule):
    manifest = {
        "name": "purchase_orders",
        "version": "0.2.0",
        "summary": "Purchase order lifecycle, receiving, PDF export, and supplier email.",
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
            "navigation": [
                {
                    "label": "nav.purchaseOrders",
                    "icon": "i-lucide-clipboard-list",
                    "to": "/purchase-orders",
                    "permission": "purchase_orders.read",
                    "order": 99,
                },
            ],
        },
    }

    def get_models(self) -> list:
        return [PurchaseOrder, PurchaseOrderItem, PurchaseOrderReceipt, PurchaseOrderReceiptLine]

    def get_router(self) -> APIRouter:
        return router

    def get_permissions(self) -> list[str]:
        return ["read", "write"]

    def get_event_handlers(self) -> dict:
        return {}
