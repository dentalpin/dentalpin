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

from app.modules.billing.models import Invoice

# Outstanding = issued or partially processed, never drafts, cancelled,
# voided or fully paid. Soft-deleted rows never count.
OPEN_STATUSES = ("issued", "partial")

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
        count as current (0-30). Buckets carry the issued total (never
        netted against anything else) plus invoice and distinct-patient
        counts.
        """
        today = date.today()
        rows = (
            await db.execute(
                select(
                    Invoice.due_date,
                    Invoice.patient_id,
                    func.sum(Invoice.total).label("total"),
                    func.count(Invoice.id).label("count"),
                )
                .where(
                    Invoice.clinic_id == clinic_id,
                    Invoice.status.in_(OPEN_STATUSES),
                    Invoice.deleted_at.is_(None),
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
