"""Financial family: invoice-axis aggregates (off-books rule).

Every query here reads the INVOICE axis only (issue/due dates, status,
totals). Nothing references the settlement side and nothing nets one
axis against the other: the copilot off-books boundary is structural,
not a review note (see ``test_reports_offbooks_guard.py``).

Grandfathered exception (not ours to remove in this PR):
``BillingReportService.get_overdue_invoices`` subtracts recorded
amounts to show its per-row remainder. It predates the rule; a
follow-up should either refit it to invoice totals or record an
explicit exemption. New code must not copy the pattern.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.billing.models import Invoice

# Outstanding = issued or partially processed, never drafts, cancelled,
# voided or fully paid. Soft-deleted rows never count.
OPEN_STATUSES = ("issued", "partial")

BUCKETS: tuple[tuple[str, int | None, int | None], ...] = (
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

        An invoice with no due date counts as current (0-30). Buckets
        carry the issued total (never netted against anything else) plus
        invoice and distinct-patient counts.
        """
        today = date.today()
        rows = (
            await db.execute(
                select(
                    Invoice.due_date,
                    func.sum(Invoice.total).label("total"),
                    func.count(Invoice.id).label("count"),
                    func.count(func.distinct(Invoice.patient_id)).label("patients"),
                )
                .where(
                    Invoice.clinic_id == clinic_id,
                    Invoice.status.in_(OPEN_STATUSES),
                    Invoice.deleted_at.is_(None),
                )
                .group_by(Invoice.due_date)
            )
        ).all()

        buckets: dict[str, dict] = {
            label: {"label": label, "total": Decimal("0"), "count": 0, "patient_count": 0}
            for label, _, _ in BUCKETS
        }
        for due_date, total, count, patients in rows:
            # Not-yet-due invoices are current outstanding (0-30).
            age = max(0, (today - due_date).days) if due_date else 0
            label = next(lbl for lbl, lo, hi in BUCKETS if lo <= age and (hi is None or age <= hi))
            slot = buckets[label]
            slot["total"] += total or Decimal("0")
            slot["count"] += count
            slot["patient_count"] += patients
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
