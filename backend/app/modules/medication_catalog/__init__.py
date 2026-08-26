"""medication_catalog — clinic-wide medication list (Settings → Clinical).

Name, dose, unit, pharmaceutical form and prescribable/active status per
clinic. CRUD lives under Settings → Clinical (same area as the treatment
catalogue), not the main sidebar. Seeded with a 56-item dental
medication list via an idempotent seeder that runs on ``clinic.created``
(own session, catalog precedent) and on demand via ``POST /seed``.

Standalone module: `depends: []`. Data source for the document
generation module (prescriptions), which reads it cross-module under
ADR 0002.
"""

from fastapi import APIRouter

from app.core.plugins import BaseModule

from .models import MedicationCatalogItem
from .router import router


class MedicationCatalogModule(BaseModule):
    """Clinic-wide medication catalog (Settings → Clinical)."""

    manifest = {
        "name": "medication_catalog",
        "version": "0.1.0",
        "summary": "Clinic-wide medication list with dose/unit/form, seeded with a 56-item dental starter set.",
        "author": "DentalPin Core Team",
        "license": "BSL-1.1",
        "category": "community",
        "depends": [],
        "installable": True,
        # Optional module: ships inactive, the admin activates it from the
        # module admin UI (repo policy for new non-core modules).
        "auto_install": False,
        "removable": True,
        # Settings-managed clinical reference data: admins manage it;
        # dentists read it (prescriptions will consume this list).
        "role_permissions": {
            "admin": ["*"],
            "dentist": ["read"],
        },
        "frontend": {
            "layer_path": "frontend",
            # No standalone nav entry — the CRUD page lives under
            # Settings → Clinical (/settings/clinical/medications, via
            # the settings registry plugin), same area as the treatment
            # catalogue.
        },
    }

    def get_models(self) -> list:
        return [MedicationCatalogItem]

    def get_router(self) -> APIRouter:
        return router

    def get_permissions(self) -> list[str]:
        return ["read", "write"]

    def get_tools(self) -> list:
        from . import tools

        return tools.get_tools()

    def get_event_handlers(self) -> dict:
        from app.core.events.types import EventType

        from .events import on_clinic_created

        # Non-transactional by design: clinic.created is published
        # without a session; the seeder runs on its own connection
        # (catalog precedent, issue #183).
        return {EventType.CLINIC_CREATED: on_clinic_created}
