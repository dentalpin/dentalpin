"""Medications module — medication catalog for clinical reference.

Standalone module (``depends: []``). Exposes ``/api/v1/medications/*``.
get_tools() is mandatory per CLAUDE.md even when empty; no agent tools
needed for this phase.
"""

from fastapi import APIRouter

from app.core.plugins import BaseModule

from .models import Medication
from .router import router


class MedicationsModule(BaseModule):
    manifest = {
        "name": "medications",
        "version": "0.1.0",
        "summary": "Medication catalog for clinical reference and future prescriptions.",
        "author": "Clinic Custom",
        "license": "BSL-1.1",
        "category": "community",
        "depends": [],
        "installable": True,
        "auto_install": True,
        "removable": True,
        "role_permissions": {
            "admin": ["*"],
            "dentist": ["read", "write"],
            "hygienist": ["read"],
            "assistant": ["read"],
            "receptionist": ["read"],
        },
        "frontend": {
            "layer_path": "frontend",
        },
    }

    def get_models(self) -> list:
        return [Medication]

    def get_router(self) -> APIRouter:
        return router

    def get_permissions(self) -> list[str]:
        return ["read", "write"]

    def get_tools(self) -> list:
        return []
