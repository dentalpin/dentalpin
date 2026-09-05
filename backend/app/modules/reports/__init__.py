"""Reports module - centralized reporting across all domains."""

from fastapi import APIRouter

from app.core.plugins import BaseModule

from .router import router


class ReportsModule(BaseModule):
    """Reports module providing unified reporting across budgets, scheduling, and billing.

    Features:
    - Billing reports (revenue, payments, VAT, overdue)
    - Budget reports (coming soon)
    - Scheduling reports (coming soon)
    - Export functionality (CSV)
    """

    manifest = {
        "name": "reports",
        "version": "0.2.0",
        "summary": "Cross-module reporting: billing, budgets, scheduling.",
        "author": "DentalPin Core Team",
        "license": "BSL-1.1",
        "category": "official",
        "depends": ["patients", "agenda", "catalog", "budget", "billing", "payments"],
        "installable": True,
        "auto_install": True,
        "removable": False,
        "role_permissions": {
            "admin": ["*"],
            "dentist": [
                "billing.read",
                "scheduling.read",
                "financial.read",
                "patient_stats.read",
                "operational.read",
            ],
            "hygienist": ["scheduling.read", "operational.read"],
            "assistant": ["scheduling.read"],
            "receptionist": [
                "billing.read",
                "scheduling.read",
                "financial.read",
                "patient_stats.read",
            ],
        },
        "frontend": {
            "layer_path": "frontend",
            "navigation": [
                {
                    "label": "nav.reports",
                    "icon": "i-lucide-bar-chart-3",
                    "to": "/reports",
                    "permission": "reports.billing.read",
                    "order": 60,
                },
            ],
        },
    }

    def get_models(self) -> list:
        # Reports module has no models - it queries other modules' data
        return []

    def get_router(self) -> APIRouter:
        return router

    def get_permissions(self) -> list[str]:
        return [
            "billing.read",  # View billing reports
            "budgets.read",  # View budget reports
            "scheduling.read",  # View scheduling reports
            "financial.read",  # Outstanding aging + issued trend (invoice axis)
            "patient_stats.read",  # Patient demographics family (next)
            "operational.read",  # Operational KPI family (next)
        ]

    def get_tools(self) -> list:
        from . import tools

        return tools.get_tools()
