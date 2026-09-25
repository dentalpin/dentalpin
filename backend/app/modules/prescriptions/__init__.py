"""prescriptions — clinical prescriptions with per-country compliance hooks."""

from fastapi import APIRouter

from app.core.plugins import BaseModule

from .hooks import PrescriptionHookRegistry as PrescriptionHookRegistry
from .models import PrescriberProfile, Prescription, PrescriptionItem, PrescriptionTemplate
from .router import router
from .tools import get_tools


class PrescriptionsModule(BaseModule):
    """Clinical pad: drafts, issue/cancel lifecycle, templates, PDF."""

    manifest = {
        "name": "prescriptions",
        "version": "0.1.0",
        "summary": "Clinical prescriptions with per-country compliance hooks.",
        "author": "DentalPin Core Team",
        "license": "BSL-1.1",
        "category": "official",
        "depends": ["patients", "patients_clinical", "medical_reference"],
        "installable": True,
        # Optional module: ships inactive, the admin activates it from the
        # module admin UI (repo policy for new non-core modules).
        "auto_install": False,
        "removable": True,
        "role_permissions": {
            "admin": ["*"],
            "dentist": ["*"],
            "hygienist": ["read"],
            "assistant": ["read"],
            "receptionist": ["read"],
        },
        "frontend": {
            # No navigation entry: the page deep-links from the patient
            # summary card + action (a bare /prescriptions with no patient
            # picker is a dead end).
            "layer_path": "frontend",
        },
    }

    def get_models(self) -> list:
        return [Prescription, PrescriptionItem, PrescriptionTemplate, PrescriberProfile]

    def get_router(self) -> APIRouter:
        return router

    def get_permissions(self) -> list[str]:
        # Registry namespaces with the module name -> final perms are
        # ``prescriptions.read`` / ``.write`` / ``.issue``.
        return ["read", "write", "issue"]

    def get_tools(self) -> list:
        return get_tools()

    async def uninstall(self, ctx) -> None:
        from sqlalchemy import select

        from .models import Prescription

        result = await ctx.db.execute(
            select(Prescription.id).where(Prescription.issued_at.is_not(None)).limit(1)
        )
        if result.first() is not None:
            raise RuntimeError(
                "Cannot uninstall prescriptions: issued prescriptions exist. "
                "Clinical records must be retained — export them first."
            )
        # Nothing to detach: no external registrations beyond the loader.
