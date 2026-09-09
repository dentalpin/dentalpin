"""sdi_it — FatturaPA / Sistema di Interscambio e-invoicing for Italy.

Issue #133, ADR 0025. Fourth application of the ``BillingComplianceHook``
seam (after ``verifactu`` ES, ``india_gst`` IN, ``nav_online`` HU), with
one rule the others do not have: **only B2B/B2G invoices go through the
SDI**. Invoices to natural persons for healthcare services may not be
electronic (art. 10-bis DL 119/2018); they stay analogue and are reported
to the Sistema Tessera Sanitaria by a separate module (ADR 0026).

Phase 1 (this module): FPR12 XML for TD01/TD04, manual transport
(download the file, upload it to the SDI, import the receipt), receipt
handling RC/NS/MC. PEC transport and the Nuxt layer follow in their own
PRs. See ``CLAUDE.md`` and ``docs/modules/sdi_it.md``.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.core.plugins import BaseModule

from .models import SdiItRecord, SdiItSettings
from .router import router

SDI_TABLES = {"sdi_it_settings", "sdi_it_records"}


class SdiItModule(BaseModule):
    manifest = {
        "name": "sdi_it",
        "version": "0.1.0",
        "summary": "FatturaPA / SDI — fatturazione elettronica B2B per l'Italia.",
        "author": "DentalPin Core Team",
        "license": "BSL-1.1",
        "category": "official",
        "depends": ["billing"],
        "installable": True,
        "auto_install": False,
        "removable": True,
        "role_permissions": {
            "admin": ["*"],
            "dentist": ["records.read"],
            "hygienist": [],
            "assistant": [],
            "receptionist": ["records.read", "records.manage"],
        },
    }

    def get_models(self) -> list:
        return [SdiItSettings, SdiItRecord]

    def get_router(self) -> APIRouter:
        return router

    def get_permissions(self) -> list[str]:
        # Namespaced → sdi_it.settings.read / .configure, records.read / .manage
        return ["settings.read", "settings.configure", "records.read", "records.manage"]

    def on_activate(self) -> None:
        # Re-attached on every boot the module is installed (ADR 0020).
        from app.modules.billing.hooks import BillingHookRegistry

        from .hook import SdiItHook

        BillingHookRegistry.register(SdiItHook())

    async def uninstall(self, ctx) -> None:
        from sqlalchemy import select

        from app.modules.billing.hooks import BillingHookRegistry

        # Once a file reached the SDI the local record (identificativo SdI,
        # receipts) is the clinic's proof of issuance — keep it.
        result = await ctx.db.execute(
            select(SdiItRecord.id)
            .where(SdiItRecord.state.in_(("exported", "delivered", "undeliverable")))
            .limit(1)
        )
        if result.first() is not None:
            raise RuntimeError(
                "Cannot uninstall sdi_it: invoices already transmitted to the SDI. "
                "Export the records before uninstalling."
            )
        BillingHookRegistry.unregister("IT")
