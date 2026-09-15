"""treasury — cash/bank accounts, transfers, and manual corrections.

Where the money sits (expenses tracks where it went). Balances are
transfer-derived: opening balance plus the signed entry ledger. payment
and expense auto-posting is explicitly Later — wiring money code across
modules needs its own grill (see CLAUDE.md).
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base, TimestampMixin


class TreasuryAccount(Base, TimestampMixin):
    """One cash drawer or bank account of a clinic."""

    __tablename__ = "treasury_accounts"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    clinic_id: Mapped[UUID] = mapped_column(ForeignKey("clinics.id"), index=True)

    name: Mapped[str] = mapped_column(String(60))
    # cash | bank
    kind: Mapped[str] = mapped_column(String(8), default="cash")
    opening_balance: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))
    is_active: Mapped[bool] = mapped_column(default=True)

    __table_args__ = (
        UniqueConstraint("clinic_id", "name", name="uq_treasury_accounts_clinic_name"),
    )


class TreasuryEntry(Base, TimestampMixin):
    """One signed movement on an account. Append-only (no update route).

    ``kind``: transfer_out | transfer_in | correction | opening.
    Transfer legs share a ``group_id`` so the pair is auditable as one
    operation. Amounts are always positive; the sign lives in ``kind``.
    """

    __tablename__ = "treasury_entries"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    clinic_id: Mapped[UUID] = mapped_column(ForeignKey("clinics.id"), index=True)
    account_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("treasury_accounts.id", ondelete="CASCADE"),
        index=True,
    )
    group_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), index=True)
    kind: Mapped[str] = mapped_column(String(16))
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    memo: Mapped[str | None] = mapped_column(Text, default=None)
