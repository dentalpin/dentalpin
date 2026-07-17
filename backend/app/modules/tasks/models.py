"""Task entity — a simple staff handoff note: assign it, mark it done.

No real-time chat, no read receipts, no "typing" state — deliberately
simple per the clinic's decision for Phase 5 of the custom roadmap.
FKs to ``users.id`` need no ``manifest.depends`` entry: ``users`` is a
core table, not a plugin module (same pattern already used by
``expenses.created_by`` and ``lab_orders.created_by``).
"""

from __future__ import annotations

from datetime import date
from uuid import uuid4

from sqlalchemy import Date, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base, TimestampMixin

TASK_PRIORITIES = ("low", "normal", "high")
TASK_STATUSES = ("open", "done")


class Task(Base, TimestampMixin):
    """A staff handoff note: assign it to someone, they mark it done."""

    __tablename__ = "tasks"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    clinic_id: Mapped[UUID] = mapped_column(ForeignKey("clinics.id"), index=True)

    title: Mapped[str] = mapped_column(String(300))
    description: Mapped[str | None] = mapped_column(Text)
    priority: Mapped[str] = mapped_column(String(10), default="normal")
    status: Mapped[str] = mapped_column(String(10), index=True, default="open")

    assigned_to: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"), index=True)
    assigned_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))

    due_date: Mapped[date | None] = mapped_column(Date)
    completed_at: Mapped[date | None] = mapped_column(Date)
