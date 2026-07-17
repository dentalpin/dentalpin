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

    def __init__(self) -> None:
        # Phase 6: re-attach the lab_orders event subscription on every
        # boot — the in-memory event bus is wiped on restart, so this
        # can't only happen in `install()` (which only runs once, from
        # the admin UI). Idempotent-safe: subscribing twice would only
        # matter if this constructor ran twice for the same instance,
        # which the module loader doesn't do. Same reasoning as verifactu.
        from .handlers import register_event_handlers

        register_event_handlers()

    def get_models(self) -> list:
        return [Task]

    def get_router(self) -> APIRouter:
        return router

    def get_permissions(self) -> list[str]:
        return ["read", "write"]

    def get_tools(self) -> list:
        from . import tools

        return tools.get_tools()

    async def uninstall(self, ctx) -> None:
        from .handlers import unregister_event_handlers

        unregister_event_handlers()
