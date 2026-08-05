"""medical_reference — clinic-managed lookup lists for allergies,
medications, systemic diseases, and surgeries, plus the APCI flag on
diseases and active per-patient interaction/contraindication flagging.

``depends: ["patients_clinical"]`` — the one deliberate exception to this
module otherwise not reading patient data: get_patient_flags() reads a
patient's recorded Medication/SystemicDisease rows (by reference_id only)
to cross-check them against known interaction/contraindication pairs.
patients_clinical itself still links back here only loosely (a plain
nullable UUID, no DB-level FK), so it keeps working standalone if this
module is ever removed — the dependency only goes one direction.
"""

from fastapi import APIRouter

from app.core.plugins import BaseModule

from .models import (
    ReferenceAllergy,
    ReferenceContraindication,
    ReferenceDisease,
    ReferenceInteraction,
    ReferenceMedication,
    ReferenceSurgery,
)
from .router import router


class MedicalReferenceModule(BaseModule):
    """Managed lookup lists backing the searchable medical-history inputs,
    plus active interaction/contraindication flagging."""

    manifest = {
        "name": "medical_reference",
        "version": "0.3.0",
        "summary": "Managed allergy/medication/disease/surgery lists, APCI flag, and interaction/contraindication warnings.",
        "author": "Clinic Custom",
        "license": "BSL-1.1",
        "category": "community",
        "depends": ["patients_clinical"],
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
        return [
            ReferenceAllergy,
            ReferenceMedication,
            ReferenceDisease,
            ReferenceSurgery,
            ReferenceInteraction,
            ReferenceContraindication,
        ]

    def get_router(self) -> APIRouter:
        return router

    def get_permissions(self) -> list[str]:
        return ["read", "write"]
