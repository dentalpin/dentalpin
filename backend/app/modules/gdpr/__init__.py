"""GDPR compliance module — subjects' data rights under EU 2016/679."""

from __future__ import annotations

from fastapi import APIRouter

from app.core.plugins import BaseModule

from .models import (
    DataBreach,
    ErasureAuditLog,
    GdprRequest,
    PatientConsent,
    RetentionPolicy,
)
from .router import router


class GdprModule(BaseModule):
    """GDPR compliance: DSRs, consents, retention, erasure and breaches.

    Partial-erasure never hard-deletes a patient row (identity fields are
    blanked once retention allows); consents/requests are append/audit data.
    """

    manifest = {
        "name": "gdpr",
        "version": "0.1.0",
        "summary": "Data-subject rights, consents, retention and breach reporting (GDPR).",
        "author": "DentalPin Core Team",
        "license": "BSL-1.1",
        "category": "official",
        "depends": ["patients"],
        "installable": True,
        "auto_install": False,
        "removable": True,
        "role_permissions": {
            "admin": ["*"],
            "dentist": ["requests.read", "consents.read", "audit.read", "retention.read"],
            "hygienist": ["requests.read"],
            "assistant": ["requests.read", "consents.read"],
            "receptionist": [
                "requests.read",
                "requests.write",
                "consents.read",
                "consents.write",
                "breaches.read",
            ],
        },
    }

    def get_models(self) -> list:
        return [
            GdprRequest,
            PatientConsent,
            RetentionPolicy,
            ErasureAuditLog,
            DataBreach,
        ]

    def get_router(self) -> APIRouter:
        return router

    def get_tools(self) -> list:
        from .tools import get_all_tools

        return get_all_tools()

    def get_permissions(self) -> list[str]:
        return [
            "requests.read",
            "requests.write",
            "consents.read",
            "consents.write",
            "retention.read",
            "retention.write",
            "audit.read",
            "breaches.read",
            "breaches.write",
        ]
