"""Expenses module — fixed/recurring office cost tracking.

Standalone module: no dependency on any other module. Admin gets full
access; other roles are read-only by default (edit ``role_permissions``
below to change that).
"""

from fastapi import APIRouter

from app.core.plugins import BaseModule

from .models import Expense
from .router import router


class ExpensesModule(BaseModule):
    """Fixed office expense tracking (rent, utilities, salaries, ...)."""

    manifest = {
        "name": "expenses",
        "version": "0.1.0",
        "summary": "Fixed/recurring office expense tracking with monthly category totals.",
        "author": "Clinic Custom",
        "license": "BSL-1.1",
        "category": "community",
        "depends": [],
        "installable": True,
        "auto_install": True,
        "removable": True,
        "role_permissions": {
            "admin": ["*"],
            "dentist": ["read"],
            "hygienist": ["read"],
            "assistant": ["read"],
            "receptionist": ["read"],
        },
        "frontend": {
            "layer_path": "frontend",
            "navigation": [
                {
                    "label": "nav.expenses",
                    "icon": "i-lucide-wallet",
                    "to": "/expenses",
                    "permission": "expenses.read",
                    "order": 90,
                },
            ],
        },
    }

    def get_models(self) -> list:
        return [Expense]

    def get_router(self) -> APIRouter:
        return router

    def get_permissions(self) -> list[str]:
        return ["read", "write"]

    def get_tools(self) -> list:
        from . import tools

        return tools.get_tools()
