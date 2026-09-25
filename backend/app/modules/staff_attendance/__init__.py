"""staff_attendance — clock in/out events for clinic staff."""

from fastapi import APIRouter

from app.core.plugins import BaseModule

from .models import AttendanceEvent
from .router import router


class StaffAttendanceModule(BaseModule):
    """Staff attendance: punches, current state, daily report."""

    manifest = {
        "name": "staff_attendance",
        "version": "0.1.0",
        "summary": "Clock in/out events, current state, and daily pairing report.",
        "author": "DentalPin Core Team",
        "license": "BSL-1.1",
        "category": "community",
        "depends": [],
        "installable": True,
        # Optional module: ships inactive, the admin activates it from the
        # module admin UI (repo policy for new non-core modules).
        "auto_install": False,
        "removable": True,
        "role_permissions": {
            "admin": ["*"],
            "dentist": ["read", "write"],
            "hygienist": ["read"],
            "assistant": ["read", "write"],
            "receptionist": ["read", "write"],
        },
        "frontend": {
            "layer_path": "frontend",
            "navigation": [
                {
                    "label": "staffAttendance.nav.title",
                    "to": "/attendance",
                    "icon": "i-lucide-clock",
                    "permission": "staff_attendance.read",
                    "section": "practice",
                    "order": 93,
                }
            ],
        },
    }

    def get_models(self) -> list:
        return [AttendanceEvent]

    def get_router(self) -> APIRouter:
        return router

    def get_permissions(self) -> list[str]:
        # Registry namespaces with the module name -> final perms are
        # ``staff_attendance.read`` / ``staff_attendance.write``.
        return ["read", "write"]
