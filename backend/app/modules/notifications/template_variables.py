"""Patient-facing template fields drawn from the standard notification producers."""

from datetime import UTC, datetime

from .channels import Channel
from .models import NotificationType
from .service import appointment_when_context

_APPOINTMENT = ("appointment_date", "appointment_time", "professional_name")
_CONTACT = ("clinic_phone", "clinic_address")

# These are send-time keys, independent of the legacy template row's variables
# metadata and of the internal fields used to identify or revalidate an event.
_EVENT_FIELDS: dict[NotificationType, tuple[str, ...]] = {
    "appointment_confirmation": (*_APPOINTMENT, *_CONTACT),
    "appointment_reminder": (*_APPOINTMENT, *_CONTACT, "checkin_url"),
    "appointment_cancelled": (*_APPOINTMENT, "cancellation_reason", "clinic_phone"),
    "welcome": _CONTACT,
    "budget_sent": (
        "budget_number",
        "budget_date",
        "treatments",
        "subtotal",
        "discount_amount",
        "total",
        "validity_days",
        "notes",
        "custom_message",
        "clinic_phone",
        "public_url",
    ),
    "budget_accepted": ("budget_number", "accepted_date", "total", "notes", "clinic_phone"),
    "budget_reminder": (
        "budget_number",
        "milestone_days",
        "total",
        "valid_until",
        "public_url",
        "clinic_phone",
    ),
    "invoice_sent": (
        "invoice_number",
        "invoice_date",
        "due_date",
        "items",
        "subtotal",
        "total_discount",
        "total_tax",
        "total",
        "balance_due",
        "billing_name",
        "custom_message",
        *_CONTACT,
    ),
    "recall_reminder": ("reason", "due_month"),
}

# Also treat fields absent on the generic staff-send path as optional. For
# example, that path supplies a check-in link only if caller context has one.
_OPTIONAL = {
    "clinic_phone",
    "clinic_address",
    "professional_name",
    "cancellation_reason",
    "checkin_url",
    "discount_amount",
    "validity_days",
    "due_date",
    "invoice_date",
    "total_discount",
    "total_tax",
    "notes",
    "custom_message",
    "public_url",
    "valid_until",
    "reason",
    "due_month",
    "billing_name",
    "milestone_days",
}
# staff/manual paths do not populate invoice or recall details automatically
_PATH_OPTIONAL = {
    "invoice_sent": set(_EVENT_FIELDS["invoice_sent"]) - set(_CONTACT),
    "recall_reminder": {"due_month", "reason"},
    "budget_reminder": {"budget_number", "total"},
    "budget_accepted": {"accepted_date"},
}

_PRIVATE_ON_WHATSAPP = {
    "items",
    "treatments",
    "notes",
    "custom_message",
    "reason",
    "cancellation_reason",
    "billing_name",
    "balance_due",
    "subtotal",
    "discount_amount",
    "total_discount",
    "total_tax",
    "total",
}


def available_fields(key: NotificationType, channel: Channel) -> tuple[str, ...]:
    if channel not in (Channel.EMAIL, Channel.WHATSAPP):
        return ()
    fields = ("patient_name", "clinic_name", "locale", *_EVENT_FIELDS[key])
    return tuple(
        field for field in fields if channel == Channel.EMAIL or field not in _PRIVATE_ON_WHATSAPP
    )


def example_context(key: NotificationType, locale: str, clinic, *, minimal: bool = False) -> dict:
    context = {
        "patient_name": "Alex Example",
        "clinic_name": "Clínica Ejemplo" if locale == "es" else "Example Dental",
        "locale": locale,
        "clinic_phone": "+34 900 000 000",
        "clinic_address": "42 Example Street",
        "professional_name": "Sam Example",
        **appointment_when_context(datetime(2027, 3, 8, 9, 30, tzinfo=UTC), clinic, locale),
        "cancellation_reason": "Schedule change",
        "checkin_url": "https://example.invalid/check-in",
        "public_url": "https://example.invalid/estimate",
        "budget_number": "QUOTE-001",
        "budget_date": "01/03/2027",
        "treatments": [{"name": "Example item", "tooth": None, "price": 100.0}],
        "subtotal": 100.0,
        "total": 90.0,
        "discount_amount": 10.0,
        "validity_days": 30,
        "notes": "Example note",
        "custom_message": "Example message",
        "accepted_date": "02/03/2027",
        "milestone_days": 7,
        "valid_until": "31/03/2027",
        "invoice_number": "INV-001",
        "invoice_date": "02/03/2027",
        "due_date": "31/03/2027",
        "items": [
            {"description": "Example item", "quantity": 1, "unit_price": 100.0, "line_total": 100.0}
        ],
        "total_discount": 10.0,
        "total_tax": 0.0,
        "balance_due": 45.0,
        "billing_name": "Alex Example",
        "reason": "Routine check-up",
        "due_month": "03/2027",
    }
    optional = optional_fields(key) if minimal else set()
    return {
        field: context[field]
        for field in available_fields(key, Channel.EMAIL)
        if field not in optional
    }


def optional_fields(key: NotificationType) -> set[str]:
    return _OPTIONAL | _PATH_OPTIONAL.get(key, set())
