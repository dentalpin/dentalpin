"""patient_admin — patient-to-patient relationships (Lien de Parentée).

Originally also held insurance exemption status (APCI/ALD); removed in
Phase 8.1 — APCI is now a computed flag off systemic-disease reference
data (see models.py docstring), not a manually-entered field, so it
doesn't belong in this module. Depends on ``patients`` only (cross-module
read of ``Patient.full_name``, allowed under ADR 0002).
"""

from fastapi import APIRouter

from app.core.plugins import BaseModule

from .models import PatientRelationship
from .router import router


class PatientAdminModule(BaseModule):
    """Patient relationships, surfaced on the patient page."""

    manifest = {
        "name": "patient_admin",
        "version": "0.2.0",
        "summary": "Patient family relationships (Lien de Parentée).",
        "author": "Clinic Custom",
        "license": "BSL-1.1",
        "category": "community",
        "depends": ["patients"],
        "installable": True,
        "auto_install": True,
        "removable": True,
        "role_permissions": {
            "admin": ["*"],
            "dentist": ["relationships.read", "relationships.write"],
            "hygienist": ["relationships.read"],
            "assistant": ["relationships.read", "relationships.write"],
            "receptionist": ["relationships.read", "relationships.write"],
        },
        "frontend": {
            "layer_path": "frontend",
            # No standalone nav entry — surfaces inline on the patient page
            # via the `patient.summary.cards` slot (slots.client.ts), same
            # extension point patients_clinical already uses.
        },
    }

    def get_models(self) -> list:
        return [PatientRelationship]

    def get_router(self) -> APIRouter:
        return router

    def get_permissions(self) -> list[str]:
        return ["relationships.read", "relationships.write"]
