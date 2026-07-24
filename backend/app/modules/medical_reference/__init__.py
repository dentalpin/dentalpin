"""medical_reference — clinic-managed lookup lists for allergies,
medications, and systemic diseases, plus the APCI flag on diseases.

No ``depends`` — this is pure reference data, doesn't read or write
anything on ``patients`` or ``patients_clinical``. Those modules read
*from* this one only loosely (a plain nullable UUID stored as
``reference_id``, no DB-level FK) precisely so patients_clinical keeps
working standalone if this module is ever removed.
"""

from fastapi import APIRouter

from app.core.plugins import BaseModule

from .models import ReferenceAllergy, ReferenceDisease, ReferenceMedication
from .router import router


class MedicalReferenceModule(BaseModule):
    """Managed lookup lists backing the searchable medical-history inputs."""

    manifest = {
        "name": "medical_reference",
        "version": "0.1.0",
        "summary": "Managed allergy/medication/disease lists with searchable lookup + APCI flag.",
        "author": "Clinic Custom",
        "license": "BSL-1.1",
        "category": "community",
        "depends": [],
        "installable": True,
        "auto_install": True,
        "removable": True,
        "role_permissions": {
            "admin": ["*"],
            "dentist": ["read"],
            "hygienist": ["read"],
            "assistant": ["read"],
            "receptionist": ["read"],
        },
        "frontend": {
            "layer_path": "frontend",
        },
    }

    def get_models(self) -> list:
        return [ReferenceAllergy, ReferenceMedication, ReferenceDisease]

    def get_router(self) -> APIRouter:
        return router

    def get_permissions(self) -> list[str]:
        return ["read", "write"]
