"""sms_gateway — SMS delivery for notifications, via a pluggable provider.

Depends on ``notifications`` (registers an ``SmsAdapter`` into its channel
registry — the only cross-module import, legal under ADR 0002/0003).

IMPORTANT — this module alone is not enough to actually send SMS. It also
needs three small upstream patches to the ``notifications`` module itself
(adding ``SMS`` to the ``Channel`` enum, an ``sms_enabled`` consent column,
and a channel-selection branch in the gateway). See the Phase 6 install
guide for exact patches — this is different from every custom module
built before this one, which were pure new-folder additions.

Manual install only (``auto_install=False``) since it does nothing useful
until a provider is configured.
"""

from fastapi import APIRouter

from app.core.plugins import BaseModule
from app.modules.notifications.channels import channel_registry

from .adapter import SmsAdapter
from .models import SmsGatewaySettings, SmsOutboxLog
from .router import router

# Register the adapter once, at import time. Idempotent in the registry
# (same pattern as whatsapp_kapso).
channel_registry.register(SmsAdapter())


class SmsGatewayModule(BaseModule):
    manifest = {
        "name": "sms_gateway",
        "version": "0.1.0",
        "summary": "SMS delivery for notifications via a pluggable provider (placeholder by default).",
        "author": "Clinic Custom",
        "license": "BSL-1.1",
        "category": "community",
        "depends": ["notifications"],
        "installable": True,
        "auto_install": False,
        "removable": True,
        "role_permissions": {
            "admin": ["*"],
        },
        "frontend": {
            "layer_path": "frontend",
            "navigation": [],
        },
    }

    def get_models(self) -> list:
        return [SmsGatewaySettings, SmsOutboxLog]

    def get_router(self) -> APIRouter:
        return router

    def get_permissions(self) -> list[str]:
        # Namespaced -> sms_gateway.settings.read / .write
        return ["settings.read", "settings.write"]

    async def uninstall(self, ctx) -> None:
        # Drop the adapter so an uninstalled module stops serving SMS;
        # the channel falls back silently (no adapter registered).
        channel_registry.unregister("sms_gateway")
