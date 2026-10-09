"""Budget module database models."""

from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base, TimestampMixin

if TYPE_CHECKING:
    from app.core.auth.models import Clinic, User
    from app.modules.catalog.models import TreatmentCatalogItem, VatType
    from app.modules.odontogram.models import Treatment
    from app.modules.patients.models import Patient


class Budget(Base, TimestampMixin):
    """Main budget entity for dental treatment quotes.

    Supports versioning, partial acceptance, and integration with
    catalog, odontogram, and future billing modules.
    """

    __tablename__ = "budgets"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    clinic_id: Mapped[UUID] = mapped_column(ForeignKey("clinics.id"), index=True)
    patient_id: Mapped[UUID] = mapped_column(ForeignKey("patients.id"), index=True)

    # Identification
    budget_number: Mapped[str] = mapped_column(String(50))  # e.g., "PRES-2024-0001"
    version: Mapped[int] = mapped_column(Integer, default=1)
    parent_budget_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("budgets.id"), index=True, default=None
    )  # For version chain

    # Status workflow (simplified)
    status: Mapped[str] = mapped_column(
        String(30), default="draft"
    )  # draft, accepted, completed, rejected, expired, cancelled

    # Validity period
    valid_from: Mapped[date] = mapped_column(Date)
    valid_until: Mapped[date | None] = mapped_column(Date, default=None)

    # Assignments
    created_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    assigned_professional_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id"), default=None
    )

    # Global discount
    global_discount_type: Mapped[str | None] = mapped_column(
        String(20), default=None
    )  # percentage, absolute
    global_discount_value: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), default=None)

    # Totals (calculated)
    subtotal: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), default=Decimal("0.00")
    )  # Sum of line totals before global discount
    total_discount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), default=Decimal("0.00")
    )  # Total discounts (line + global)
    total_tax: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"))  # Total VAT
    total: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"))  # Final amount

    # Notes
    internal_notes: Mapped[str | None] = mapped_column(Text, default=None)
    patient_notes: Mapped[str | None] = mapped_column(Text, default=None)

    # Future integrations
    insurance_estimate: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2), default=None
    )  # Reserved for insurance module

    # Acceptance / rejection metadata --------------------------------------
    # ``remote_link`` (patient via public link) | ``in_clinic`` (reception
    # captured the acceptance with optional tablet signature) | ``manual``
    # (legacy or pre-public-link records).
    accepted_via: Mapped[str | None] = mapped_column(String(20), default=None)
    # When the patient rejects from the public link the rejection_reason
    # is one of the closed-list keys (price/time/second_opinion/other) and
    # rejection_note carries the optional free-text comment.
    rejection_reason: Mapped[str | None] = mapped_column(String(50), default=None)
    rejection_note: Mapped[str | None] = mapped_column(Text, default=None)

    # Public link metadata (see ADR 0006) ---------------------------------
    # ``public_token`` is the UUID embedded in the patient-facing link.
    # Generated when the budget is created; never recycled. A new token is
    # minted on resend (clone to v+1).
    public_token: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), default=uuid4, unique=True, index=True
    )
    # First time the public link was opened (for "viewed but not
    # responded" inbox markers). Idempotent.
    viewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    # Last automatic reminder dispatched (7d / 14d milestones).
    last_reminder_sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    # Auth method resolved at send-time. ``phone_last4`` (default when the
    # patient record has phone digits) | ``dob`` (fallback when phone is
    # missing) | ``manual_code`` (last resort: reception sets a code,
    # communicated verbally). ``none`` only for clinics that opt-in via
    # ``clinic.settings.budget_public_auth_disabled``.
    public_auth_method: Mapped[str] = mapped_column(String(20), default="phone_last4")
    # Hashed code (bcrypt/argon2) for ``public_auth_method=manual_code``.
    # Nullable for the other methods (verification reads from Patient).
    public_auth_secret_hash: Mapped[str | None] = mapped_column(String(255), default=None)
    # Set when the budget exceeds the lockout threshold (10 failed
    # verification attempts). Token becomes inert until reception
    # reissues. See ``BudgetAccessLog``.
    public_locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)

    # Plan snapshots ------------------------------------------------------
    # Read-only denormalized fields populated when the budget is created
    # from a treatment plan. Let endpoints that live in the budget module
    # render plan context without importing ``treatment_plan`` models.
    # Real-time plan state lives in the treatment_plan module — query
    # that module for live status. See ADR 0003.
    plan_number_snapshot: Mapped[str | None] = mapped_column(String(50), default=None)
    plan_status_snapshot: Mapped[str | None] = mapped_column(String(20), default=None)

    # Soft delete
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)

    # Relationships
    clinic: Mapped["Clinic"] = relationship(foreign_keys=[clinic_id])
    patient: Mapped["Patient"] = relationship()
    creator: Mapped["User"] = relationship(foreign_keys=[created_by])
    assigned_professional: Mapped["User | None"] = relationship(
        foreign_keys=[assigned_professional_id]
    )
    parent_budget: Mapped["Budget | None"] = relationship(
        remote_side="Budget.id", foreign_keys=[parent_budget_id]
    )
    items: Mapped[list["BudgetItem"]] = relationship(
        back_populates="budget", cascade="all, delete-orphan", order_by="BudgetItem.display_order"
    )
    signatures: Mapped[list["BudgetSignature"]] = relationship(
        back_populates="budget", cascade="all, delete-orphan"
    )
    history: Mapped[list["BudgetHistory"]] = relationship(
        back_populates="budget",
        cascade="all, delete-orphan",
        order_by="BudgetHistory.changed_at.desc()",
    )

    __table_args__ = (
        UniqueConstraint(
            "clinic_id", "budget_number", "version", name="uq_budget_clinic_number_version"
        ),
        Index("idx_budgets_clinic", "clinic_id"),
        Index("idx_budgets_clinic_patient", "clinic_id", "patient_id"),
        Index("idx_budgets_clinic_status", "clinic_id", "status"),
        Index("idx_budgets_valid_until", "valid_until"),
        Index("idx_budgets_parent", "parent_budget_id"),
    )


class BudgetItem(Base, TimestampMixin):
    """Individual line item in a budget.

    References catalog items with snapshotted prices at time of creation.
    Supports per-item acceptance and treatment tracking.
    """

    __tablename__ = "budget_items"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    clinic_id: Mapped[UUID] = mapped_column(ForeignKey("clinics.id"), index=True)
    budget_id: Mapped[UUID] = mapped_column(
        ForeignKey("budgets.id", ondelete="CASCADE"), index=True
    )

    # Catalog reference
    catalog_item_id: Mapped[UUID] = mapped_column(
        ForeignKey("treatment_catalog_items.id"), index=True
    )

    # Snapshotted pricing (frozen at time of creation)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    quantity: Mapped[int] = mapped_column(Integer, default=1)

    # Line discount
    discount_type: Mapped[str | None] = mapped_column(
        String(20), default=None
    )  # percentage, absolute
    discount_value: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), default=None)

    # VAT (snapshotted)
    vat_type_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("vat_types.id"), index=True, default=None
    )
    vat_rate: Mapped[float] = mapped_column(Float, default=0.0)

    # Calculated line totals
    line_subtotal: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), default=Decimal("0.00")
    )  # unit_price * quantity
    line_discount: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), default=Decimal("0.00")
    )  # Applied discount
    line_tax: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.00"))  # VAT amount
    line_total: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), default=Decimal("0.00")
    )  # Final line amount

    # Dental specifics
    tooth_number: Mapped[int | None] = mapped_column(Integer, default=None)  # FDI notation
    surfaces: Mapped[list | None] = mapped_column(JSONB, default=None)  # ["M", "O", "D"]

    # Odontogram integration - link to a Treatment (header + teeth).
    treatment_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("treatments.id"), index=True, default=None
    )

    # Billing tracking (for partial invoicing)
    invoiced_quantity: Mapped[int] = mapped_column(Integer, default=0)

    # Display
    display_order: Mapped[int] = mapped_column(Integer, default=0)
    notes: Mapped[str | None] = mapped_column(Text, default=None)

    # Relationships
    clinic: Mapped["Clinic"] = relationship()
    budget: Mapped["Budget"] = relationship(back_populates="items")
    catalog_item: Mapped["TreatmentCatalogItem"] = relationship()
    vat_type: Mapped["VatType | None"] = relationship()
    treatment: Mapped["Treatment | None"] = relationship()

    __table_args__ = (
        Index("idx_budget_items_budget", "budget_id"),
        Index("idx_budget_items_catalog", "catalog_item_id"),
        Index("idx_budget_items_tooth", "budget_id", "tooth_number"),
        Index("idx_budget_items_treatment", "treatment_id"),
    )


class BudgetSignature(Base):
    """Digital signature record for budget acceptance.

    Stores signature data for audit trail and legal compliance.
    MVP uses click-to-accept; extensible for external providers.
    """

    __tablename__ = "budget_signatures"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    clinic_id: Mapped[UUID] = mapped_column(ForeignKey("clinics.id"), index=True)
    budget_id: Mapped[UUID] = mapped_column(
        ForeignKey("budgets.id", ondelete="CASCADE"), index=True
    )

    # Signature type
    signature_type: Mapped[str] = mapped_column(String(30))  # full_acceptance, rejection

    # Signed items (kept for historical records, all items now signed together)
    signed_items: Mapped[list | None] = mapped_column(JSONB, default=None)  # List of item IDs

    # Signer information
    signed_by_name: Mapped[str] = mapped_column(String(200))
    signed_by_email: Mapped[str | None] = mapped_column(String(255), default=None)
    relationship_to_patient: Mapped[str] = mapped_column(
        String(30)
    )  # patient, guardian, representative

    # Signature method
    signature_method: Mapped[str] = mapped_column(
        String(30)
    )  # click_accept, drawn, external_provider
    signature_data: Mapped[dict | None] = mapped_column(JSONB, default=None)  # Method-specific data

    # Audit information
    ip_address: Mapped[str | None] = mapped_column(String(45), default=None)  # IPv4/IPv6
    user_agent: Mapped[str | None] = mapped_column(Text, default=None)
    signed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    # External provider integration (future)
    external_signature_id: Mapped[str | None] = mapped_column(String(255), default=None)
    external_provider: Mapped[str | None] = mapped_column(String(50), default=None)

    # Document integrity
    document_hash: Mapped[str | None] = mapped_column(String(64), default=None)  # SHA-256

    # Timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now()
    )

    # Relationships
    clinic: Mapped["Clinic"] = relationship()
    budget: Mapped["Budget"] = relationship(back_populates="signatures")

    __table_args__ = (
        Index("idx_budget_signatures_budget", "budget_id"),
        Index("idx_budget_signatures_clinic", "clinic_id"),
    )


class BudgetHistory(Base):
    """Audit log for budget changes.

    Records all changes to budgets for traceability and compliance.
    """

    __tablename__ = "budget_history"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    clinic_id: Mapped[UUID] = mapped_column(ForeignKey("clinics.id"), index=True)
    budget_id: Mapped[UUID] = mapped_column(
        ForeignKey("budgets.id", ondelete="CASCADE"), index=True
    )

    # Action performed
    action: Mapped[str] = mapped_column(
        String(30)
    )  # created, updated, status_changed, item_added, item_removed, signed, sent, duplicated

    # Actor
    changed_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    # State snapshots
    previous_state: Mapped[dict | None] = mapped_column(JSONB, default=None)
    new_state: Mapped[dict | None] = mapped_column(JSONB, default=None)

    # Additional context
    notes: Mapped[str | None] = mapped_column(Text, default=None)

    # Relationships
    clinic: Mapped["Clinic"] = relationship()
    budget: Mapped["Budget"] = relationship(back_populates="history")
    user: Mapped["User"] = relationship()

    __table_args__ = (
        Index("idx_budget_history_budget", "budget_id"),
        Index("idx_budget_history_clinic", "clinic_id"),
        Index("idx_budget_history_changed_at", "changed_at"),
    )


class BudgetAccessLog(Base):
    """Audit row per public-link access event.

    Captures successful and failed patient-link verification attempts and
    follow-on public actions (see ADR 0006). Failed verification rows power
    the lockout policy:

    - 5 failures in 15 minutes per token → 429 (transient).
    - 10 retained failures against the same budget, from any IPs →
      ``Budget.public_locked_at`` set → token stops verifying (the lock
      is deliberately budget-wide); reception clears it via
      ``unlock-public``, which also drops the failed-attempt rows (or
      reissues when the link itself is burned).

    A daily cron purges rows older than 90 days (retention policy).
    Staff administrative actions belong in ``BudgetHistory``, not here.
    """

    __tablename__ = "budget_access_logs"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    budget_id: Mapped[UUID] = mapped_column(
        ForeignKey("budgets.id", ondelete="CASCADE"), index=True
    )
    attempted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now()
    )
    # SHA-256 of the requester IP (privacy-preserving — we don't store
    # the raw IP). It preserves patient-request correlation for audit.
    # The current lockout counters intentionally key on budget and
    # outcome, not this hash.
    ip_hash: Mapped[str] = mapped_column(String(64))
    success: Mapped[bool] = mapped_column(Boolean)
    method_attempted: Mapped[str] = mapped_column(String(20))

    __table_args__ = (
        Index("idx_budget_access_logs_budget_attempted", "budget_id", "attempted_at"),
    )
