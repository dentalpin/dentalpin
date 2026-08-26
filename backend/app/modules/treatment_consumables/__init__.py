"""treatment_consumables — catalog treatments ↔ inventory items junction.

Pure mapping with a quantity per link (root canal → 2 anesthetic
vials). Reads both dependencies to validate links and resolve names;
writes only its own table. **No stock deduction** — that lands in the
inventory core upgrade (#226).

depends: ["catalog", "inventory"] — declared so the loader mounts this
module after both, and so CI enforces the cross-module FKs.
"""

from fastapi import APIRouter

from app.core.plugins import BaseModule

from .models import TreatmentConsumable
from .router import router


class TreatmentConsumablesModule(BaseModule):
    """Links catalog treatments to the inventory items they consume."""

    manifest = {
        "name": "treatment_consumables",
        "version": "0.1.0",
        "summary": "Maps catalog treatments to inventory items with quantity per link.",
        "author": "DentalPin Core Team",
        "license": "BSL-1.1",
        "category": "community",
        "depends": ["catalog", "inventory"],
        "installable": True,
        # Optional module: ships inactive, the admin activates it from the
        # module admin UI (repo policy for new non-core modules).
        "auto_install": False,
        "removable": True,
        # Mapping config consumed chairside by dentists/assistants; admins
        # manage it. Other roles get nothing out of the box.
        "role_permissions": {
            "admin": ["*"],
            "dentist": ["read"],
        },
        "frontend": {
            "layer_path": "frontend",
            "navigation": [
                {
                    "label": "nav.treatmentConsumables",
                    "icon": "i-lucide-link-2",
                    "to": "/treatment-consumables",
                    "permission": "treatment_consumables.read",
                    "order": 92,
                },
            ],
        },
    }

    def get_models(self) -> list:
        return [TreatmentConsumable]

    def get_router(self) -> APIRouter:
        return router

    def get_permissions(self) -> list[str]:
        return ["read", "write"]

    def get_tools(self) -> list:
        from . import tools

        return tools.get_tools()

    def get_event_handlers(self) -> dict:
        # Pure mapping: emits nothing, consumes nothing. Stock deduction
        # (a future subscriber of treatment events) belongs to the
        # inventory core upgrade (#226), not here.
        return {}
