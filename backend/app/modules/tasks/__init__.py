"""Tasks module — simple staff handoff board (assign a note, mark it done).

Standalone module: no dependency on any other plugin module. FKs to
``users.id`` need no ``manifest.depends`` entry since ``users`` is a
core table, not a plugin module.
"""

from fastapi import APIRouter

from app.core.plugins import BaseModule

from .models import Task
from .router import router


class TasksModule(BaseModule):
    """Simple staff handoff board: assign a note to someone, mark it done."""

    manifest = {
        "name": "tasks",
        "version": "0.1.0",
        "summary": "Simple staff handoff board — assign a note, mark it done.",
        "author": "Clinic Custom",
        "license": "BSL-1.1",
        "category": "community",
        "depends": [],
        "installable": True,
        "auto_install": True,
        "removable": True,
        "role_permissions": {
            "admin": ["*"],
            "dentist": ["read", "write"],
            "hygienist": ["read", "write"],
            "assistant": ["read", "write"],
            "receptionist": ["read", "write"],
        },
        "frontend": {
            "layer_path": "frontend",
            "navigation": [
                {
                    "label": "nav.tasks",
                    "icon": "i-lucide-list-checks",
                    "to": "/tasks",
                    "permission": "tasks.read",
                    "order": 94,
                },
            ],
        },
    }

    def get_models(self) -> list:
        return [Task]

    def get_router(self) -> APIRouter:
        return router

    def get_permissions(self) -> list[str]:
        return ["read", "write"]

    def get_tools(self) -> list:
        from . import tools

        return tools.get_tools()

    def get_event_handlers(self) -> dict:
        # Phase 6: the official extension point for event subscriptions —
        # the loader calls this exactly once per final (deduplicated)
        # module instance, unlike a manual subscribe() in __init__, which
        # double-fires when DENTALPIN_DEV_MODULE_SCAN's filesystem-scan
        # fallback briefly instantiates a second, discarded copy of this
        # module (its __init__ still runs before the duplicate is thrown
        # away). This is what caused the "2 tasks from 1 status change" bug.
        from .handlers import _on_lab_order_ready

        return {"lab_order.status_changed": _on_lab_order_ready}
