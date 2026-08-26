"""treatment_consumables — junction: catalog treatment → inventory items.

Pure mapping with a quantity per link (e.g. root canal → 2 anesthetic
vials). **No stock deduction here** — that lands in the inventory core
upgrade (#226). Reads both dependency modules to validate links and to
resolve display names (ADR 0002); writes only its own table.
"""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base, TimestampMixin


class TreatmentConsumable(Base, TimestampMixin):
    """One link: ``inventory_item`` is consumed by ``catalog_item``.

    Uniqueness of the (clinic, treatment, item) triple is enforced at
    the DB level so the concurrent-create race is closed in SQL (the
    inventory #153 lesson); duplicates via the API get a 409.
    """

    __tablename__ = "treatment_consumables"
    __table_args__ = (
        UniqueConstraint(
            "clinic_id",
            "catalog_item_id",
            "inventory_item_id",
            name="uq_treatment_consumables_link",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    clinic_id: Mapped[UUID] = mapped_column(ForeignKey("clinics.id"), index=True)

    catalog_item_id: Mapped[UUID] = mapped_column(
        ForeignKey("treatment_catalog_items.id"), index=True
    )
    inventory_item_id: Mapped[UUID] = mapped_column(ForeignKey("inventory_items.id"), index=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("1"))
    # Optional free-text note, e.g. "per session" / "only if surgery".
    note: Mapped[str | None] = mapped_column(String(200))
