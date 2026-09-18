"""treasury — cash/bank accounts, transfers, and manual corrections."""

from fastapi import APIRouter

from app.core.plugins import BaseModule

from .models import TreasuryAccount, TreasuryEntry
from .router import router


class TreasuryModule(BaseModule):
    """Where the money sits (expenses tracks where it went)."""

    manifest = {
        "name": "treasury",
        "version": "0.1.0",
        "summary": "Cash/bank accounts, transfers, and manual corrections.",
        "author": "DentalPin Core Team",
        "license": "BSL-1.1",
        "category": "community",
        "depends": [],
        "installable": True,
        # Optional module: ships inactive, the admin activates it from the
        # module admin UI (repo policy for new non-core modules).
        "auto_install": False,
        "removable": True,
        # Money balances keep the payroll-grade blast radius: admin only
        # until a clinic widens grants via the roles UI (#46).
        "role_permissions": {
            "admin": ["*"],
        },
        "frontend": {
            "layer_path": "frontend",
            "navigation": [
                {
                    "label": "treasury.nav.title",
                    "to": "/treasury",
                    "icon": "i-lucide-wallet",
                    "permission": "treasury.read",
                    "section": "financials",
                    "order": 94,
                }
            ],
        },
    }

    def get_models(self) -> list:
        return [TreasuryAccount, TreasuryEntry]

    def get_router(self) -> APIRouter:
        return router

    def get_permissions(self) -> list[str]:
        # Registry namespaces with the module name -> final perms are
        # ``treasury.read`` / ``treasury.write``.
        return ["read", "write"]
