"""Documents module — branded PDF generation for dental prescriptions,
medical certificates, referral letters and radiology requests."""

from fastapi import APIRouter

from app.core.erasure.types import ErasureContributor
from app.core.plugins import BaseModule, ModuleContext

from . import lifecycle
from .models import ConsentEvidence, ConsentSigningLink, ConsentTemplate, GeneratedDocument
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
        # ``patients`` only — patient demographics feed the document
        # letterhead body. The prescription form holds free-text
        # medication lines; there is no catalog coupling.
        "depends": ["patients"],
        "installable": True,
        "auto_install": False,
        "removable": True,
        "role_permissions": {
            "admin": ["*"],
            "dentist": ["read", "write"],
            "assistant": ["read"],
        },
        "frontend": {
            "layer_path": "frontend",
            "navigation": [
                {
                    "label": "nav.documents",
                    "section": "clinical",
                    "to": "/documents",
                    "icon": "i-lucide-file-text",
                    "permission": "documents.read",
                    "order": 75,
                }
            ],
        },
    }

    def get_models(self) -> list:
        return [GeneratedDocument, ConsentTemplate, ConsentSigningLink, ConsentEvidence]

    def get_router(self) -> APIRouter:
        from .consent import router as consent_router

        combined = APIRouter()
        combined.include_router(consent_router)
        # The existing router contains an empty root path, which cannot be
        # nested with include_router without a prefix. Preserve those routes.
        combined.routes.extend(router.routes)
        return combined

    def get_permissions(self) -> list[str]:
        return ["read", "write"]

    def get_tools(self) -> list:
        return _get_tools()

    async def install(self, ctx: ModuleContext) -> None:
        await lifecycle.install(ctx)

    async def uninstall(self, ctx: ModuleContext) -> None:
        await lifecycle.uninstall(ctx)

    async def post_upgrade(self, ctx: ModuleContext, from_version: str) -> None:
        await lifecycle.post_upgrade(ctx, from_version)

    def get_erasure_contributors(self) -> list[ErasureContributor]:
        from .erasure import DocumentsErasureContributor

        return [DocumentsErasureContributor()]
