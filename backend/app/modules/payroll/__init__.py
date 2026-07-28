"""Payroll module — staff payroll profiles, periods, entries, reports.

Standalone (depends: []). No dependency on staff_activity or any other
custom module, per the phase spec. Publishes payroll.period_processed
and payroll.payment_made (needs EventType additions — see install guide).
"""

from fastapi import APIRouter

from app.core.plugins import BaseModule

from .models import PayrollEntry, PayrollPeriod, StaffPayrollProfile
from .router import router


class PayrollModule(BaseModule):
    manifest = {
        "name": "payroll",
        "version": "0.1.0",
        "summary": "Staff payroll: profiles, monthly runs, pay slips, reports.",
        "author": "Clinic Custom",
        "license": "BSL-1.1",
        "category": "community",
        "depends": [],
        "installable": True,
        "auto_install": True,
        "removable": True,
        "role_permissions": {
            "admin": ["*"],
            "dentist": [],
            "hygienist": [],
            "assistant": [],
            "receptionist": [],
        },
        "frontend": {
            "layer_path": "frontend",
            "navigation": [
                {
                    "label": "nav.payroll",
                    "icon": "i-lucide-banknote",
                    "to": "/payroll",
                    "permission": "payroll.read",
                    "order": 100,
                },
            ],
        },
    }

    def get_models(self) -> list:
        return [StaffPayrollProfile, PayrollPeriod, PayrollEntry]

    def get_router(self) -> APIRouter:
        return router

    def get_permissions(self) -> list[str]:
        return ["read", "write"]

    def get_tools(self) -> list:
        return []
