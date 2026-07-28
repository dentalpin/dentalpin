"""Documents module — prescriptions, certificates, referral letters,
radiology requests, letterhead configuration, and PDF export.

Standalone module: no dependency on any other module (see phase handoff
§5 dependency strategy for how prescriptions/audit logging degrade
gracefully until Phases 9/10 land).
"""

from fastapi import APIRouter

from app.core.plugins import BaseModule

from .models import GeneratedDocument, Letterhead
from .router import router


class DocumentsModule(BaseModule):
    """Prescriptions, certificates, referral letters, radiology requests,
    letterhead configuration, and PDF export."""

    manifest = {
        "name": "documents",
        "version": "0.1.0",
        "summary": "Prescriptions, certificates, referral letters, radiology "
                    "requests, letterhead configuration, and PDF export.",
        "author": "Clinic Custom",
        "license": "BSL-1.1",
        "category": "community",
        "depends": [],
        "installable": True,
        "auto_install": True,
        "removable": True,
        # NOTE: bare action names — role -> module-local permissions granted.
        # Mirrors inventory's shape; adjust per-role grants to your actual
        # clinic workflow (e.g. whether receptionists should write documents).
        "role_permissions": {
            "admin": ["*"],
            "dentist": ["read", "write"],
            "hygienist": ["read"],
            "assistant": ["read", "write"],
            "receptionist": ["read"],
        },
        "frontend": {
            "layer_path": "frontend",
            "navigation": [
                {
                    "label": "nav.documents",
                    "icon": "i-lucide-file-text",
                    "to": "/documents",
                    "permission": "documents.read",
                    # Pick a value that doesn't collide with an existing
                    # nav entry — 93 is taken by inventory in the example.
                    "order": 95,
                },
            ],
        },
    }

    def get_models(self) -> list:
        return [Letterhead, GeneratedDocument]

    def get_router(self) -> APIRouter:
        return router

    def get_permissions(self) -> list[str]:
        return ["read", "write"]
