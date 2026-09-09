"""payroll - staff payroll with encrypted bank/tax data (admin-only).

v1 scope (issue #229, approved design): profiles with Fernet-encrypted
bank account + tax ID, monthly periods with a status lifecycle, raw
per-employee entries (gross/deductions/net stored as entered), and pure
aggregation reports. No tax computation, no country rules, no agent
tools — the agent layer never sees payroll.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.core.plugins import BaseModule

from .models import PayrollEntry, PayrollPeriod, PayrollProfile
from .router import router


class PayrollModule(BaseModule):
    """Staff payroll: encrypted profiles, periods, entries, reports."""

    manifest = {
        "name": "payroll",
        "version": "0.1.0",
        "summary": "Staff payroll with encrypted bank/tax data, periods, entries and reports.",
        "author": "lamanji",
        "license": "BSL-1.1",
        "category": "official",
        "depends": [],
        "installable": True,
        "auto_install": False,
        "removable": True,
        # Strictly admin: bank/tax data keeps the blast radius on the
        # wildcard-admin role (approved v1 scope, issue #229).
        "role_permissions": {
            "admin": ["*"],
        },
        # Payroll frontend (issue #391): admin-only pages. Navigation is
        # backend-driven via useModules; entries self-hide without the
        # payroll grants.
        "frontend": {
            "layer_path": "frontend",
            "navigation": [
                {
                    "label": "payroll.nav.profiles",
                    "to": "/payroll/profiles",
                    "icon": "i-lucide-users",
                    "permission": "payroll.read",
                    "order": 90,
                },
                {
                    "label": "payroll.nav.periods",
                    "to": "/payroll/periods",
                    "icon": "i-lucide-calendar-days",
                    "permission": "payroll.read",
                    "order": 91,
                },
                {
                    "label": "payroll.nav.reports",
                    "to": "/payroll/reports",
                    "icon": "i-lucide-chart-column",
                    "permission": "payroll.reports.read",
                    "order": 92,
                },
            ],
        },
    }

    def get_models(self) -> list:
        return [PayrollProfile, PayrollPeriod, PayrollEntry]

    def get_router(self) -> APIRouter:
        return router

    def get_permissions(self) -> list[str]:
        return ["read", "write", "reports.read"]
