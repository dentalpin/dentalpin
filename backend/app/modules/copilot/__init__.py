"""Copilot module — conversational AI agent over DentalPin (issue #81).

A thin *surface* over the core agentic engine (``app/core/agents`` +
``app/core/llm``). Consumes tools through the global registry only;
never imports another module's service, so it keeps ``depends = []`` and
stays cleanly removable. Per-user RBAC parity: the agent can never see
or do anything the calling user couldn't through the UI.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.core.events.types import EventType
from app.core.plugins import BaseModule
from app.core.scheduling import ScheduledJob

from .models import CopilotConversation, CopilotMessage, CopilotNudge, CopilotSettings
from .router import router


class CopilotModule(BaseModule):
    manifest = {
        "name": "copilot",
        "version": "0.1.0",
        "summary": "Conversational AI agent over DentalPin, scoped to the caller's permissions.",
        "author": "DentalPin Core Team",
        "license": "BSL-1.1",
        "category": "official",
        "depends": [],
        "installable": True,
        "auto_install": True,
        "removable": True,
        "role_permissions": {
            "admin": ["*"],
            "dentist": ["chat", "history.read"],
            "hygienist": ["chat", "history.read"],
            "assistant": ["chat", "history.read"],
            "receptionist": ["chat", "history.read"],
        },
        "frontend": {
            "layer_path": "frontend",
            # No sidebar entry — CopilotMount.vue (fixed bottom-right FAB,
            # Cmd/Ctrl+K) is the only entry point now. It's a fully
            # independent floating component, unaffected by this — the
            # /copilot route and its layer are still registered via
            # layer_path above, just not linked from the sidebar.
            "navigation": [],
        },
    }

    def get_models(self) -> list:
        return [CopilotConversation, CopilotMessage, CopilotNudge, CopilotSettings]

    def get_router(self) -> APIRouter:
        return router

    def get_event_handlers(self) -> dict:
        # Proactive nudges (ADR 0014 §Deferred). Subscription only — no
        # cross-module import, so depends = [] holds (ADR 0003).
        from .events import on_appointment_cancelled

        return {EventType.APPOINTMENT_CANCELLED: on_appointment_cancelled}

    def get_permissions(self) -> list[str]:
        # Registry namespaces → copilot.chat, copilot.history.read, etc.
        return ["chat", "history.read", "history.read_all", "supervise", "configure"]

    def get_tools(self) -> list:
        # Copilot consumes tools; it exposes none of its own.
        return []

    def get_scheduled_jobs(self) -> list[ScheduledJob]:
        # Morning digest — hourly gate; the task matches each clinic's
        # digest_hour against the current hour and no-ops otherwise.
        from .tasks import send_morning_digests

        return [
            ScheduledJob(
                id="copilot_morning_digests",
                func=send_morning_digests,
                trigger="cron",
                trigger_args={"minute": 0},
                name="Send the copilot morning digest to opted-in clinics (hourly gate)",
            ),
        ]
