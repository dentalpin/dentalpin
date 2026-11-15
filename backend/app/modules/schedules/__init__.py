"""Schedules module — clinic + professional operating hours.

First officially-removable module. Provides clinic weekly hours,
per-professional weekly schedules, date-range overrides (vacations,
holidays, reduced hours), an availability resolver consumed by the
agenda calendar via HTTP (no cross-module import), plus occupancy
analytics over the agenda's appointments.

Agenda must NEVER declare ``depends: ["schedules"]`` — that would
make schedules required and defeat the uninstall story. Integration
goes the other way: agenda's frontend calls
``GET /api/v1/schedules/availability`` with a 404-tolerant composable
that falls back to the legacy 08:00–21:00 bounds when the module is
uninstalled.
"""

from fastapi import APIRouter

from app.core.plugins import BaseModule

from .events import (
    on_appointment_cancelled,
    on_appointment_scheduled,
    on_appointment_updated,
    on_clinic_created,
)
from .models import (
    ClinicOverride,
    ClinicWeeklySchedule,
    ProfessionalOverride,
    ProfessionalWeeklySchedule,
    ScheduleShift,
)
from .router import router


class SchedulesModule(BaseModule):
    manifest = {
        "name": "schedules",
        "version": "0.1.0",
        "summary": (
            "Clinic + professional operating hours, overrides, availability, "
            "and occupancy analytics."
        ),
        "author": "DentalPin Core Team",
        "license": "BSL-1.1",
        "category": "official",
        "depends": ["agenda"],
        "installable": True,
        "auto_install": True,
        "removable": True,
        "role_permissions": {
            "admin": ["*"],
            "dentist": [
                "clinic_hours.read",
                "professional.own.read",
                "professional.own.write",
                "availability.read",
                "analytics.read",
            ],
            "hygienist": [
                "clinic_hours.read",
                "professional.own.read",
                "professional.own.write",
                "availability.read",
            ],
            "assistant": [
                "clinic_hours.read",
                "professional.read",
                "availability.read",
                "assistant.own.read",
                "assistant.own.write",
            ],
            "receptionist": [
                "clinic_hours.read",
                "professional.read",
                "assistant.read",
                "assistant.write",
                "availability.read",
                "analytics.read",
            ],
        },
        "frontend": {
            "layer_path": "frontend",
            "navigation": [],
        },
    }

    def get_models(self) -> list:
        return [
            ClinicWeeklySchedule,
            ClinicOverride,
            ProfessionalWeeklySchedule,
            ProfessionalOverride,
            ScheduleShift,
        ]

    def get_router(self) -> APIRouter:
        return router

    def get_permissions(self) -> list[str]:
        return [
            "clinic_hours.read",
            "clinic_hours.write",
            "professional.read",
            "professional.write",
            "professional.own.read",
            "professional.own.write",
            "assistant.read",
            "assistant.write",
            "assistant.own.read",
            "assistant.own.write",
            "availability.read",
            "analytics.read",
        ]

    def get_tools(self) -> list:
        from . import tools

        return tools.get_tools()

    def get_event_handlers(self) -> dict:
        return {
            "appointment.scheduled": on_appointment_scheduled,
            "appointment.updated": on_appointment_updated,
            "appointment.cancelled": on_appointment_cancelled,
            "clinic.created": on_clinic_created,
        }
