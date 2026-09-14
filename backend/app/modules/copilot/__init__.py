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
            "navigation": [
                {
                    "label": "nav.copilot",
                    "icon": "i-lucide-sparkles",
                    "to": "/copilot",
                    "permission": "copilot.chat",
                    "order": 90,
                },
            ],
        },
    }

    def on_activate(self) -> None:
        # Re-attach built-in providers on every boot while copilot is
        # installed. In-memory registrations belong here per ADR 0020.
        from app.core.llm.factory import ANTHROPIC_SPEC, OPENAI_SPEC
        from app.core.llm.registry import llm_provider_registry

        llm_provider_registry.register(OPENAI_SPEC)
        llm_provider_registry.register(ANTHROPIC_SPEC)

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
