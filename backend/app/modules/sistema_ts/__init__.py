"""sistema_ts — Sistema Tessera Sanitaria expense submission for Italy.

Issue #134, ADR 0026. The B2C half of Italian compliance: every paid
invoice to a natural person is sent to the Sistema TS synchronous web
service (``inserimento``), credit notes as ``rimborso``, voids as
``cancellazione``, and a change of the patient's opposizione as
``variazione``. Runs beside ``sdi_it`` (ADR 0025), which handles the
B2B invoices; the two are exclusive by art. 10-bis DL 119/2018.

No billing hook (the registry holds one hook per country and the
trigger here is *payment*, not issue): a worker scans ``billing`` every
two minutes for new paid invoices of enabled clinics and drains the
queue. Own tables only; opposition and per-item ``tipoSpesa`` live in the
module (ADR 0026 §4). See ``CLAUDE.md`` and ``docs/modules/sistema_ts.md``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter

from app.core.plugins import BaseModule

from .models import (
    SistemaTsDocument,
    SistemaTsItemType,
    SistemaTsPatientOpposition,
    SistemaTsSettings,
)
from .router import router

if TYPE_CHECKING:
    from app.core.scheduling import ScheduledJob

TS_TABLES = {
    "sistema_ts_settings",
    "sistema_ts_documents",
    "sistema_ts_patient_opposition",
    "sistema_ts_item_types",
}


class SistemaTsModule(BaseModule):
    manifest = {
        "name": "sistema_ts",
        "version": "0.1.0",
        "summary": "Sistema Tessera Sanitaria — invio delle spese sanitarie dei pazienti (IT).",
        "author": "DentalPin Core Team",
        "license": "BSL-1.1",
        "category": "official",
        "depends": ["billing", "patients", "catalog", "payments"],
        "installable": True,
        "auto_install": False,
        "removable": True,
        "role_permissions": {
            "admin": ["*"],
            "dentist": ["documents.read", "opposition.read", "opposition.write"],
            "hygienist": ["opposition.read"],
            "assistant": ["opposition.read"],
            "receptionist": [
                "documents.read",
                "documents.manage",
                "opposition.read",
                "opposition.write",
            ],
        },
        "frontend": {"layer_path": "frontend", "navigation": []},
    }

    def get_models(self) -> list:
        return [SistemaTsSettings, SistemaTsDocument, SistemaTsPatientOpposition, SistemaTsItemType]

    def get_router(self) -> APIRouter:
        return router

    def get_permissions(self) -> list[str]:
        # Namespaced → sistema_ts.settings.read / .configure, documents.read / .manage,
        # opposition.read / .write
        return [
            "settings.read",
            "settings.configure",
            "documents.read",
            "documents.manage",
            "opposition.read",
            "opposition.write",
        ]

    def get_scheduled_jobs(self) -> list[ScheduledJob]:
        from .tasks import scheduled_jobs

        return scheduled_jobs()

    async def uninstall(self, ctx) -> None:
        from sqlalchemy import select

        # Accepted documents carry the protocollo — the clinic's proof of
        # submission for ten years (ADR 0026 §6). Keep them.
        result = await ctx.db.execute(
            select(SistemaTsDocument.id).where(SistemaTsDocument.protocollo.is_not(None)).limit(1)
        )
        if result.first() is not None:
            raise RuntimeError(
                "Cannot uninstall sistema_ts: documents already accepted by the Sistema TS. "
                "Export the records before uninstalling."
            )
