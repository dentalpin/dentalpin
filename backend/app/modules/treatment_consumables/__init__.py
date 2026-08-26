"""treatment_consumables — catalog treatments ↔ inventory items junction.

Pure mapping with a quantity per link (root canal → 2 anesthetic
vials). Reads both dependencies to validate links and resolve names;
writes only its own table.  Handles ``odontogram.treatment.performed``
via subscription inversion (#226): reads links via ORM model, calls
``InventoryService.deduct_for_treatment`` as a clean public primitive.

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
        from app.core.events.types import EventType

        from .events import on_treatment_performed

        # Subscription inversion (#226): this module owns the links table
        # and already depends on inventory, so the subscription direction
        # is legal (no cycle).  Reads links via ORM model, calls
        # InventoryService.deduct_for_treatment as a clean public
        # primitive — no raw SQL, no inspector guard, no fail-soft branch.
        return {EventType.ODONTOGRAM_TREATMENT_PERFORMED: on_treatment_performed}
