from fastapi import APIRouter

from app.core.plugins import BaseModule


class TreatmentConsumablesModule(BaseModule):
    manifest = {
        "name": "treatment_consumables",
        "version": "0.1.0",
        "summary": "Links catalog treatments to the inventory items they consume",
        "author": "Clinic Custom",
        "license": "BSL-1.1",
        "category": "community",
        "depends": ["catalog", "inventory"],
        "installable": True,
        "auto_install": False,
        "removable": True,
        "role_permissions": {"admin": ["*"]},
        "frontend": {
            "layer_path": "frontend",
            "navigation": [
                {
                    "label": "nav.treatmentConsumables",
                    "to": "/treatment-consumables",
                    "icon": "i-lucide-link",
                    # Single-prefixed: loader prefixes get_permissions()'s
                    # bare "read" -> "treatment_consumables.read". Do not
                    # double-prefix here (see Phase 10 postmortem).
                    "permission": "treatment_consumables.read",
                    "order": 96,
                }
            ],
        },
    }

    def get_models(self) -> list:
        from .models import TreatmentConsumable

        return [TreatmentConsumable]

    def get_router(self) -> APIRouter:
        from .router import router

        return router

    def get_permissions(self) -> list[str]:
        # Bare names — the loader prefixes each with the module name,
        # producing treatment_consumables.read / treatment_consumables.write.
        return ["read", "write"]

    def get_event_handlers(self) -> dict:
        # No event integration in this phase (deduction logic is Phase 12).
        return {}
