"""Optional online booking module; public surface is disabled by default."""

from fastapi import APIRouter

from app.core.plugins import BaseModule
from app.core.scheduling import ScheduledJob

from .models import BookingMail, BookingRateLimit, BookingRequest, BookingSettings


class OnlineBookingModule(BaseModule):
    manifest = {
        "name": "online_booking",
        "version": "0.1.0",
        "summary": "Online booking requests",
        "author": "DentalPin Core Team",
        "license": "BSL-1.1",
        "category": "official",
        "depends": ["agenda", "schedules", "patients", "notifications"],
        "installable": True,
        "auto_install": False,
        "removable": True,
        "role_permissions": {"admin": ["*"], "receptionist": ["read", "write"]},
        "frontend": {
            "layer_path": "frontend",
            "navigation": [
                {
                    "label": "onlineBooking.title",
                    "icon": "i-lucide-calendar-check",
                    "to": "/online-booking",
                    "permission": "online_booking.read",
                    "order": 26,
                }
            ],
        },
    }

    def get_models(self) -> list:
        return [BookingSettings, BookingRequest, BookingRateLimit, BookingMail]

    def get_router(self) -> APIRouter:
        from .router import router

        return router

    def get_permissions(self) -> list[str]:
        return ["read", "write", "settings"]

    def get_scheduled_jobs(self) -> list[ScheduledJob]:
        from .tasks import cleanup, dispatch_mail

        return [
            ScheduledJob(
                id="online_booking_dispatch_mail",
                func=dispatch_mail,
                trigger="interval",
                trigger_args={"seconds": 15},
                name="Dispatch booking emails",
            ),
            ScheduledJob(
                id="online_booking_cleanup",
                func=cleanup,
                trigger="interval",
                trigger_args={"minutes": 15},
                name="Expire and purge online booking requests",
            ),
        ]
