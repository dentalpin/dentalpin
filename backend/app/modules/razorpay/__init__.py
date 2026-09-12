"""razorpay — first production payment gateway provider module.

Community-style provider module: registers a ``RazorpayAdapter`` into
``payment_gateways``'s registry from ``on_activate`` — i.e. on every
boot the module is installed, and never while it is not (issue #91,
ADR 0020). That is the only cross-module dependency, declared in
``manifest.depends``; ``payment_gateways`` does not depend on this
module. All Razorpay SDK/API usage, webhook verification,
credentials, and provider ids live here — never in ``payment_gateways``
or core ``payments``.

Issue #263 (PR 1 of #365). See ADR 0016 (channel adapters — the
pattern this module's registration mirrors) and the payment-gateways
architecture ADR.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter

from app.core.plugins import BaseModule
from app.modules.payment_gateways.adapters import gateway_registry

from .adapter import RazorpayAdapter
from .models import RazorpaySettings
from .router import router

if TYPE_CHECKING:
    from app.core.plugins.base import ModuleContext

# Table names exercised by the round-trip uninstall test.
RAZORPAY_TABLES = {"razorpay_settings"}


class RazorpayModule(BaseModule):
    manifest = {
        "name": "razorpay",
        "version": "0.1.0",
        "summary": "Razorpay payment gateway — UPI, QR, cards, and payment links for India clinics.",
        "author": "DentalPin Core Team",
        "license": "BSL-1.1",
        "category": "official",
        "depends": ["payment_gateways"],
        "installable": True,
        "auto_install": False,
        "removable": True,
        "role_permissions": {"admin": ["*"]},
        "frontend": {"layer_path": "frontend", "navigation": []},
    }

    def get_models(self) -> list:
        return [RazorpaySettings]

    def get_router(self) -> APIRouter:
        return router

    def get_permissions(self) -> list[str]:
        # Namespaced -> razorpay.settings.read / razorpay.settings.write
        return ["settings.read", "settings.write"]

    def on_activate(self) -> None:
        # Idempotent in the registry. Not registered => payment_gateways
        # simply has no "razorpay" provider available, and every
        # payment_gateways endpoint that looks it up returns a clear
        # "unknown or inactive provider" error rather than a crash.
        gateway_registry.register(RazorpayAdapter())

    async def uninstall(self, ctx: ModuleContext) -> None:
        gateway_registry.unregister("razorpay")
