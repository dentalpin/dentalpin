"""patient_timeline — unified patient activity log.

Cross-module audit stream. Populated by event handlers that react to
patient.*, appointment.*, treatment.*, budget.*, invoice.*, notification.*,
and document.* events from other modules.

Handlers live in ``events.py``. They read only from the event payload and
own their DB sessions, so the module stays removable in isolation (no
hard coupling to agenda / odontogram / budget / billing / etc.).
"""

from typing import Any

from fastapi import APIRouter

from app.core.events import EventType
from app.core.plugins import BaseModule

from . import events
from .models import PatientTimeline
from .router import router


class PatientTimelineModule(BaseModule):
    """Timeline module: logs cross-module patient events."""

    manifest = {
        "name": "patient_timeline",
        "version": "0.1.0",
        "summary": "Patient timeline — unified activity log.",
        "author": "DentalPin Core Team",
        "license": "BSL-1.1",
        "category": "official",
        "depends": ["patients"],
        "installable": True,
        "auto_install": True,
        "removable": False,
        "role_permissions": {
            "admin": ["*"],
            "dentist": ["read"],
            "hygienist": ["read"],
            "assistant": ["read"],
            "receptionist": ["read"],
        },
        "frontend": {
            "layer_path": "frontend",
        },
    }

    def get_models(self) -> list:
        return [PatientTimeline]

    def get_router(self) -> APIRouter:
        return router

    def get_permissions(self) -> list[str]:
        return ["read"]

    def get_tools(self) -> list:
        from . import tools

        return tools.get_tools()

    def get_event_handlers(self) -> dict[str, Any]:
        """Populate the timeline from other modules' events."""
        return {
            # Visits
            EventType.APPOINTMENT_SCHEDULED: events.on_appointment_scheduled,
            EventType.APPOINTMENT_CONFIRMED: events.on_appointment_confirmed,
            EventType.APPOINTMENT_CHECKED_IN: events.on_appointment_checked_in,
            EventType.APPOINTMENT_IN_TREATMENT: events.on_appointment_in_treatment,
            EventType.APPOINTMENT_COMPLETED: events.on_appointment_completed,
            EventType.APPOINTMENT_CANCELLED: events.on_appointment_cancelled,
            EventType.APPOINTMENT_NO_SHOW: events.on_appointment_no_show,
            # Treatments
            EventType.ODONTOGRAM_TREATMENT_PERFORMED: events.on_tooth_treatment_performed,
            EventType.TREATMENT_PLAN_CREATED: events.on_plan_created,
            EventType.TREATMENT_PLAN_TREATMENT_COMPLETED: events.on_plan_item_completed,
            # Financial
            EventType.BUDGET_SENT: events.on_budget_sent,
            EventType.BUDGET_ACCEPTED: events.on_budget_accepted,
            EventType.BUDGET_REJECTED: events.on_budget_rejected,
            EventType.BUDGET_EXPIRED: events.on_budget_expired,
            EventType.BUDGET_RENEGOTIATED: events.on_budget_renegotiated,
            EventType.BUDGET_VIEWED: events.on_budget_viewed,
            EventType.BUDGET_REMINDER_SENT: events.on_budget_reminder_sent,
            # Treatment plan workflow transitions
            EventType.TREATMENT_PLAN_CONFIRMED: events.on_treatment_plan_confirmed,
            EventType.TREATMENT_PLAN_CLOSED: events.on_treatment_plan_closed,
            EventType.TREATMENT_PLAN_REACTIVATED: events.on_treatment_plan_reactivated,
            EventType.INVOICE_ISSUED: events.on_invoice_issued,
            EventType.INVOICE_PAID: events.on_invoice_paid,
            # Communications — the generic notification.* events cover every
            # channel (email, whatsapp, …). The legacy email.* events are NOT
            # subscribed anymore: the gateway dual-publishes them for
            # channel=email for one release, so keeping both would record
            # every email send twice (issue #287 bug 12).
            EventType.NOTIFICATION_SENT: events.on_notification_sent,
            EventType.NOTIFICATION_FAILED: events.on_notification_failed,
            EventType.NOTIFICATION_REPLY_RECEIVED: events.on_notification_reply_received,
            # Medical history
            EventType.PATIENT_MEDICAL_UPDATED: events.on_medical_updated,
            # Documents + photos
            EventType.DOCUMENT_UPLOADED: events.on_document_uploaded,
            EventType.PHOTO_UPLOADED: events.on_photo_uploaded,
            EventType.PAIR_CREATED: events.on_pair_created,
            # Clinical notes (clinical_notes module — single handler covers
            # administrative / diagnosis / treatment / treatment_plan).
            EventType.CLINICAL_NOTE_ADMINISTRATIVE_CREATED: events.on_clinical_note_created,
            EventType.CLINICAL_NOTE_DIAGNOSIS_CREATED: events.on_clinical_note_created,
            EventType.CLINICAL_NOTE_TREATMENT_CREATED: events.on_clinical_note_created,
            EventType.CLINICAL_NOTE_PLAN_CREATED: events.on_clinical_note_created,
            EventType.AGENDA_VISIT_NOTE_UPDATED: events.on_visit_note_updated,
            EventType.TREATMENT_PLAN_ITEM_COMPLETED_WITHOUT_NOTE: (
                events.on_item_completed_without_note
            ),
        }
