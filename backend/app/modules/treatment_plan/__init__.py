"""Treatment plan module - orchestrates patient treatment workflows.

This module provides:
- Treatment plan creation and management
- Integration with odontogram treatments (ToothTreatment)
- Budget synchronization via event bus
- Appointment treatment tracking
- Media attachments for before/after documentation
"""

from typing import Any

from fastapi import APIRouter

from app.core.events.types import EventType
from app.core.plugins import BaseModule
from app.core.scheduling import ScheduledJob

from .models import (
    PlannedTreatmentItem,
    TreatmentPlan,
)
from .owner_resolvers import register as _register_attachment_owners
from .router import router

# Register the ``plan_item`` attachment owner_type with media at import
# time. Safe because ``media`` is in ``manifest.depends`` and Python
# import order resolves it first.
_register_attachment_owners()


class TreatmentPlanModule(BaseModule):
    """Treatment plan module for orchestrating patient treatment workflows.

    Features:
    - Treatment plan CRUD with status workflow
    - Integration with ToothTreatment (odontogram)
    - Budget generation and synchronization
    - Event-driven communication with other modules
    - Media attachments for treatment documentation
    """

    manifest = {
        "name": "treatment_plan",
        "version": "0.1.0",
        "summary": "Patient treatment plans with budget + odontogram sync.",
        "author": "DentalPin Core Team",
        "license": "BSL-1.1",
        "category": "official",
        "depends": ["patients", "agenda", "odontogram", "catalog", "budget", "media"],
        "installable": True,
        "auto_install": True,
        "removable": False,
        "role_permissions": {
            "admin": ["*"],
            "dentist": ["*"],
            "hygienist": ["plans.read"],
            "assistant": [
                "plans.read",
                "plans.write",
            ],
            # Reception drives the bandeja de planes: read + write notes
            # + close (terminal transitions tied to patient outcomes) +
            # reactivate (welcoming a returning patient back to draft).
            # Confirm stays with the doctor.
            "receptionist": [
                "plans.read",
                "plans.write",
                "plans.close",
                "plans.reactivate",
            ],
        },
        "frontend": {
            "layer_path": "frontend",
            "navigation": [
                {
                    "label": "nav.treatmentPlans",
                    "icon": "i-lucide-clipboard-list",
                    "to": "/treatment-plans",
                    "permission": "treatment_plan.plans.read",
                    "order": 30,
                },
            ],
        },
    }

    def get_models(self) -> list:
        return [
            TreatmentPlan,
            PlannedTreatmentItem,
        ]

    def get_router(self) -> APIRouter:
        return router

    def get_scheduled_jobs(self) -> list[ScheduledJob]:
        from .tasks import auto_close_expired_plans

        return [
            ScheduledJob(
                id="auto_close_expired_plans",
                func=auto_close_expired_plans,
                trigger="cron",
                trigger_args={"hour": 3, "minute": 0},
                name="Close pending plans whose budgets have been expired > N days (daily 03:00)",
            ),
        ]

    def get_permissions(self) -> list[str]:
        return [
            "plans.read",
            "plans.write",
            # Workflow transitions split out for fine-grained RBAC.
            "plans.confirm",
            "plans.close",
            "plans.reactivate",
        ]

    def get_event_handlers(self) -> dict[str, Any]:
        from .events import (
            on_appointment_completed,
            on_budget_accepted,
            on_budget_cancelled,
            on_budget_rejected,
            on_budget_renegotiated,
            on_budget_superseded,
            on_treatment_performed,
        )

        return {
            EventType.APPOINTMENT_COMPLETED: on_appointment_completed,
            EventType.BUDGET_ACCEPTED: on_budget_accepted,
            EventType.BUDGET_CANCELLED: on_budget_cancelled,
            EventType.BUDGET_REJECTED: on_budget_rejected,
            EventType.BUDGET_RENEGOTIATED: on_budget_renegotiated,
            EventType.BUDGET_SUPERSEDED: on_budget_superseded,
            EventType.ODONTOGRAM_TREATMENT_PERFORMED: on_treatment_performed,
        }
