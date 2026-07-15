"""Billing module service layer - business logic."""

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import and_, desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from app.core.list_query import parse_sort
from app.modules.payments.models import Payment as PaymentModel
from app.modules.payments.models import Refund as RefundModel

from .models import (
    Invoice,
    InvoiceHistory,
    InvoiceItem,
    InvoicePayment,
    InvoiceSeries,
    InvoiceSeriesHistory,
)

# Public sort field → SQL column. balance_due is computed (not stored),
# so it's not in this list; the frontend handles balance ordering
# client-side over the current page when needed.
_INVOICE_SORT_ALLOW = {
    "issue_date": Invoice.issue_date,
    "due_date": Invoice.due_date,
    "total": Invoice.total,
    "created_at": Invoice.created_at,
    "invoice_number": Invoice.invoice_number,
}
_INVOICE_SORT_DEFAULT = "created_at:desc"

# --- Invoice ↔ Payment computed summary -----------------------------------


async def compute_paid_summary(
    db: AsyncSession, clinic_id: UUID, invoice_id: UUID
) -> tuple[Decimal, Decimal]:
    """Return ``(total_paid, balance_due)`` for an invoice.

    ``total_paid`` is the sum of ``InvoicePayment.amount`` on this
    invoice minus the proportional share of any refunds on the linked
    payments. The proportional share is
    ``refund.amount * imputed_amount / payment.amount`` summed across
    refunds and invoice-payment links.
    """
    # Sum of imputed amounts per linked payment for this invoice.
    rows = await db.execute(
        select(InvoicePayment.payment_id, func.sum(InvoicePayment.amount))
        .where(
            InvoicePayment.clinic_id == clinic_id,
            InvoicePayment.invoice_id == invoice_id,
        )
        .group_by(InvoicePayment.payment_id)
    )
    imputed_per_payment: dict[UUID, Decimal] = {row[0]: row[1] for row in rows.all()}

    if not imputed_per_payment:
        # Need the invoice.total to compute balance_due.
        total_row = await db.execute(
            select(Invoice.total).where(Invoice.id == invoice_id, Invoice.clinic_id == clinic_id)
        )
        total = total_row.scalar_one_or_none() or Decimal("0.00")
        return Decimal("0.00"), total

    payment_ids = list(imputed_per_payment.keys())

    payment_rows = await db.execute(
        select(PaymentModel.id, PaymentModel.amount).where(PaymentModel.id.in_(payment_ids))
    )
    payment_amount: dict[UUID, Decimal] = {row[0]: row[1] for row in payment_rows.all()}

    refund_rows = await db.execute(
        select(RefundModel.payment_id, func.coalesce(func.sum(RefundModel.amount), Decimal("0")))
        .where(RefundModel.payment_id.in_(payment_ids))
        .group_by(RefundModel.payment_id)
    )
    refunded_per_payment: dict[UUID, Decimal] = {row[0]: row[1] for row in refund_rows.all()}

    net_paid = Decimal("0.00")
    for pid, imputed in imputed_per_payment.items():
        full_amount = payment_amount.get(pid, imputed)
        refunded = refunded_per_payment.get(pid, Decimal("0"))
        # Proportional share of refunds affecting this invoice link.
        if full_amount > 0:
            adjustment = refunded * (imputed / full_amount)
        else:  # pragma: no cover - defensive
            adjustment = Decimal("0")
        net_paid += imputed - adjustment

    total_row = await db.execute(
        select(Invoice.total).where(Invoice.id == invoice_id, Invoice.clinic_id == clinic_id)
    )
    invoice_total = total_row.scalar_one_or_none() or Decimal("0.00")
    return net_paid, invoice_total - net_paid


class InvoiceNumberService:
    """Service for generating invoice numbers."""

    @staticmethod
    async def generate_number(
        db: AsyncSession,
        clinic_id: UUID,
        series_id: UUID,
    ) -> tuple[str, int]:
        """Generate the next invoice number for a series.

        Handles yearly reset if configured.

        Args:
            db: Database session
            clinic_id: Clinic ID
            series_id: Series ID

        Returns:
            Tuple of (invoice_number, sequential_number)

        Example:
            "FAC-2024-0001", 1
        """
        # Get series with lock for update
        result = await db.execute(
            select(InvoiceSeries)
            .where(
                InvoiceSeries.id == series_id,
                InvoiceSeries.clinic_id == clinic_id,
            )
            .with_for_update()
        )
        series = result.scalar_one_or_none()

        if not series:
            raise ValueError(f"Series {series_id} not found")

        if not series.is_active:
            raise ValueError(f"Series {series.prefix} is not active")

        current_year = date.today().year

        # Check for yearly reset
        if series.reset_yearly and series.last_reset_year != current_year:
            series.current_number = 0
            series.last_reset_year = current_year

        # Increment number
        series.current_number += 1
        sequential_number = series.current_number

        # Format invoice number
        invoice_number = f"{series.prefix}-{current_year}-{sequential_number:04d}"

        await db.flush()

        return invoice_number, sequential_number


class InvoiceSeriesService:
    """Service for invoice series management."""

    @staticmethod
    async def list_series(
        db: AsyncSession,
        clinic_id: UUID,
        series_type: str | None = None,
        active_only: bool = True,
    ) -> list[InvoiceSeries]:
        """List invoice series for a clinic."""
        query = select(InvoiceSeries).where(InvoiceSeries.clinic_id == clinic_id)

        if series_type:
            query = query.where(InvoiceSeries.series_type == series_type)

        if active_only:
            query = query.where(InvoiceSeries.is_active.is_(True))

        query = query.order_by(InvoiceSeries.series_type, InvoiceSeries.prefix)

        result = await db.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def get_default_series(
        db: AsyncSession,
        clinic_id: UUID,
        series_type: str,
    ) -> InvoiceSeries | None:
        """Get default series for a type."""
        result = await db.execute(
            select(InvoiceSeries).where(
                InvoiceSeries.clinic_id == clinic_id,
                InvoiceSeries.series_type == series_type,
                InvoiceSeries.is_default.is_(True),
                InvoiceSeries.is_active.is_(True),
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def create_series(
        db: AsyncSession,
        clinic_id: UUID,
        data: dict,
    ) -> InvoiceSeries:
        """Create a new invoice series."""
        # If this is default, unset other defaults
        if data.get("is_default"):
            await db.execute(
                select(InvoiceSeries)
                .where(
                    InvoiceSeries.clinic_id == clinic_id,
                    InvoiceSeries.series_type == data["series_type"],
                    InvoiceSeries.is_default.is_(True),
                )
                .with_for_update()
            )
            # SQLAlchemy will handle the update when we flush

        series = InvoiceSeries(
            clinic_id=clinic_id,
            prefix=data["prefix"],
            series_type=data["series_type"],
            description=data.get("description"),
            reset_yearly=data.get("reset_yearly", True),
            is_default=data.get("is_default", False),
            last_reset_year=date.today().year,
        )
        db.add(series)
        await db.flush()

        return series

    @staticmethod
    async def update_series(
        db: AsyncSession,
        series: InvoiceSeries,
        data: dict,
        changed_by: UUID | None = None,
    ) -> InvoiceSeries:
        """Update an invoice series."""
        previous_state = {
            "prefix": series.prefix,
            "description": series.description,
            "reset_yearly": series.reset_yearly,
            "is_default": series.is_default,
            "is_active": series.is_active,
        }

        # If setting as default, unset others
        if data.get("is_default") and not series.is_default:
            result = await db.execute(
                select(InvoiceSeries).where(
                    InvoiceSeries.clinic_id == series.clinic_id,
                    InvoiceSeries.series_type == series.series_type,
                    InvoiceSeries.is_default.is_(True),
                    InvoiceSeries.id != series.id,
                )
            )
            for other_series in result.scalars().all():
                other_series.is_default = False

        if "prefix" in data and data["prefix"] is not None:
            series.prefix = data["prefix"]
        if "description" in data:
            series.description = data["description"]
        if "reset_yearly" in data:
            series.reset_yearly = data["reset_yearly"]
        if "is_default" in data:
            series.is_default = data["is_default"]
        if "is_active" in data:
            series.is_active = data["is_active"]

        await db.flush()

        # Log change if changed_by provided
        if changed_by:
            new_state = {
                "prefix": series.prefix,
                "description": series.description,
                "reset_yearly": series.reset_yearly,
                "is_default": series.is_default,
                "is_active": series.is_active,
            }
            await InvoiceSeriesHistoryService.add_entry(
                db,
                clinic_id=series.clinic_id,
                series_id=series.id,
                action="updated",
                changed_by=changed_by,
                previous_state=previous_state,
                new_state=new_state,
            )

        return series

    @staticmethod
    async def reset_series_counter(
        db: AsyncSession,
        series: InvoiceSeries,
        new_number: int,
        changed_by: UUID,
    ) -> InvoiceSeries:
        """Reset series counter to a new number.

        Validates that new_number > max(sequential_number) for invoices in this series.
        """
        # Find max sequential_number for invoices in this series
        max_result = await db.execute(
            select(func.max(Invoice.sequential_number)).where(
                Invoice.series_id == series.id,
                Invoice.clinic_id == series.clinic_id,
            )
        )
        max_sequential = max_result.scalar() or 0

        if new_number <= max_sequential:
            raise ValueError(
                f"New number must be greater than {max_sequential} (highest existing invoice number)"
            )

        previous_number = series.current_number
        series.current_number = new_number

        await db.flush()

        # Log the reset
        await InvoiceSeriesHistoryService.add_entry(
            db,
            clinic_id=series.clinic_id,
            series_id=series.id,
            action="reset",
            changed_by=changed_by,
            previous_state={"current_number": previous_number},
            new_state={"current_number": new_number},
            notes=f"Counter reset from {previous_number} to {new_number}",
        )

        return series


class InvoiceSeriesHistoryService:
    """Service for invoice series audit log."""

    @staticmethod
    async def add_entry(
        db: AsyncSession,
        clinic_id: UUID,
        series_id: UUID,
        action: str,
        changed_by: UUID,
        previous_state: dict | None = None,
        new_state: dict | None = None,
        notes: str | None = None,
    ) -> InvoiceSeriesHistory:
        """Add a history entry for a series change."""
        entry = InvoiceSeriesHistory(
            clinic_id=clinic_id,
            series_id=series_id,
            action=action,
            changed_by=changed_by,
            changed_at=datetime.now(UTC),
            previous_state=previous_state,
            new_state=new_state,
            notes=notes,
        )
        db.add(entry)
        await db.flush()
        return entry

    @staticmethod
    async def list_history(
        db: AsyncSession,
        clinic_id: UUID,
        series_id: UUID,
    ) -> list[InvoiceSeriesHistory]:
        """List history entries for a series."""
        result = await db.execute(
            select(InvoiceSeriesHistory)
            .where(
                InvoiceSeriesHistory.clinic_id == clinic_id,
                InvoiceSeriesHistory.series_id == series_id,
            )
            .options(joinedload(InvoiceSeriesHistory.user))
            .order_by(desc(InvoiceSeriesHistory.changed_at))
        )
        return list(result.scalars().all())


class InvoiceHistoryService:
    """Service for invoice audit log."""

    @staticmethod
    async def add_entry(
        db: AsyncSession,
        clinic_id: UUID,
        invoice_id: UUID,
        action: str,
        changed_by: UUID,
        previous_state: dict | None = None,
        new_state: dict | None = None,
        notes: str | None = None,
    ) -> InvoiceHistory:
        """Add a history entry for an invoice."""
        entry = InvoiceHistory(
            clinic_id=clinic_id,
            invoice_id=invoice_id,
            action=action,
            changed_by=changed_by,
            changed_at=datetime.now(UTC),
            previous_state=previous_state,
            new_state=new_state,
            notes=notes,
        )
        db.add(entry)
        await db.flush()
        return entry

    @staticmethod
    async def list_history(
        db: AsyncSession,
        clinic_id: UUID,
        invoice_id: UUID,
    ) -> list[InvoiceHistory]:
        """List history entries for an invoice."""
        result = await db.execute(
            select(InvoiceHistory)
            .where(
                InvoiceHistory.clinic_id == clinic_id,
                InvoiceHistory.invoice_id == invoice_id,
            )
            .options(joinedload(InvoiceHistory.user))
            .order_by(desc(InvoiceHistory.changed_at))
        )
        return list(result.scalars().all())


class InvoiceItemService:
    """Service for invoice item operations."""

    @staticmethod
    async def create_item(
        db: AsyncSession,
        clinic_id: UUID,
        invoice: Invoice,
        data: dict,
    ) -> InvoiceItem:
        """Create an invoice item."""
        # Get VAT rate from VAT type if provided
        vat_rate = 0.0
        if data.get("vat_type_id"):
            from app.modules.catalog.models import VatType

            result = await db.execute(
                select(VatType).where(
                    VatType.id == data["vat_type_id"],
                    VatType.clinic_id == clinic_id,
                )
            )
            vat_type = result.scalar_one_or_none()
            if vat_type:
                vat_rate = vat_type.rate

        item = InvoiceItem(
            clinic_id=clinic_id,
            invoice_id=invoice.id,
            catalog_item_id=data.get("catalog_item_id"),
            description=data["description"],
            internal_code=data.get("internal_code"),
            unit_price=Decimal(str(data["unit_price"])),
            quantity=data.get("quantity", 1),
            discount_type=data.get("discount_type"),
            discount_value=Decimal(str(data["discount_value"]))
            if data.get("discount_value")
            else None,
            vat_type_id=data.get("vat_type_id"),
            vat_rate=vat_rate,
            vat_exempt_reason=data.get("vat_exempt_reason"),
            tooth_number=data.get("tooth_number"),
            surfaces=data.get("surfaces"),
            display_order=data.get("display_order", 0),
        )
        db.add(item)

        # Calculate line totals
        await InvoiceService.calculate_item_totals(item)

        await db.flush()

        # Recalculate invoice totals
        await InvoiceService.recalculate_totals(db, invoice)

        return item

    @staticmethod
    async def update_item(
        db: AsyncSession,
        clinic_id: UUID,
        item: InvoiceItem,
        invoice: Invoice,
        data: dict,
    ) -> InvoiceItem:
        """Update an invoice item."""
        if "description" in data and data["description"] is not None:
            item.description = data["description"]
        if "unit_price" in data and data["unit_price"] is not None:
            item.unit_price = Decimal(str(data["unit_price"]))
        if "quantity" in data and data["quantity"] is not None:
            item.quantity = data["quantity"]
        if "discount_type" in data:
            item.discount_type = data["discount_type"]
        if "discount_value" in data:
            item.discount_value = (
                Decimal(str(data["discount_value"])) if data["discount_value"] else None
            )
        if "vat_type_id" in data:
            item.vat_type_id = data["vat_type_id"]
            # Update VAT rate
            if data["vat_type_id"]:
                from app.modules.catalog.models import VatType

                result = await db.execute(
                    select(VatType).where(
                        VatType.id == data["vat_type_id"],
                        VatType.clinic_id == clinic_id,
                    )
                )
                vat_type = result.scalar_one_or_none()
                if vat_type:
                    item.vat_rate = vat_type.rate
            else:
                item.vat_rate = 0.0
        if "vat_exempt_reason" in data:
            item.vat_exempt_reason = data["vat_exempt_reason"]
        if "display_order" in data and data["display_order"] is not None:
            item.display_order = data["display_order"]

        # Recalculate line totals
        await InvoiceService.calculate_item_totals(item)

        await db.flush()

        # Recalculate invoice totals
        await InvoiceService.recalculate_totals(db, invoice)

        return item

    @staticmethod
    async def delete_item(
        db: AsyncSession,
        item: InvoiceItem,
        invoice: Invoice,
    ) -> None:
        """Delete an invoice item."""
        await db.delete(item)
        await db.flush()

        # Recalculate invoice totals
        await InvoiceService.recalculate_totals(db, invoice)


class InvoiceService:
    """Service for invoice operations."""

    @staticmethod
    async def calculate_item_totals(item: InvoiceItem) -> None:
        """Calculate line totals for an item."""
        # Line subtotal = unit_price * quantity
        item.line_subtotal = item.unit_price * item.quantity

        # Calculate discount
        item.line_discount = Decimal("0.00")
        if item.discount_type and item.discount_value:
            if item.discount_type == "percentage":
                item.line_discount = item.line_subtotal * item.discount_value / Decimal("100")
            else:  # absolute
                item.line_discount = item.discount_value

        # Subtotal after discount
        taxable_amount = item.line_subtotal - item.line_discount

        # Calculate tax
        item.line_tax = taxable_amount * Decimal(str(item.vat_rate)) / Decimal("100")

        # Line total
        item.line_total = taxable_amount + item.line_tax

    @staticmethod
    async def recalculate_totals(db: AsyncSession, invoice: Invoice) -> None:
        """Recalculate invoice totals from items."""
        # Reload items to ensure fresh data
        await db.refresh(invoice, ["items"])

        subtotal = Decimal("0.00")
        total_discount = Decimal("0.00")
        total_tax = Decimal("0.00")
        total = Decimal("0.00")

        for item in invoice.items:
            subtotal += item.line_subtotal
            total_discount += item.line_discount
            total_tax += item.line_tax
            total += item.line_total

        invoice.subtotal = subtotal
        invoice.total_discount = total_discount
        invoice.total_tax = total_tax
        invoice.total = total

        await db.flush()

    @staticmethod
    async def list_invoices(
        db: AsyncSession,
        clinic_id: UUID,
        page: int = 1,
        page_size: int = 20,
        patient_id: UUID | None = None,
        status: list[str] | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        due_from: date | None = None,
        due_to: date | None = None,
        overdue: bool | None = None,
        search: str | None = None,
        budget_id: UUID | None = None,
        is_credit_note: bool | None = None,
        compliance_severity: list[str] | None = None,
        *,
        sort: str | None = None,
    ) -> tuple[list[Invoice], int]:
        """List invoices with filtering and pagination."""
        conditions = [
            Invoice.clinic_id == clinic_id,
            Invoice.deleted_at.is_(None),
        ]

        if patient_id:
            conditions.append(Invoice.patient_id == patient_id)

        if status:
            conditions.append(Invoice.status.in_(status))

        if date_from:
            conditions.append(Invoice.issue_date >= date_from)

        if date_to:
            conditions.append(Invoice.issue_date <= date_to)

        if due_from:
            conditions.append(Invoice.due_date >= due_from)

        if due_to:
            conditions.append(Invoice.due_date <= due_to)

        if overdue:
            today = date.today()
            conditions.append(
                and_(
                    Invoice.due_date < today,
                    Invoice.status.in_(["issued", "partial"]),
                )
            )

        if budget_id:
            conditions.append(Invoice.budget_id == budget_id)

        if is_credit_note is not None:
            if is_credit_note:
                conditions.append(Invoice.credit_note_for_id.isnot(None))
            else:
                conditions.append(Invoice.credit_note_for_id.is_(None))

        if compliance_severity:
            # Country-agnostic: matches any country key in the JSONB
            # whose ``severity`` is in the requested list. Compliance
            # modules (verifactu et al.) write ``severity`` themselves
            # — billing knows nothing about the vocabulary beyond the
            # whitelist enforced at the router boundary.
            from sqlalchemy import bindparam, text

            jsonpath = (
                "$.* ? (" + " || ".join([f'@.severity == "{s}"' for s in compliance_severity]) + ")"
            )
            # Whitelist guarantees only [a-z] values, so the inline
            # interpolation above is safe — but assert defensively.
            assert all(s.isalpha() and s.islower() for s in compliance_severity)
            # CAST a jsonpath: asyncpg envía el bindparam como VARCHAR
            # y PostgreSQL no acepta VARCHAR para el segundo argumento.
            conditions.append(
                text(
                    "jsonb_path_exists(invoices.compliance_data, CAST(:jp AS jsonpath))"
                ).bindparams(bindparam("jp", value=jsonpath))
            )

        # The search filter joins ``patients`` to match by patient name —
        # so both the count and the data query share the same join when
        # active. Without search we count the indexed invoices table
        # directly, no join overhead.
        search_join_needed = False
        if search:
            from app.modules.patients.models import Patient

            search_term = f"%{search}%"
            conditions.append(
                or_(
                    Invoice.invoice_number.ilike(search_term),
                    Patient.first_name.ilike(search_term),
                    Patient.last_name.ilike(search_term),
                )
            )
            search_join_needed = True

        count_stmt = select(func.count(Invoice.id))
        if search_join_needed:
            from app.modules.patients.models import Patient

            count_stmt = count_stmt.select_from(Invoice).outerjoin(Patient)
        total = (await db.execute(count_stmt.where(*conditions))).scalar() or 0

        query = (
            select(Invoice)
            .where(*conditions)
            .options(
                joinedload(Invoice.patient),
                joinedload(Invoice.creator),
            )
            .order_by(parse_sort(sort, _INVOICE_SORT_ALLOW, _INVOICE_SORT_DEFAULT))
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        if search_join_needed:
            from app.modules.patients.models import Patient

            query = query.outerjoin(Patient)

        result = await db.execute(query)
        invoices = list(result.scalars().unique().all())

        return invoices, total

    @staticmethod
    async def list_for_export(
        db: AsyncSession,
        clinic_id: UUID,
        date_from: date | None = None,
        date_to: date | None = None,
        statuses: list[str] | None = None,
    ) -> list[Invoice]:
        """Fetch issued invoices for accountant export, items + allocated
        payments eager-loaded.

        Not paginated — an accounting period (month/quarter/year) is
        bounded and fits in memory. Drafts are always excluded (they are
        not fiscal documents). When ``statuses`` is given it further
        narrows the set; otherwise all non-draft invoices are returned.
        """
        conditions = [
            Invoice.clinic_id == clinic_id,
            Invoice.deleted_at.is_(None),
            Invoice.status != "draft",
        ]
        if statuses:
            conditions.append(Invoice.status.in_(statuses))
        if date_from:
            conditions.append(Invoice.issue_date >= date_from)
        if date_to:
            conditions.append(Invoice.issue_date <= date_to)

        query = (
            select(Invoice)
            .where(*conditions)
            .options(
                joinedload(Invoice.patient),
                joinedload(Invoice.series),
                selectinload(Invoice.items),
                selectinload(Invoice.invoice_payments).joinedload(InvoicePayment.payment),
            )
            .order_by(Invoice.issue_date, Invoice.invoice_number)
        )
        result = await db.execute(query)
        return list(result.scalars().unique().all())

    @staticmethod
    async def get_invoice(
        db: AsyncSession,
        clinic_id: UUID,
        invoice_id: UUID,
        include_items: bool = True,
        include_payments: bool = True,
    ) -> Invoice | None:
        """Get an invoice by ID with optional related data."""
        query = select(Invoice).where(
            Invoice.id == invoice_id,
            Invoice.clinic_id == clinic_id,
            Invoice.deleted_at.is_(None),
        )

        options = [
            joinedload(Invoice.patient),
            joinedload(Invoice.creator),
            joinedload(Invoice.issuer),
            joinedload(Invoice.budget),
            joinedload(Invoice.credit_note_for),
            joinedload(Invoice.series),
        ]

        if include_items:
            options.append(selectinload(Invoice.items).joinedload(InvoiceItem.catalog_item))
            options.append(selectinload(Invoice.items).joinedload(InvoiceItem.vat_type))

        if include_payments:
            options.append(
                selectinload(Invoice.invoice_payments).joinedload(InvoicePayment.payment)
            )

        query = query.options(*options)

        result = await db.execute(query)
        return result.scalar_one_or_none()

    @staticmethod
    async def create_invoice(
        db: AsyncSession,
        clinic_id: UUID,
        created_by: UUID,
        patient_id: UUID,
        series_id: UUID | None = None,
        payment_term_days: int = 30,
        due_date: date | None = None,
        notes: dict | None = None,
    ) -> Invoice:
        """Create a new invoice as a draft.

        Invoice number is NOT assigned here - it will be assigned when the
        invoice is issued via InvoiceWorkflowService.issue_invoice().
        This prevents gaps in numbering when drafts are cancelled.

        Billing data is NOT stored for drafts - it comes dynamically from the
        patient. When the invoice is issued, billing data is snapshotted.
        """
        # Verify patient exists
        from app.modules.patients.models import Patient

        result = await db.execute(
            select(Patient).where(
                Patient.id == patient_id,
                Patient.clinic_id == clinic_id,
            )
        )
        patient = result.scalar_one_or_none()
        if not patient:
            raise ValueError("Patient not found")

        # Draft invoices don't store billing data - it comes from patient dynamically
        invoice = Invoice(
            clinic_id=clinic_id,
            patient_id=patient_id,
            invoice_number=None,  # Assigned when issued
            series_id=series_id,  # Can be pre-selected, but number generated on issue
            sequential_number=None,  # Assigned when issued
            status="draft",
            payment_term_days=payment_term_days,
            due_date=due_date,
            billing_name=None,  # Comes from patient for drafts
            billing_tax_id=None,
            billing_address=None,
            billing_email=None,
            internal_notes=notes.get("internal_notes") if notes else None,
            public_notes=notes.get("public_notes") if notes else None,
            created_by=created_by,
        )
        db.add(invoice)
        await db.flush()

        # Add history
        await InvoiceHistoryService.add_entry(
            db,
            clinic_id=clinic_id,
            invoice_id=invoice.id,
            action="created",
            changed_by=created_by,
            new_state={"status": "draft"},
        )

        return invoice

    @staticmethod
    async def update_invoice(
        db: AsyncSession,
        invoice: Invoice,
        updated_by: UUID,
        data: dict,
    ) -> Invoice:
        """Update an invoice (only drafts).

        For drafts, billing data is not stored - it comes from the patient.
        Patient can be changed for draft invoices.
        """
        from .workflow import InvoiceWorkflowService

        if not InvoiceWorkflowService.can_edit(invoice):
            raise ValueError("Can only edit draft invoices")

        previous_state = {}

        # Handle patient change (only for drafts without budget link)
        if "patient_id" in data and data["patient_id"]:
            new_patient_id = data["patient_id"]
            if new_patient_id != invoice.patient_id:
                # Can't change patient if linked to a budget
                if invoice.budget_id:
                    raise ValueError("Cannot change patient for invoice linked to a budget")

                # Verify new patient exists
                from app.modules.patients.models import Patient

                result = await db.execute(
                    select(Patient).where(
                        Patient.id == new_patient_id,
                        Patient.clinic_id == invoice.clinic_id,
                    )
                )
                new_patient = result.scalar_one_or_none()
                if not new_patient:
                    raise ValueError("Patient not found")

                previous_state["patient_id"] = str(invoice.patient_id)
                invoice.patient_id = new_patient_id

        if "payment_term_days" in data and data["payment_term_days"] is not None:
            previous_state["payment_term_days"] = invoice.payment_term_days
            invoice.payment_term_days = data["payment_term_days"]

        if "due_date" in data:
            previous_state["due_date"] = invoice.due_date.isoformat() if invoice.due_date else None
            invoice.due_date = data["due_date"]

        if "internal_notes" in data:
            previous_state["internal_notes"] = invoice.internal_notes
            invoice.internal_notes = data["internal_notes"]

        if "public_notes" in data:
            previous_state["public_notes"] = invoice.public_notes
            invoice.public_notes = data["public_notes"]

        await db.flush()

        # Add history
        if previous_state:
            await InvoiceHistoryService.add_entry(
                db,
                clinic_id=invoice.clinic_id,
                invoice_id=invoice.id,
                action="updated",
                changed_by=updated_by,
                previous_state=previous_state,
                new_state={k: str(getattr(invoice, k)) for k in previous_state.keys()},
            )

        return invoice

    @staticmethod
    async def delete_invoice(
        db: AsyncSession,
        invoice: Invoice,
        deleted_by: UUID,
    ) -> None:
        """Soft delete an invoice (only drafts)."""
        from .workflow import InvoiceWorkflowService

        if not InvoiceWorkflowService.can_edit(invoice):
            raise ValueError("Can only delete draft invoices")

        invoice.deleted_at = datetime.now(UTC)

        await InvoiceHistoryService.add_entry(
            db,
            clinic_id=invoice.clinic_id,
            invoice_id=invoice.id,
            action="deleted",
            changed_by=deleted_by,
        )

        await db.flush()

    @staticmethod
    async def create_from_budget(
        db: AsyncSession,
        clinic_id: UUID,
        created_by: UUID,
        budget_id: UUID,
        items: list[dict],
        payment_term_days: int | None = None,
        due_date: date | None = None,
        notes: dict | None = None,
    ) -> Invoice:
        """Create an invoice from a budget with partial invoicing support.

        Args:
            db: Database session
            clinic_id: Clinic ID
            created_by: User creating the invoice
            budget_id: Budget to invoice from
            items: List of items to invoice:
                   [{"budget_item_id": UUID, "quantity": int | None}, ...]
            payment_term_days: Optional payment term override
            due_date: Optional due date
            notes: Optional notes

        Returns:
            Created invoice (draft, billing data from patient)
        """
        from app.modules.budget.models import Budget, BudgetItem

        # Get budget
        result = await db.execute(
            select(Budget)
            .where(
                Budget.id == budget_id,
                Budget.clinic_id == clinic_id,
                Budget.deleted_at.is_(None),
            )
            .options(selectinload(Budget.items).joinedload(BudgetItem.catalog_item))
        )
        budget = result.scalar_one_or_none()

        if not budget:
            raise ValueError("Budget not found")

        # Validate budget status (must be accepted or completed)
        if budget.status not in ["accepted", "completed"]:
            raise ValueError(f"Cannot invoice budget with status '{budget.status}'")

        # Create invoice (billing data comes from patient dynamically for drafts)
        invoice = await InvoiceService.create_invoice(
            db,
            clinic_id=clinic_id,
            created_by=created_by,
            patient_id=budget.patient_id,
            payment_term_days=payment_term_days or 30,
            due_date=due_date,
            notes=notes,
        )

        # Link to budget
        invoice.budget_id = budget_id

        # Create invoice items from budget items
        budget_items_map = {str(bi.id): bi for bi in budget.items}

        for item_spec in items:
            budget_item_id = str(item_spec["budget_item_id"])
            budget_item = budget_items_map.get(budget_item_id)

            if not budget_item:
                raise ValueError(f"Budget item {budget_item_id} not found")

            # Calculate available quantity
            invoiced_qty = getattr(budget_item, "invoiced_quantity", 0) or 0
            available_qty = budget_item.quantity - invoiced_qty

            if available_qty <= 0:
                raise ValueError(f"Budget item {budget_item_id} is fully invoiced")

            # Determine quantity to invoice
            requested_qty = item_spec.get("quantity")
            if requested_qty is None:
                quantity = available_qty
            else:
                if requested_qty > available_qty:
                    raise ValueError(
                        f"Requested quantity ({requested_qty}) exceeds available ({available_qty})"
                    )
                quantity = requested_qty

            # Get description from catalog item
            description = "Unknown treatment"
            internal_code = None
            if budget_item.catalog_item:
                names = budget_item.catalog_item.names or {}
                description = names.get("es") or names.get("en") or names.get("fr") or description
                internal_code = budget_item.catalog_item.internal_code

            # Create invoice item
            invoice_item = InvoiceItem(
                clinic_id=clinic_id,
                invoice_id=invoice.id,
                budget_item_id=budget_item.id,
                catalog_item_id=budget_item.catalog_item_id,
                description=description,
                internal_code=internal_code,
                unit_price=budget_item.unit_price,
                quantity=quantity,
                discount_type=budget_item.discount_type,
                discount_value=budget_item.discount_value,
                vat_type_id=budget_item.vat_type_id,
                vat_rate=budget_item.vat_rate,
                tooth_number=budget_item.tooth_number,
                surfaces=budget_item.surfaces,
                display_order=budget_item.display_order,
            )
            db.add(invoice_item)

            # Calculate line totals
            await InvoiceService.calculate_item_totals(invoice_item)

            # Update budget item invoiced quantity
            budget_item.invoiced_quantity = invoiced_qty + quantity

        await db.flush()

        # Recalculate invoice totals
        await InvoiceService.recalculate_totals(db, invoice)

        await db.flush()

        return invoice


async def compute_paid_summaries_for_invoices(
    db: AsyncSession, clinic_id: UUID, invoice_ids: list[UUID]
) -> dict[UUID, tuple[Decimal, Decimal]]:
    """Batch version of ``compute_paid_summary`` for list views.

    Returns ``{invoice_id: (total_paid, balance_due)}``. Invoices with
    no ``InvoicePayment`` rows still appear with ``(0, invoice.total)``.
    """
    if not invoice_ids:
        return {}

    # Imputed amounts per (invoice, payment).
    imp_rows = await db.execute(
        select(
            InvoicePayment.invoice_id,
            InvoicePayment.payment_id,
            func.sum(InvoicePayment.amount),
        )
        .where(
            InvoicePayment.clinic_id == clinic_id,
            InvoicePayment.invoice_id.in_(invoice_ids),
        )
        .group_by(InvoicePayment.invoice_id, InvoicePayment.payment_id)
    )

    imputed_by_invoice: dict[UUID, dict[UUID, Decimal]] = {}
    payment_ids: set[UUID] = set()
    for invoice_id, payment_id, amount in imp_rows.all():
        imputed_by_invoice.setdefault(invoice_id, {})[payment_id] = amount
        payment_ids.add(payment_id)

    payment_amount: dict[UUID, Decimal] = {}
    refunded_per_payment: dict[UUID, Decimal] = {}
    if payment_ids:
        pay_rows = await db.execute(
            select(PaymentModel.id, PaymentModel.amount).where(PaymentModel.id.in_(payment_ids))
        )
        payment_amount = {row[0]: row[1] for row in pay_rows.all()}

        ref_rows = await db.execute(
            select(RefundModel.payment_id, func.sum(RefundModel.amount))
            .where(RefundModel.payment_id.in_(payment_ids))
            .group_by(RefundModel.payment_id)
        )
        refunded_per_payment = {row[0]: row[1] or Decimal("0") for row in ref_rows.all()}

    totals_rows = await db.execute(
        select(Invoice.id, Invoice.total).where(Invoice.id.in_(invoice_ids))
    )
    totals: dict[UUID, Decimal] = {row[0]: row[1] for row in totals_rows.all()}

    out: dict[UUID, tuple[Decimal, Decimal]] = {}
    for invoice_id in invoice_ids:
        net_paid = Decimal("0")
        for payment_id, imputed in imputed_by_invoice.get(invoice_id, {}).items():
            full = payment_amount.get(payment_id, imputed)
            refunded = refunded_per_payment.get(payment_id, Decimal("0"))
            adjustment = refunded * (imputed / full) if full > 0 else Decimal("0")
            net_paid += imputed - adjustment
        total = totals.get(invoice_id, Decimal("0"))
        out[invoice_id] = (net_paid, total - net_paid)
    return out


class InvoicePaymentService:
    """Operations on the ``invoice_payments`` link table."""

    @staticmethod
    async def list_for_invoice(
        db: AsyncSession, clinic_id: UUID, invoice_id: UUID
    ) -> list[InvoicePayment]:
        result = await db.execute(
            select(InvoicePayment)
            .where(
                InvoicePayment.clinic_id == clinic_id,
                InvoicePayment.invoice_id == invoice_id,
            )
            .options(joinedload(InvoicePayment.payment))
            .order_by(desc(InvoicePayment.created_at))
        )
        return list(result.scalars().unique().all())
