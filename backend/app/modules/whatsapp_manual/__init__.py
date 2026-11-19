"""Community module for staff-operated WhatsApp delivery."""

from fastapi import APIRouter
from sqlalchemy import delete, update

from app.core.plugins import BaseModule
from app.core.plugins.context import ModuleContext
from app.core.scheduling import ScheduledJob
from app.modules.notifications.channels import channel_registry
from app.modules.notifications.models import ClinicChannelSettings, CommunicationMessage

from .adapter import ADAPTER_NAME, ManualWhatsAppAdapter
from .models import ManualDeliveryDeclaration
from .router import router
from .service import expire_whatsapp_drafts


class WhatsappManualModule(BaseModule):
    """Register the manual transport, tray and expiry job."""

    manifest = {
        "name": ADAPTER_NAME,
        "version": "0.1.0",
        "summary": "Staff-operated WhatsApp delivery from a shared pending tray.",
        "author": "Clínica Dental Araque",
        "license": "BSL-1.1",
        "category": "community",
        "depends": ["notifications", "patients", "agenda"],
        "installable": True,
        "auto_install": False,
        "removable": True,
        "role_permissions": {
            "admin": ["*"],
            "dentist": ["read", "write"],
            "hygienist": ["read", "write"],
            "assistant": ["read", "write"],
            "receptionist": ["read", "write"],
        },
        "frontend": {
            "layer_path": "frontend",
            "navigation": [
                {
                    "label": "whatsapp_manual.title",
                    "icon": "i-lucide-message-circle",
                    "to": "/whatsapp-manual",
                    "permission": "whatsapp_manual.read",
                    "section": "clinical",
                    "order": 26,
                },
            ],
        },
    }

    def get_models(self) -> list:
        return [ManualDeliveryDeclaration]

    def get_router(self) -> APIRouter:
        return router

    def get_permissions(self) -> list[str]:
        return ["read", "write", "settings.write"]

    def on_activate(self) -> None:
        channel_registry.register(ManualWhatsAppAdapter())

    async def uninstall(self, ctx: ModuleContext) -> None:
        # The module lifecycle is instance-wide. Cancel only drafts owned
        # by this adapter, including clinics that already changed selection.
        await ctx.db.execute(
            update(CommunicationMessage)
            .where(
                CommunicationMessage.direction == "outbound",
                CommunicationMessage.channel == "whatsapp",
                CommunicationMessage.provider == ADAPTER_NAME,
                CommunicationMessage.status == "awaiting_manual",
            )
            .values(status="skipped", error_message="adapter_uninstalled", next_attempt_at=None)
        )
        await ctx.db.execute(
            delete(ClinicChannelSettings).where(
                ClinicChannelSettings.channel == "whatsapp",
                ClinicChannelSettings.adapter_name == ADAPTER_NAME,
            )
        )
        channel_registry.unregister(ADAPTER_NAME)

    def get_scheduled_jobs(self) -> list[ScheduledJob]:
        return [
            ScheduledJob(
                id="expire_manual_whatsapp",
                func=expire_whatsapp_drafts,
                trigger="interval",
                trigger_args={"minutes": 5},
                name="Expire manual WhatsApp appointment drafts",
            )
        ]
