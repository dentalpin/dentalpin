"""sms_gateway - SMS delivery for notifications via pluggable providers.

Community, removable. Registers an ``SmsGatewayAdapter`` into the
notifications channel registry from ``on_activate`` — same pattern as
``whatsapp_kapso`` (issue #91): the only cross-module dependency,
declared in ``manifest.depends``; ``notifications`` never imports this
module.

Issue #231 (PR2). See ADR 0016 (channel adapters).
"""

from __future__ import annotations

from fastapi import APIRouter

from app.core.plugins import BaseModule
from app.modules.notifications.channels import channel_registry

from .adapter import SmsGatewayAdapter
from .models import SmsGatewaySettings
from .router import router

# Table names exercised by the round-trip uninstall test.
SMS_TABLES = {"sms_gateway_settings"}


class SmsGatewayModule(BaseModule):
    manifest = {
        "name": "sms_gateway",
        "version": "0.1.0",
        "summary": "SMS delivery for notifications via pluggable providers.",
        "author": "lamanji",
        "license": "BSL-1.1",
        "category": "community",
        "depends": ["notifications"],
        "installable": True,
        "auto_install": False,
        "removable": True,
        "role_permissions": {"admin": ["*"]},
        # Settings-only frontend (issue #392 review): the provider page
        # registers under Settings → Integrations; no nav entries.
        "frontend": {"layer_path": "frontend", "navigation": []},
    }

    def get_models(self) -> list:
        return [SmsGatewaySettings]

    def get_router(self) -> APIRouter:
        return router

    def get_permissions(self) -> list[str]:
        # Namespaced → sms_gateway.settings.read / .write
        return ["settings.read", "settings.write"]

    def on_activate(self) -> None:
        # Idempotent in the registry. Not registered → the gateway falls
        # back to the next configured channel.
        channel_registry.register(SmsGatewayAdapter())

    async def uninstall(self, ctx) -> None:
        channel_registry.unregister("sms_gateway")
