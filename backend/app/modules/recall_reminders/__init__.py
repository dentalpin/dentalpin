"""recall_reminders — connects the upstream `recalls` module to the
upstream `notifications` gateway.

Phase 6 of the custom roadmap. `recalls` already publishes
`EventType.RECALL_CREATED` but "never sends" anything (by its own design —
see its CLAUDE.md). `notifications` already has a full delivery gateway
but nothing calls it for recalls. This module is pure glue: it has no
models, no UI, no API surface of its own — it just subscribes to one
event and calls one existing function.

Depends on both `recalls` and `notifications` for the imports below (ADR
0002 / 0003 — legal cross-module reads/calls because both are declared).

REQUIRES a "recall_reminder" notification template to exist (any channel)
or every recall will enqueue a message that gets silently skipped for lack
of a template. There is no dedicated Templates UI for this (checked — it
doesn't exist in the current frontend); create it via a direct API call
to `POST /api/v1/notifications/templates` (e.g. through the /docs page)
instead.
"""

from fastapi import APIRouter

from app.core.plugins import BaseModule


class RecallRemindersModule(BaseModule):
    manifest = {
        "name": "recall_reminders",
        "version": "0.1.0",
        "summary": "Connects recalls to the notifications gateway — auto-reminds patients when a recall is created.",
        "author": "Clinic Custom",
        "license": "BSL-1.1",
        "category": "community",
        "depends": ["recalls", "notifications"],
        "installable": True,
        "auto_install": False,
        "removable": True,
        "role_permissions": {"admin": ["*"]},
        "frontend": {
            "layer_path": "frontend",
            "navigation": [],  # pure backend glue, nothing to show
        },
    }

    def get_models(self) -> list:
        return []

    def get_router(self) -> APIRouter:
        return APIRouter()

    def get_permissions(self) -> list[str]:
        return []

    def get_event_handlers(self) -> dict:
        # The official extension point — called exactly once per final
        # (deduplicated) module instance. A manual subscribe() in
        # __init__ double-fires under DENTALPIN_DEV_MODULE_SCAN's
        # filesystem-scan fallback, which briefly instantiates (and
        # discards) a second copy of this module — its __init__ still
        # runs before the duplicate is thrown away. Same fix as `tasks`.
        from .handlers import _on_recall_created
        from app.core.events import EventType

        return {EventType.RECALL_CREATED: _on_recall_created}
