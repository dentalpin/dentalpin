"""Phase 6 connector: lab_orders → tasks.

Subscribes to the ``lab_order.status_changed`` event (published by the
``lab_orders`` module) and auto-creates a handoff task when an order
becomes "ready" — e.g. "Call patient — crown ready for pickup."

``tasks`` does NOT declare a dependency on ``lab_orders`` in its manifest:
this is a one-way, event-only connection. If ``lab_orders`` isn't
installed, this handler simply never fires (no event to receive) — tasks
still works standalone. This mirrors how ``verifactu`` subscribes to a
core event without importing the publisher's internals.
"""

from __future__ import annotations

from datetime import date
from uuid import UUID

from app.core.events import event_bus
from app.database import async_session_maker

from .models import Task

_WORK_TYPE_LABELS = {
    "crown": "crown",
    "bridge": "bridge",
    "denture": "denture",
    "implant": "implant",
    "veneer": "veneer",
    "orthodontic": "orthodontic appliance",
    "other": "lab work",
}


async def _on_lab_order_ready(payload: dict) -> None:
    if payload.get("status") != "ready":
        return

    work_type = _WORK_TYPE_LABELS.get(payload.get("work_type", ""), "lab work")
    title = f"Call patient — {work_type} ready"
    tooth = payload.get("tooth_reference")
    description = f"Tooth {tooth}" if tooth else None

    async with async_session_maker() as db:
        task = Task(
            clinic_id=UUID(payload["clinic_id"]),
            title=title,
            description=description,
            priority="normal",
            status="open",
            due_date=date.today(),
        )
        db.add(task)
        await db.commit()


def register_event_handlers() -> None:
    event_bus.subscribe("lab_order.status_changed", _on_lab_order_ready)


def unregister_event_handlers() -> None:
    event_bus.unsubscribe("lab_order.status_changed", _on_lab_order_ready)
