"""Financial family: invoice-axis aggregates.

Every query here reads the INVOICE axis only (issue/due dates, status,
totals): nothing joins the payments side and nothing nets one axis
against the other (pinned by ``test_reports_offbooks_guard.py``).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.core.utils.dates import clinic_today_for
from app.modules.billing.models import Invoice

BUCKETS: tuple[tuple[str, int | None, int | None], ...] = (
    ("not_due", None, -1),
    ("0-30", 0, 30),
    ("31-60", 31, 60),
    ("61-90", 61, 90),
    ("90+", 91, None),
)


class FinancialReportService:
    """Aging buckets + issued trend, invoice axis only."""

    @staticmethod
    async def aging_buckets(db: AsyncSession, clinic_id: UUID) -> list[dict]:
        """Outstanding invoice totals per age bucket (due-date anchored).

        Not-yet-due invoices get their own ``not_due`` ("no vencidas")
        bucket instead of folding into 0-30; invoices with no due date
        count as current (0-30). Buckets carry the outstanding invoice
        total plus invoice and distinct-patient counts.

        Outstanding = billing's ``open_receivable_conditions`` (issued or
        partial, not imported history, never a credit note, #1201), the
        same base as the overdue list. Soft-deleted rows never count.

        Credit notes never appear as rows of their own, but the invoice
        they rectify stays ``issued`` next to them (billing keeps both
        documents), so each invoice's total is netted with its live
        credit notes (issued/partial/paid, not deleted): a partly credited
        invoice carries the rest in its own due-date bucket, a fully
        credited one drops out. Netting stays on the invoice axis (no
        payment data).
        """
        from app.modules.billing.service import open_receivable_conditions

        today = await clinic_today_for(db, clinic_id)
        credit_note = aliased(Invoice)
        credited = (
            select(
                credit_note.credit_note_for_id.label("invoice_id"),
                func.sum(credit_note.total).label("credited"),
            )
            .where(
                credit_note.clinic_id == clinic_id,
                credit_note.credit_note_for_id.is_not(None),
                credit_note.status.notin_(("draft", "cancelled", "voided")),
                credit_note.deleted_at.is_(None),
            )
            .group_by(credit_note.credit_note_for_id)
            .subquery()
        )
        # Credit note totals are negative, so adding them nets the invoice.
        net = Invoice.total + func.coalesce(credited.c.credited, 0)
        rows = (
            await db.execute(
                select(
                    Invoice.due_date,
                    Invoice.patient_id,
                    func.sum(net).label("total"),
                    func.count(Invoice.id).label("count"),
                )
                .outerjoin(credited, credited.c.invoice_id == Invoice.id)
                .where(
                    Invoice.clinic_id == clinic_id,
                    *open_receivable_conditions(),
                    Invoice.deleted_at.is_(None),
                    net > 0,
                )
                .group_by(Invoice.due_date, Invoice.patient_id)
            )
        ).all()

        buckets: dict[str, dict] = {
            label: {"label": label, "total": Decimal("0"), "count": 0, "patient_count": 0}
            for label, _, _ in BUCKETS
        }
        patients: dict[str, set[UUID]] = {label: set() for label, _, _ in BUCKETS}
        for due_date, patient_id, total, count in rows:
            if due_date is None:
                label = "0-30"
            else:
                age = (today - due_date).days
                label = next(
                    lbl
                    for lbl, lo, hi in BUCKETS
                    if (lo is None or age >= lo) and (hi is None or age <= hi)
                )
            slot = buckets[label]
            slot["total"] += total or Decimal("0")
            slot["count"] += count
            patients[label].add(patient_id)
        for label, ids in patients.items():
            buckets[label]["patient_count"] = len(ids)
        return [buckets[label] for label, _, _ in BUCKETS]

    @staticmethod
    async def issued_trend(
        db: AsyncSession, clinic_id: UUID, date_from: date, date_to: date
    ) -> list[dict]:
        """Issued invoice totals per month in the window (YYYY-MM points).

        Drafts, cancelled and voided invoices never count; soft-deleted
        rows never count. Totals are issued amounts on their own axis.
        """
        rows = (
            await db.execute(
                select(
                    func.to_char(Invoice.issue_date, "YYYY-MM").label("month"),
                    func.sum(Invoice.total).label("total"),
                    func.count(Invoice.id).label("count"),
                )
                .where(
                    Invoice.clinic_id == clinic_id,
                    Invoice.status.notin_(["draft", "cancelled", "voided"]),
                    Invoice.issue_date.is_not(None),
                    Invoice.issue_date >= date_from,
                    Invoice.issue_date <= date_to,
                    Invoice.deleted_at.is_(None),
                )
                .group_by("month")
                .order_by("month")
            )
        ).all()
        return [
            {"month": month, "total": total or Decimal("0"), "count": count}
            for month, total, count in rows
        ]
