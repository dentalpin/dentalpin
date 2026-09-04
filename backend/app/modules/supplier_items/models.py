"""SupplierItem model - the link between a supplier and an inventory item.

An inventory item can be sourced from several suppliers ("multiple vendors");
each link carries the supplier's SKU for that item and the unit price quoted.
The (supplier_id, inventory_item_id) pair is unique, so a supplier can only
price a given item once - adjust the price, don't create a second row.

Soft-delete via ``is_active``: removing a link only flips the flag so
historical purchase-order references remain stable (L7). ``list``/``get``
filter active rows; ``delete`` deactivates.
"""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base, TimestampMixin


class SupplierItem(Base, TimestampMixin):
    """A (supplier, inventory_item) sourcing link with SKU and price."""

    __tablename__ = "supplier_items"
    __table_args__ = (
        UniqueConstraint(
            "supplier_id", "inventory_item_id", name="uq_supplier_items_supplier_item"
        ),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    clinic_id: Mapped[UUID] = mapped_column(ForeignKey("clinics.id"), index=True)

    supplier_id: Mapped[UUID] = mapped_column(ForeignKey("suppliers.id"), index=True)
    inventory_item_id: Mapped[UUID] = mapped_column(ForeignKey("inventory_items.id"), index=True)

    # The supplier's own code for this item (their catalog SKU).
    supplier_sku: Mapped[str | None] = mapped_column(String(100))
    # Unit price this supplier quotes for the item. Matches inventory's
    # unit_cost precision. Nullable - a link can exist before pricing is set.
    price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))

    # Soft delete - a removed link keeps the row for historical references.
    is_active: Mapped[bool] = mapped_column(default=True, server_default="true")
