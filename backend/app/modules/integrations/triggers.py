"""Event types and API token scopes this module actually supports.

Phase 1 shipped two working triggers end-to-end (issue #65); Phase 2
adds the concrete-appointment status set and the budget workflow set —
every one of these has a real publisher that passes its session via
``db=`` (which the ADR 0019 guard test enforces) and a payload whose
``clinic_id`` is present, so a transactional ``_enqueue`` handler can
send it out clinic-scoped.

Almost every other event issue #65 §3 wants already exists on the bus
(``core/events/types.py``) — adding it here means only "declare a new
transactional handler in handlers.py", no new bus infra. Keeping this
list separate from ``EventType`` (which has ~60 events, most
irrelevant to webhooks) is what lets ``WebhookSubscriptionCreate``
reject a subscription for an event nobody will ever deliver, instead
of silently accepting one that never fires.

``SUPPORTED_TOKEN_SCOPES`` is the same idea for API tokens. The public
data-read API (Phase 2) enforces them per endpoint; ``patients:read``
gates the read surface and ``patients:write`` the write surface. The
MCP module consumes both (see ``docs/technical/mcp/overview.md``).
"""

from app.core.events import EventType

SUPPORTED_EVENT_TYPES: frozenset[str] = frozenset(
    {
        EventType.PATIENT_CREATED,
        EventType.APPOINTMENT_COMPLETED,
        # Phase 2 — concrete appointment lifecycle (agenda publishes each of
        # these with its session; payloads carry clinic_id).
        EventType.APPOINTMENT_SCHEDULED,
        EventType.APPOINTMENT_CANCELLED,
        EventType.APPOINTMENT_NO_SHOW,
        # Phase 2 — budget workflow (accept/reject/send drive the issue's
        # "treatment plan accepted/rejected" use cases; treatment_plan on
        # the bus defers to budget for those transitions).
        EventType.BUDGET_SENT,
        EventType.BUDGET_ACCEPTED,
        EventType.BUDGET_REJECTED,
    }
)

SUPPORTED_TOKEN_SCOPES: frozenset[str] = frozenset({"patients:read", "patients:write"})
