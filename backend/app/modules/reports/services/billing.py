"""Billing report service."""

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import and_, desc, func, not_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.core.auth.models import User
from app.core.utils.dates import clinic_today_for
from app.modules.billing.models import Invoice, InvoiceItem, InvoicePayment, InvoiceSeries
from app.modules.budget.models import Budget, BudgetItem
from app.modules.catalog.models import VatType


class BillingReportService:
    """Service for billing reports."""

    @staticmethod
    async def top_clients_by_billing(
        db: AsyncSession,
        clinic_id: UUID,
        date_from: date,
        date_to: date,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Top patients by gross invoiced amount in a period.

        **Invoice axis only.** Sums issued invoice totals; never references
        payments. Keep this single-axis so it cannot surface the
        invoiced-vs-collected difference (off-books rule).
        """
        from app.modules.patients.models import Patient

        result = await db.execute(
            select(
                Invoice.patient_id,
                func.concat(Patient.first_name, " ", Patient.last_name).label("patient_name"),
                func.coalesce(func.sum(Invoice.total), Decimal("0")).label("total_invoiced"),
                func.count(Invoice.id).label("invoice_count"),
            )
            .join(Patient, Patient.id == Invoice.patient_id)
            .where(
                Invoice.clinic_id == clinic_id,
                Invoice.status.notin_(["draft", "voided"]),
                Invoice.issue_date >= date_from,
                Invoice.issue_date <= date_to,
                Invoice.deleted_at.is_(None),
            )
            .group_by(Invoice.patient_id, Patient.first_name, Patient.last_name)
            .order_by(desc("total_invoiced"))
            .limit(limit)
        )
        return [
            {
                "patient_id": str(row.patient_id),
                "patient_name": row.patient_name,
                "total_invoiced": float(row.total_invoiced),
                "invoice_count": int(row.invoice_count),
            }
            for row in result.all()
        ]

    @staticmethod
    async def get_patient_summary(
        db: AsyncSession,
        clinic_id: UUID,
        patient_id: UUID,
    ) -> dict[str, Any]:
        """Get billing summary for a specific patient.

        Returns:
            - total_budgeted: Sum of all budgets
            - total_discount: Sum of line + global discounts on those budgets
            - work_in_progress: Sum of accepted budgets not yet fully invoiced
            - work_completed: Sum of accepted budgets fully invoiced
            - total_invoiced: Sum of issued invoices
            - total_paid: Sum of payments
            - balance_pending: total_invoiced - total_paid
        """
        from sqlalchemy import case

        # Budget aggregation. The ``completed`` budget status was removed in
        # 2026-04 (budget/CLAUDE.md): financial closure on the budget axis is
        # "fully invoiced" — every line's derived ``invoiced_quantity`` cache
        # has reached its ``quantity``. ``work_in_progress`` is the
        # complement, so the two tiles partition the accepted total (#242).
        items_state = (
            select(
                BudgetItem.budget_id.label("budget_id"),
                func.bool_and(BudgetItem.invoiced_quantity >= BudgetItem.quantity).label(
                    "fully_invoiced"
                ),
            )
            .join(Budget, Budget.id == BudgetItem.budget_id)
            .where(
                BudgetItem.clinic_id == clinic_id,
                Budget.clinic_id == clinic_id,
                Budget.patient_id == patient_id,
            )
            .group_by(BudgetItem.budget_id)
            .subquery()
        )
        # Budgets with no items have no row in ``items_state`` → not completed.
        fully_invoiced = func.coalesce(items_state.c.fully_invoiced, False)

        budget_result = await db.execute(
            select(
                func.coalesce(func.sum(Budget.total), Decimal("0")).label("total_budgeted"),
                func.coalesce(func.sum(Budget.total_discount), Decimal("0")).label(
                    "total_discount"
                ),
                func.coalesce(
                    func.sum(
                        case(
                            (
                                and_(Budget.status == "accepted", not_(fully_invoiced)),
                                Budget.total,
                            ),
                            else_=0,
                        )
                    ),
                    Decimal("0"),
                ).label("work_in_progress"),
                func.coalesce(
                    func.sum(
                        case(
                            (and_(Budget.status == "accepted", fully_invoiced), Budget.total),
                            else_=0,
                        )
                    ),
                    Decimal("0"),
                ).label("work_completed"),
            )
            .select_from(Budget)
            .outerjoin(items_state, items_state.c.budget_id == Budget.id)
            .where(
                Budget.clinic_id == clinic_id,
                Budget.patient_id == patient_id,
                Budget.deleted_at.is_(None),
            )
        )
        budget_totals = budget_result.one()

        # Invoice aggregation (only issued, partial, paid). ``total_paid``
        # comes from ``invoice_payments`` since the legacy cached column
        # was removed when payments became its own module.
        # Same refund-aware arithmetic as the invoice detail/list views
        # (``compute_paid_summaries_for_invoices``) so this tab never
        # disagrees with the invoice page (issue #178).
        from app.modules.billing.service import compute_paid_summaries_for_invoices

        invoice_rows = await db.execute(
            select(Invoice.id, Invoice.total).where(
                Invoice.clinic_id == clinic_id,
                Invoice.patient_id == patient_id,
                Invoice.status.in_(["issued", "partial", "paid"]),
                Invoice.deleted_at.is_(None),
            )
        )
        invoices = invoice_rows.all()
        total_invoiced = sum((row.total for row in invoices), Decimal("0"))
        paid_by_invoice = await compute_paid_summaries_for_invoices(
            db, clinic_id, [row.id for row in invoices]
        )
        total_paid = sum((paid for paid, _ in paid_by_invoice.values()), Decimal("0"))
        balance_pending = total_invoiced - total_paid

        return {
            "patient_id": patient_id,
            "total_budgeted": budget_totals.total_budgeted,
            "total_discount": budget_totals.total_discount,
            "work_in_progress": budget_totals.work_in_progress,
            "work_completed": budget_totals.work_completed,
            "total_invoiced": total_invoiced,
            "total_paid": total_paid,
            "balance_pending": balance_pending,
        }

    @staticmethod
    async def get_summary(
        db: AsyncSession,
        clinic_id: UUID,
        date_from: date,
        date_to: date,
    ) -> dict[str, Any]:
        """Get billing summary for a period.

        Returns:
            - total_invoiced: Total amount invoiced (issued invoices in period)
            - total_paid: Total payments received in period
            - total_pending: Total balance due (all outstanding invoices)
            - invoice_count: Number of invoices issued in period
            - paid_count: Number of fully paid invoices in period
            - overdue_count: Number of overdue invoices (all time)
            - vat_breakdown: VAT breakdown by rate
        """
        # Get totals for issued invoices in the period. ``total_pending``
        # is the sum of invoice totals minus their imputed payments.
        result = await db.execute(
            select(
                func.count(Invoice.id).label("invoice_count"),
                func.coalesce(func.sum(Invoice.total), Decimal("0")).label("total_invoiced"),
            ).where(
                Invoice.clinic_id == clinic_id,
                Invoice.status.notin_(["draft", "voided"]),
                Invoice.issue_date >= date_from,
                Invoice.issue_date <= date_to,
                Invoice.deleted_at.is_(None),
            )
        )
        totals = result.one()

        from app.modules.billing.service import compute_paid_summaries_for_invoices

        # ``total_pending`` is Σ balance_due across the clinic's outstanding
        # invoices, through the same refund-aware helper the invoice page and
        # the patient tab use. Subtracting a raw Σ ``InvoicePayment.amount``
        # from the invoiced total let a refunded payment keep reducing
        # receivables, so the dashboard reported nothing outstanding on an
        # invoice the invoice page showed as unpaid (#690).
        open_invoice_ids = (
            (
                await db.execute(
                    select(Invoice.id).where(
                        Invoice.clinic_id == clinic_id,
                        Invoice.status.in_(["issued", "partial"]),
                        Invoice.deleted_at.is_(None),
                    )
                )
            )
            .scalars()
            .all()
        )
        paid_by_invoice = await compute_paid_summaries_for_invoices(
            db, clinic_id, list(open_invoice_ids)
        )
        total_pending = sum((balance for _, balance in paid_by_invoice.values()), Decimal("0"))

        # Total paid in period for billed invoices. Computed from the
        # InvoicePayment link table — this represents the fiscal "cobrado
        # via factura" view (legitimate, fiscal-axis report). The
        # patient-centric "total collected" lives in the payments
        # module's own reports.
        result = await db.execute(
            select(
                func.coalesce(func.sum(InvoicePayment.amount), Decimal("0")).label("total_paid"),
            ).where(
                InvoicePayment.clinic_id == clinic_id,
                InvoicePayment.created_at
                >= datetime.combine(date_from, datetime.min.time(), tzinfo=UTC),
                InvoicePayment.created_at
                <= datetime.combine(date_to, datetime.max.time(), tzinfo=UTC),
            )
        )
        payments_totals = result.one()

        # Count paid invoices
        result = await db.execute(
            select(func.count(Invoice.id)).where(
                Invoice.clinic_id == clinic_id,
                Invoice.status == "paid",
                Invoice.issue_date >= date_from,
                Invoice.issue_date <= date_to,
                Invoice.deleted_at.is_(None),
            )
        )
        paid_count = result.scalar() or 0

        # Count overdue invoices. ``status in (issued, partial)`` implies
        # balance > 0 — fully paid invoices transition to ``paid``.
        today = await clinic_today_for(db, clinic_id)
        result = await db.execute(
            select(func.count(Invoice.id)).where(
                Invoice.clinic_id == clinic_id,
                Invoice.status.in_(["issued", "partial"]),
                Invoice.due_date < today,
                Invoice.deleted_at.is_(None),
            )
        )
        overdue_count = result.scalar() or 0

        # Get VAT breakdown
        vat_breakdown = await BillingReportService._get_vat_breakdown(
            db, clinic_id, date_from, date_to
        )

        return {
            "period_start": date_from,
            "period_end": date_to,
            "total_invoiced": totals.total_invoiced,
            "total_paid": payments_totals.total_paid,
            "total_pending": total_pending,
            "invoice_count": totals.invoice_count,
            "paid_count": paid_count,
            "overdue_count": overdue_count,
            "vat_breakdown": vat_breakdown,
        }

    @staticmethod
    async def _get_vat_breakdown(
        db: AsyncSession,
        clinic_id: UUID,
        date_from: date,
        date_to: date,
    ) -> list[dict[str, Any]]:
        """Get VAT breakdown for a period (internal helper)."""
        result = await db.execute(
            select(
                InvoiceItem.vat_type_id,
                InvoiceItem.vat_rate,
                func.coalesce(
                    func.sum(InvoiceItem.line_subtotal - InvoiceItem.line_discount),
                    Decimal("0"),
                ).label("base_amount"),
                func.coalesce(func.sum(InvoiceItem.line_tax), Decimal("0")).label("tax_amount"),
            )
            .join(Invoice, InvoiceItem.invoice_id == Invoice.id)
            .where(
                Invoice.clinic_id == clinic_id,
                Invoice.status.notin_(["draft", "voided"]),
                Invoice.issue_date >= date_from,
                Invoice.issue_date <= date_to,
                Invoice.deleted_at.is_(None),
            )
            .group_by(InvoiceItem.vat_type_id, InvoiceItem.vat_rate)
        )
        vat_rows = result.all()

        # Get VAT type names
        vat_type_ids = [r.vat_type_id for r in vat_rows if r.vat_type_id]
        vat_names: dict[UUID, str] = {}
        if vat_type_ids:
            result = await db.execute(select(VatType).where(VatType.id.in_(vat_type_ids)))
            for vt in result.scalars():
                vat_names[vt.id] = vt.names.get("es", f"IVA {vt.rate}%")

        return [
            {
                "vat_type_id": row.vat_type_id,
                "vat_rate": row.vat_rate,
                "vat_name": vat_names.get(row.vat_type_id, f"IVA {row.vat_rate}%"),
                "base_amount": row.base_amount,
                "tax_amount": row.tax_amount,
                "total_amount": row.base_amount + row.tax_amount,
            }
            for row in vat_rows
        ]

    @staticmethod
    async def get_overdue_invoices(
        db: AsyncSession,
        clinic_id: UUID,
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        """Get list of overdue invoices, oldest due-date first.

        ``limit`` caps the result so a clinic with years of unpaid
        balances does not blow up the response. Default is enough to
        cover the action board; callers that need the full list should
        paginate (no usage today, surface added when needed).
        """
        today = await clinic_today_for(db, clinic_id)

        result = await db.execute(
            select(Invoice)
            .where(
                Invoice.clinic_id == clinic_id,
                Invoice.status.in_(["issued", "partial"]),
                Invoice.due_date < today,
                Invoice.deleted_at.is_(None),
            )
            .options(joinedload(Invoice.patient))
            .order_by(Invoice.due_date)
            .limit(limit)
        )

        invoices = result.scalars().all()

        # Refund-aware, like the invoice page: a raw Σ ``InvoicePayment.amount``
        # left a refunded invoice sitting in the overdue list with
        # ``balance_due`` 0, i.e. reading as nothing to chase (#690).
        from app.modules.billing.service import compute_paid_summaries_for_invoices

        paid_by_inv = await compute_paid_summaries_for_invoices(
            db, clinic_id, [i.id for i in invoices]
        )

        return [
            {
                "id": inv.id,
                "invoice_number": inv.invoice_number,
                "patient_name": (
                    f"{inv.patient.last_name}, {inv.patient.first_name}" if inv.patient else "-"
                ),
                "issue_date": inv.issue_date,
                "due_date": inv.due_date,
                "days_overdue": (today - inv.due_date).days,
                "balance_due": paid_by_inv.get(inv.id, (Decimal("0"), inv.total))[1],
            }
            for inv in invoices
        ]

    @staticmethod
    async def get_by_payment_method(
        db: AsyncSession,
        clinic_id: UUID,
        date_from: date,
        date_to: date,
    ) -> list[dict[str, Any]]:
        """Get payments breakdown by payment method (invoice-imputed only).

        Reads ``InvoicePayment`` joined with the payments module's
        ``Payment.method``. Patient-level "all collected" is in the
        payments module's own reports.
        """
        from app.modules.payments.models import Payment as PaymentModel

        result = await db.execute(
            select(
                PaymentModel.method.label("payment_method"),
                func.count(InvoicePayment.id).label("payment_count"),
                func.coalesce(func.sum(InvoicePayment.amount), Decimal("0")).label("total_amount"),
            )
            .join(PaymentModel, PaymentModel.id == InvoicePayment.payment_id)
            .where(
                InvoicePayment.clinic_id == clinic_id,
                PaymentModel.payment_date >= date_from,
                PaymentModel.payment_date <= date_to,
            )
            .group_by(PaymentModel.method)
            .order_by(desc("total_amount"))
        )

        return [
            {
                "payment_method": row.payment_method,
                "total_amount": row.total_amount,
                "payment_count": row.payment_count,
            }
            for row in result.all()
        ]

    @staticmethod
    async def get_by_professional(
        db: AsyncSession,
        clinic_id: UUID,
        date_from: date,
        date_to: date,
    ) -> list[dict[str, Any]]:
        """Get billing breakdown by professional (creator)."""
        result = await db.execute(
            select(
                Invoice.created_by,
                func.count(Invoice.id).label("invoice_count"),
                func.coalesce(func.sum(Invoice.total), Decimal("0")).label("total_invoiced"),
            )
            .where(
                Invoice.clinic_id == clinic_id,
                Invoice.status.notin_(["draft", "voided"]),
                Invoice.issue_date >= date_from,
                Invoice.issue_date <= date_to,
                Invoice.deleted_at.is_(None),
            )
            .group_by(Invoice.created_by)
        )
        rows = result.all()

        # Get user names
        user_ids = [r.created_by for r in rows]
        user_names: dict[UUID, str] = {}
        if user_ids:
            result = await db.execute(select(User).where(User.id.in_(user_ids)))
            for user in result.scalars():
                user_names[user.id] = f"{user.first_name} {user.last_name}"

        return [
            {
                "professional_id": row.created_by,
                "professional_name": user_names.get(row.created_by, "-"),
                "total_invoiced": row.total_invoiced,
                "invoice_count": row.invoice_count,
            }
            for row in rows
        ]

    @staticmethod
    async def get_vat_summary(
        db: AsyncSession,
        clinic_id: UUID,
        date_from: date,
        date_to: date,
    ) -> list[dict[str, Any]]:
        """Get VAT summary for accounting."""
        result = await db.execute(
            select(
                InvoiceItem.vat_type_id,
                InvoiceItem.vat_rate,
                func.coalesce(
                    func.sum(InvoiceItem.line_subtotal - InvoiceItem.line_discount),
                    Decimal("0"),
                ).label("base_amount"),
                func.coalesce(func.sum(InvoiceItem.line_tax), Decimal("0")).label("tax_amount"),
            )
            .join(Invoice, InvoiceItem.invoice_id == Invoice.id)
            .where(
                Invoice.clinic_id == clinic_id,
                Invoice.status.notin_(["draft", "voided"]),
                Invoice.issue_date >= date_from,
                Invoice.issue_date <= date_to,
                Invoice.deleted_at.is_(None),
            )
            .group_by(InvoiceItem.vat_type_id, InvoiceItem.vat_rate)
            .order_by(InvoiceItem.vat_rate)
        )
        rows = result.all()

        # Get VAT type names
        vat_type_ids = [r.vat_type_id for r in rows if r.vat_type_id]
        vat_names: dict[UUID, str] = {}
        if vat_type_ids:
            result = await db.execute(select(VatType).where(VatType.id.in_(vat_type_ids)))
            for vt in result.scalars():
                vat_names[vt.id] = vt.names.get("es", f"IVA {vt.rate}%")

        return [
            {
                "vat_type_id": row.vat_type_id,
                "vat_rate": row.vat_rate,
                "vat_name": vat_names.get(row.vat_type_id, f"IVA {row.vat_rate}%"),
                "base_amount": row.base_amount,
                "tax_amount": row.tax_amount,
                "total_amount": row.base_amount + row.tax_amount,
            }
            for row in rows
        ]

    @staticmethod
    async def get_numbering_gaps(
        db: AsyncSession,
        clinic_id: UUID,
    ) -> list[dict[str, Any]]:
        """Find gaps in invoice numbering.

        Returns list of gaps by series and year.
        """
        # Get all series for the clinic
        result = await db.execute(
            select(InvoiceSeries).where(
                InvoiceSeries.clinic_id == clinic_id,
                InvoiceSeries.is_active.is_(True),
            )
        )
        series_list = result.scalars().all()

        gaps = []

        for series in series_list:
            # Get all sequential numbers for this series, grouped by the
            # fiscal year they were drawn in (the counter restarts there on a
            # reset_yearly series), not the year the draft was created.
            # Only include issued invoices (those with sequential_number assigned)
            result = await db.execute(
                select(
                    func.coalesce(
                        Invoice.fiscal_year, func.extract("year", Invoice.issue_date)
                    ).label("year"),
                    Invoice.sequential_number,
                )
                .where(
                    Invoice.clinic_id == clinic_id,
                    Invoice.series_id == series.id,
                    Invoice.sequential_number.isnot(None),  # Only issued invoices
                    Invoice.deleted_at.is_(None),
                )
                .order_by("year", Invoice.sequential_number)
            )
            rows = result.all()

            # Group by year
            by_year: dict[int, list[int]] = {}
            for row in rows:
                year = int(row.year)
                if year not in by_year:
                    by_year[year] = []
                by_year[year].append(row.sequential_number)

            # Find gaps in each year
            for year, numbers in by_year.items():
                if not numbers:
                    continue

                numbers = sorted(set(numbers))
                expected = set(range(1, max(numbers) + 1))
                found = set(numbers)
                missing = sorted(expected - found)

                if missing:
                    gaps.append(
                        {
                            "series_prefix": series.prefix,
                            "year": year,
                            "missing_numbers": missing,
                        }
                    )

        return gaps
