"""Notifications module - email notifications and preferences management."""

from fastapi import APIRouter

from app.core.events.types import EventType
from app.core.plugins import BaseModule
from app.core.scheduling import ScheduledJob

from . import channels  # noqa: F401 — registers the built-in EmailAdapter at import
from .models import (
    ClinicChannelSettings,
    ClinicNotificationSettings,
    ClinicSmtpSettings,
    CommunicationMessage,
    NotificationPreference,
    NotificationTemplate,
)
from .router import router


class NotificationsModule(BaseModule):
    """Notifications module providing email notifications management.

    Features:
    - Customizable email templates per clinic
    - Patient notification preferences
    - Clinic-level settings for auto/manual sending
    - Email logs and auditing
    - Event-driven notifications
    """

    manifest = {
        "name": "notifications",
        "version": "0.1.0",
        "summary": "Email templates, preferences, SMTP, event-driven sending.",
        "author": "DentalPin Core Team",
        "license": "BSL-1.1",
        "category": "official",
        "depends": ["patients", "agenda", "budget", "billing", "catalog"],
        "installable": True,
        "auto_install": True,
        "removable": False,
        "role_permissions": {
            "admin": ["*"],
            # settings.read: every send surface (appointment modal, quote /
            # invoice send) reads GET /settings to know which channel
            # buttons to render (#287) — write stays admin-only.
            "dentist": ["preferences.read", "preferences.write", "send", "settings.read"],
            "hygienist": [],
            "assistant": ["preferences.read", "preferences.write", "send", "settings.read"],
            "receptionist": ["preferences.read", "preferences.write", "send", "settings.read"],
        },
        "frontend": {
            "layer_path": "frontend",
        },
    }

    def get_models(self) -> list:
        return [
            NotificationTemplate,
            NotificationPreference,
            ClinicNotificationSettings,
            ClinicChannelSettings,
            ClinicSmtpSettings,
            CommunicationMessage,
        ]

    def get_router(self) -> APIRouter:
        return router

    def get_tools(self) -> list:
        from . import tools

        return tools.get_tools()

    def get_scheduled_jobs(self) -> list[ScheduledJob]:
        from .tasks import dispatch_outbox, process_appointment_reminders

        return [
            ScheduledJob(
                id="appointment_reminders",
                func=process_appointment_reminders,
                trigger="interval",
                trigger_args={"minutes": 5},
                name="Process appointment reminders (every 5 minutes)",
            ),
            ScheduledJob(
                id="notifications_dispatch_outbox",
                func=dispatch_outbox,
                trigger="interval",
                trigger_args={"seconds": 45},
                name="Dispatch the notifications outbox (every 45s)",
            ),
        ]

    def get_permissions(self) -> list[str]:
        return [
            "templates.read",  # View email templates
            "templates.write",  # Edit email templates
            "preferences.read",  # View notification preferences
            "preferences.write",  # Edit notification preferences
            "logs.read",  # View email logs
            "send",  # Send emails manually
            "settings.read",  # View clinic notification settings
            "settings.write",  # Edit clinic notification settings
        ]

    def get_event_handlers(self) -> dict:
        from .handlers import NotificationHandlers

        return {
            EventType.APPOINTMENT_SCHEDULED: NotificationHandlers.on_appointment_scheduled,
            EventType.APPOINTMENT_CANCELLED: NotificationHandlers.on_appointment_cancelled,
            EventType.PATIENT_CREATED: NotificationHandlers.on_patient_created,
            EventType.BUDGET_SENT: NotificationHandlers.on_budget_sent,
            EventType.BUDGET_ACCEPTED: NotificationHandlers.on_budget_accepted,
            EventType.BUDGET_REMINDER_SENT: NotificationHandlers.on_budget_reminder_sent,
            EventType.INVOICE_SENT: NotificationHandlers.on_invoice_sent,
        }
