"""Documents module — branded PDF generation for dental prescriptions,
medical certificates, referral letters and radiology requests."""

from fastapi import APIRouter

from app.core.plugins import BaseModule, ModuleContext
from . import lifecycle
from .models import GeneratedDocument
from .router import router
from .tools import get_tools as _get_tools


class DocumentsModule(BaseModule):
    manifest = {
        "name": "documents",
        "version": "0.1.0",
        "summary": (
            "Generates prescriptions, medical certificates, referral "
            "letters and radiology requests as branded PDFs with "
            "configurable clinic letterhead."
        ),
        "author": "DentalPin Contributors",
        "license": "BSL-1.1",
        "category": "official",
        "depends": ["patients", "medication_catalog"],
        "installable": True,
        "auto_install": False,
        "removable": True,
        "role_permissions": {
            "admin": ["*"],
            "dentist": ["documents.read", "documents.write"],
            "assistant": ["documents.read"],
        },
        "frontend": {
            "layer_path": "frontend",
            "navigation": [
                {
                    "label": "nav.documents",
                    "to": "/documents",
                    "icon": "i-lucide-file-text",
                    "permission": "documents.read",
                    "order": 75,
                }
            ],
        },
    }

    def get_models(self) -> list:
        return [GeneratedDocument]

    def get_router(self) -> APIRouter:
        return router

    def get_permissions(self) -> list[str]:
        return ["documents.read", "documents.write"]

    def get_tools(self) -> list:
        return _get_tools()

    async def install(self, ctx: ModuleContext) -> None:
        await lifecycle.install(ctx)

    async def uninstall(self, ctx: ModuleContext) -> None:
        await lifecycle.uninstall(ctx)

    async def post_upgrade(self, ctx: ModuleContext, from_version: str) -> None:
        await lifecycle.post_upgrade(ctx, from_version)
