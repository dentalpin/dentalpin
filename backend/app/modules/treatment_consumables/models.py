"""TreatmentConsumable junction — links a catalog treatment to the
inventory items it consumes, and how many of each.

Read-only relationship to `catalog` (TreatmentCatalogItem) and
`inventory` (InventoryItem) — this module never writes to either.
"""

from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

from sqlalchemy import ForeignKey, Index, Numeric, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base, TimestampMixin


class TreatmentConsumable(Base, TimestampMixin):
    """One row = "treatment X needs N units of inventory item Y"."""

    __tablename__ = "treatment_consumables"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    clinic_id: Mapped[UUID] = mapped_column(ForeignKey("clinics.id"), index=True)

    treatment_id: Mapped[UUID] = mapped_column(
        ForeignKey("treatment_catalog_items.id", ondelete="CASCADE"), index=True
    )
    inventory_item_id: Mapped[UUID] = mapped_column(
        ForeignKey("inventory_items.id", ondelete="CASCADE"), index=True
    )

    quantity_needed: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=1)

    __table_args__ = (
        UniqueConstraint(
            "treatment_id", "inventory_item_id", name="uq_treatment_consumable_pair"
        ),
        Index("idx_treatment_consumables_clinic", "clinic_id"),
        Index("idx_treatment_consumables_treatment", "treatment_id"),
        Index("idx_treatment_consumables_item", "inventory_item_id"),
    )
