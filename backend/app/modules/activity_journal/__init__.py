"""activity_journal — append-only, event-driven staff activity log.

Pure listener on the event bus: subscribes to every EventType that is
published transactionally (all its publishers pass ``db=db``, audited
across app/) and writes one immutable row per occurrence inside the
publisher's transaction (ADR 0019). Writes only to its own table; the
schema is designed for the GDPR audit-trail work (#44) to build on.

Standalone module: depends on nothing. Staff-activity data is sensitive
(who did what), so ``role_permissions`` defaults to admin-only, like
expenses; clinics can widen it from the module admin UI.
"""

from fastapi import APIRouter

from app.core.events.types import EventType
from app.core.plugins import BaseModule

from .events import build_handlers
from .models import ActivityJournalEntry
from .router import router

# Every event type whose publishers all publish inside a DB transaction.
# Events with any db-less publisher (email.*, copilot.*, migration.*,
# legacy odontogram updates, ...) are excluded on purpose — a
# transactional handler without a session raises RuntimeError and would
# break those flows. See docs/technical/activity_journal/events.md.
_SUBSCRIBED = [
    # Agenda (incl. the dynamic status-map publishes in agenda/service.py)
    EventType.APPOINTMENT_SCHEDULED,
    EventType.APPOINTMENT_CONFIRMED,
    EventType.APPOINTMENT_CHECKED_IN,
    EventType.APPOINTMENT_IN_TREATMENT,
    EventType.APPOINTMENT_COMPLETED,
    EventType.APPOINTMENT_CANCELLED,
    EventType.APPOINTMENT_NO_SHOW,
    # Budgets
    EventType.BUDGET_SENT,
    EventType.BUDGET_ACCEPTED,
    EventType.BUDGET_REJECTED,
    EventType.BUDGET_CANCELLED,
    EventType.BUDGET_RENEGOTIATED,
    EventType.BUDGET_SUPERSEDED,
    # Billing / payments
    EventType.INVOICE_SENT,
    EventType.PAYMENT_ALLOCATED,
    EventType.PAYMENT_REFUNDED,
    # Patients
    EventType.PATIENT_CREATED,
    EventType.PATIENT_ARCHIVED,
    # Recalls / treatments / lab
    EventType.RECALL_CREATED,
    EventType.ODONTOGRAM_TREATMENT_PERFORMED,
    EventType.LAB_ORDER_STATUS_CHANGED,
    EventType.TREATMENT_PLAN_TREATMENT_ADDED,
    EventType.TREATMENT_PLAN_TREATMENT_REMOVED,
    EventType.TREATMENT_PLAN_ITEM_SESSION_COMPLETED,
    EventType.TREATMENT_PLAN_BUDGET_SYNC_REQUESTED,
    # Documents — generated PDFs (publisher passes db=db).
    EventType.DOCUMENT_GENERATED,
    # Treasury — transfers and corrections (publisher passes db=db).
    EventType.TREASURY_TRANSFERRED,
    EventType.TREASURY_CORRECTED,
]


class ActivityJournalModule(BaseModule):
    """Append-only staff activity log fed by the event bus."""

    manifest = {
        "name": "activity_journal",
        "version": "0.1.0",
        "summary": "Append-only staff activity log recorded from module events.",
        "author": "DentalPin Core Team",
        "license": "BSL-1.1",
        "category": "community",
        "depends": [],
        "installable": True,
        # Optional module: ships inactive, the admin activates it from the
        # module admin UI (repo policy for new non-core modules).
        "auto_install": False,
        "removable": True,
        # Staff-activity data is sensitive — default to admin-only and let
        # each clinic widen it deliberately (same call as expenses).
        "role_permissions": {
            "admin": ["*"],
        },
        "frontend": {
            "layer_path": "frontend",
            "navigation": [
                {
                    "label": "nav.journal",
                    "section": "practice",
                    "icon": "i-lucide-history",
                    "to": "/journal",
                    "permission": "activity_journal.read",
                    "order": 95,
                },
            ],
        },
    }

    def get_models(self) -> list:
        return [ActivityJournalEntry]

    def get_router(self) -> APIRouter:
        return router

    def get_permissions(self) -> list[str]:
        return ["read"]

    def get_tools(self) -> list:
        from . import tools

        return tools.get_tools()

    def get_event_handlers(self) -> dict:
        """Subscribe to every transactionally-published event type."""
        return build_handlers(_SUBSCRIBED)
