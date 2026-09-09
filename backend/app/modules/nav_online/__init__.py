"""nav_online — NAV Online Számla real-time invoice reporting for Hungary.

Issue #341. Third application of the ``BillingComplianceHook`` seam
(after ``verifactu`` ES and ``india_gst`` IN): when a HU clinic issues an
invoice, the hook snapshots it as NAV ``InvoiceData`` XML (Online Számla
3.0 schema) into a queue row; a scheduled worker exchanges a token,
submits ``manageInvoice`` operations and polls ``queryTransactionStatus``
until NAV reports DONE or ABORTED. Sandbox (``test``) / production
environment switch, technical-user credentials encrypted at rest.

Phase 1 = CREATE for invoices and STORNO for credit notes, one operation
per request, no MODIFY chains, no EKÁER, no online pénztárgép. See
``CLAUDE.md`` and ``docs/modules/nav_online.md``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter

from app.core.plugins import BaseModule

from .models import NavOnlineRecord, NavOnlineSettings
from .router import router

if TYPE_CHECKING:
    from app.core.scheduling import ScheduledJob

NAV_TABLES = {"nav_online_settings", "nav_online_records"}


class NavOnlineModule(BaseModule):
    manifest = {
        "name": "nav_online",
        "version": "0.1.0",
        "summary": "NAV Online Számla — valós idejű számlaadat-szolgáltatás (HU).",
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
            "receptionist": ["records.read"],
        },
        "frontend": {"layer_path": "frontend", "navigation": []},
    }

    def get_models(self) -> list:
        return [NavOnlineSettings, NavOnlineRecord]

    def get_router(self) -> APIRouter:
        return router

    def get_permissions(self) -> list[str]:
        # Namespaced → nav_online.settings.read / .configure, records.read, queue.manage
        return ["settings.read", "settings.configure", "records.read", "queue.manage"]

    def get_scheduled_jobs(self) -> list[ScheduledJob]:
        from .tasks import scheduled_jobs

        return scheduled_jobs()

    def on_activate(self) -> None:
        # Re-attached on every boot the module is installed (ADR 0020):
        # the hook registry is in-memory and billing looks hooks up by
        # the clinic's country at request time.
        from app.modules.billing.hooks import BillingHookRegistry

        from .hook import NavOnlineHook

        BillingHookRegistry.register(NavOnlineHook())

    async def uninstall(self, ctx) -> None:
        from sqlalchemy import select

        from app.modules.billing.hooks import BillingHookRegistry

        # Same posture as verifactu: once NAV has a transaction on file the
        # local log (transaction ids, statuses) is the clinic's audit trail.
        result = await ctx.db.execute(
            select(NavOnlineRecord.id).where(NavOnlineRecord.state.in_(("sent", "done"))).limit(1)
        )
        if result.first() is not None:
            raise RuntimeError(
                "Cannot uninstall nav_online: invoices already reported to NAV. "
                "Export the records before uninstalling."
            )
        BillingHookRegistry.unregister("HU")
