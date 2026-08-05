"""Lab orders module — track work sent to external labs, per patient.

Depends on ``patients`` (whose work this is) and ``contacts`` (Phase 2 —
which lab it went to). Cross-branch FKs to both are allowed under ADR 0002
because both are declared in ``manifest.depends`` below; the synchronous
read of ``contacts`` in ``service.py`` follows ADR 0003.
"""

from fastapi import APIRouter

from app.core.plugins import BaseModule

from .models import LabOrder
from .router import router


class LabOrdersModule(BaseModule):
    """Lab work order tracking, linked to a patient and an external lab contact."""

    manifest = {
        "name": "lab_orders",
        "version": "0.1.0",
        "summary": "Track lab work orders per patient — status from sent to received.",
        "author": "Clinic Custom",
        "license": "BSL-1.1",
        "category": "community",
        "depends": ["patients", "contacts"],
        "installable": True,
        "auto_install": True,
        "removable": True,
        "role_permissions": {
            "admin": ["*"],
            "dentist": ["read", "write"],
            "hygienist": ["read"],
            "assistant": ["read", "write"],
            "receptionist": ["read", "write"],
        },
        "frontend": {
            "layer_path": "frontend",
            "navigation": [
                {
                    "label": "nav.labOrdersForm",
                    "icon": "i-lucide-clipboard-plus",
                    "to": "/lab-orders/new",
                    "permission": "lab_orders.write",
                    "order": 92,
                },
                {
                    "label": "nav.labOrdersStatus",
                    "icon": "i-lucide-flask-conical",
                    "to": "/lab-orders",
                    "permission": "lab_orders.read",
                    "order": 92.5,
                },
            ],
        },
    }

    def get_models(self) -> list:
        return [LabOrder]

    def get_router(self) -> APIRouter:
        return router

    def get_permissions(self) -> list[str]:
        return ["read", "write"]

    def get_tools(self) -> list:
        from . import tools

        return tools.get_tools()
