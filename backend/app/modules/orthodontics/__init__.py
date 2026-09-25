"""Orthodontics module — case tracking + monthly controls (issue #270, slice-a).

Slice-a ships clinical tracking: cases, per-visit controls, photo
evolution via media attachments, chip-catalog settings seeds. No money
code: installments, recall upsert, plan/appointment links, copilot
tools, and the settings UI land in slice-b / follow-ups.
"""

from fastapi import APIRouter

from app.core.plugins import BaseModule

from .models import OrthoCase, OrthoControl, OrthoSettings
from .router import router


class OrthodonticsModule(BaseModule):
    manifest = {
        "name": "orthodontics",
        "version": "0.1.0",
        "summary": "Orthodontic case tracking — monthly controls, wires, photo evolution.",
        "author": "DentalPin Core Team",
        "license": "BSL-1.1",
        "category": "official",
        "depends": ["patients", "media"],
        "installable": True,
        "auto_install": False,
        "removable": True,
        "role_permissions": {
            "admin": ["*"],
            "dentist": ["cases.read", "cases.write", "controls.write", "settings.manage"],
            "hygienist": ["cases.read", "controls.write"],
            "assistant": ["cases.read", "cases.write"],
            "receptionist": ["cases.read"],
        },
        "frontend": {
            "layer_path": "frontend",
            "navigation": [
                {
                    "label": "Ortodoncia",
                    "labelKey": "orthodontics.nav.title",
                    "to": "/orthodontics",
                    "icon": "i-lucide-smile",
                    "order": 96,
                    "permission": "orthodontics.cases.read",
                }
            ],
        },
    }

    def get_models(self) -> list:
        return [OrthoCase, OrthoControl, OrthoSettings]

    def get_router(self) -> APIRouter:
        return router

    def get_permissions(self) -> list[str]:
        return ["cases.read", "cases.write", "controls.write", "settings.manage"]

    def on_activate(self) -> None:
        from .owner_resolvers import register as register_attachment_owners

        register_attachment_owners()
