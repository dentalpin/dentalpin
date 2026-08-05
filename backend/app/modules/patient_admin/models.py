"""patient_admin — patient-to-patient relationships (Lien de Parentée).

Originally also held a manually-entered exemption-status table, removed in
Phase 8.1: APCI turned out to mean "on the Liste des Affections Prises en
Charge Intégralement" — i.e. it's derived from which systemic disease is
recorded, not a separately-entered field. That check now belongs with the
reference-data work (systemic disease reference list + cross-check), not
here. See migration padm_0002 for the table drop.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base, TimestampMixin

if TYPE_CHECKING:
    from app.modules.patients.models import Patient


class PatientRelationship(Base, TimestampMixin):
    """Directed link: ``related_patient`` is ``patient``'s ``relationship_type``.

    One row per pair — the inverse label (parent<->child, spouse<->spouse,
    sibling<->sibling, guardian<->ward, other<->other) is derived at read
    time (see ``service.py``), not stored, so the two sides can never drift
    out of sync.
    """

    __tablename__ = "patient_admin_relationship"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    clinic_id: Mapped[UUID] = mapped_column(ForeignKey("clinics.id"), index=True)

    patient_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("patients.id", ondelete="CASCADE"),
        index=True,
    )
    related_patient_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("patients.id", ondelete="CASCADE"),
        index=True,
    )
    # parent | child | spouse | sibling | guardian | ward | other
    relationship_type: Mapped[str] = mapped_column(String(20))
    notes: Mapped[str | None] = mapped_column(Text)

    patient: Mapped[Patient] = relationship(foreign_keys=[patient_id])
    related_patient: Mapped[Patient] = relationship(foreign_keys=[related_patient_id])

    __table_args__ = (
        UniqueConstraint("patient_id", "related_patient_id", name="uq_patient_admin_relationship_pair"),
    )
