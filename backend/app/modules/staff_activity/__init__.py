from fastapi import APIRouter

from app.core.plugins import BaseModule


class StaffActivityModule(BaseModule):
    manifest = {
        "name": "staff_activity",
        "version": "0.1.0",
        "summary": "Append-only staff activity journal across the platform",
        "author": "Clinic Custom",
        "license": "BSL-1.1",
        "category": "community",
        "depends": [],
        "installable": True,
        "auto_install": False,
        "removable": True,
        "role_permissions": {"admin": ["*"]},
        "frontend": {
            "layer_path": "frontend",
            "navigation": [
                {
                    "label": "nav.staffActivity",
                    "to": "/staff-activity",
                    "icon": "i-lucide-clipboard-list",
                    "permission": "staff_activity.view",
                    "order": 95,
                }
            ],
        },
    }

    def get_models(self) -> list:
        from .models import StaffActivityLog

        return [StaffActivityLog]

    def get_router(self) -> APIRouter:
        from .router import router

        return router

    def get_permissions(self) -> list[str]:
        return ["view"]

    def get_event_handlers(self) -> dict:
        from .handlers import make_activity_handlers

        return make_activity_handlers()
