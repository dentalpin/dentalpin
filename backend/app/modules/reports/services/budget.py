"""Budget report service."""

from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import User
from app.core.utils.dates import clinic_day_range, clinic_zone_for
from app.modules.budget.models import Budget, BudgetItem
from app.modules.catalog.models import TreatmentCatalogItem


async def _clinic_days(
    db: AsyncSession, clinic_id: UUID, date_from: date, date_to: date
) -> tuple[datetime, datetime]:
    """``[start, end)`` of the report period on the clinic's clock.

    ``created_at`` is an instant; a bare ``date`` compared with it is read as
    UTC midnight, so the period was cut on UTC days.
    """
    return clinic_day_range(await clinic_zone_for(db, clinic_id), date_from, date_to)


class BudgetReportService:
    """Service for budget reports."""

    @staticmethod
    async def get_summary(
        db: AsyncSession,
        clinic_id: UUID,
        date_from: date,
        date_to: date,
    ) -> dict[str, Any]:
        """Get budget summary for a period.

        Returns:
            - total_created: Number of budgets created
            - total_amount: Sum of all budget totals
            - accepted_count: Number of accepted budgets
            - accepted_amount: Sum of accepted budget totals
            - rejected_count: Number of rejected budgets
            - pending_count: Number of pending budgets (draft)
            - acceptance_rate: Percentage of accepted vs (accepted + rejected)
            - average_value: Average budget total
        """
        day_start, day_end = await _clinic_days(db, clinic_id, date_from, date_to)
        # Get counts and totals by status
        result = await db.execute(
            select(
                func.count(Budget.id).label("total_created"),
                func.coalesce(func.sum(Budget.total), Decimal("0")).label("total_amount"),
                func.coalesce(func.sum(case((Budget.status == "accepted", 1), else_=0)), 0).label(
                    "accepted_count"
                ),
                func.coalesce(
                    func.sum(case((Budget.status == "accepted", Budget.total), else_=0)),
                    Decimal("0"),
                ).label("accepted_amount"),
                func.coalesce(func.sum(case((Budget.status == "rejected", 1), else_=0)), 0).label(
                    "rejected_count"
                ),
                func.coalesce(func.sum(case((Budget.status == "draft", 1), else_=0)), 0).label(
                    "pending_count"
                ),
                func.coalesce(func.sum(case((Budget.status == "completed", 1), else_=0)), 0).label(
                    "completed_count"
                ),
                func.coalesce(
                    func.sum(case((Budget.status == "completed", Budget.total), else_=0)),
                    Decimal("0"),
                ).label("completed_amount"),
            ).where(
                Budget.clinic_id == clinic_id,
                Budget.created_at >= day_start,
                Budget.created_at < day_end,
                Budget.deleted_at.is_(None),
            )
        )
        totals = result.one()

        # Calculate acceptance rate
        decided = totals.accepted_count + totals.rejected_count
        acceptance_rate = (totals.accepted_count / decided * 100) if decided > 0 else 0.0

        # Calculate average value
        average_value = (
            totals.total_amount / totals.total_created if totals.total_created > 0 else Decimal("0")
        )

        return {
            "period_start": date_from,
            "period_end": date_to,
            "total_created": totals.total_created,
            "total_amount": totals.total_amount,
            "accepted_count": totals.accepted_count,
            "accepted_amount": totals.accepted_amount,
            "rejected_count": totals.rejected_count,
            "pending_count": totals.pending_count,
            "completed_count": totals.completed_count,
            "completed_amount": totals.completed_amount,
            "acceptance_rate": round(acceptance_rate, 1),
            "average_value": average_value,
        }

    @staticmethod
    async def get_by_professional(
        db: AsyncSession,
        clinic_id: UUID,
        date_from: date,
        date_to: date,
    ) -> list[dict[str, Any]]:
        """Get budget breakdown by professional (creator or assigned)."""
        day_start, day_end = await _clinic_days(db, clinic_id, date_from, date_to)
        # Use created_by as the professional
        result = await db.execute(
            select(
                Budget.created_by,
                func.count(Budget.id).label("budget_count"),
                func.coalesce(func.sum(Budget.total), Decimal("0")).label("total_amount"),
                func.coalesce(func.sum(case((Budget.status == "accepted", 1), else_=0)), 0).label(
                    "accepted_count"
                ),
            )
            .where(
                Budget.clinic_id == clinic_id,
                Budget.created_at >= day_start,
                Budget.created_at < day_end,
                Budget.deleted_at.is_(None),
            )
            .group_by(Budget.created_by)
        )
        rows = result.all()

        # Get user names
        user_ids = [r.created_by for r in rows if r.created_by]
        user_names: dict[UUID, str] = {}
        if user_ids:
            result = await db.execute(select(User).where(User.id.in_(user_ids)))
            for user in result.scalars():
                user_names[user.id] = f"{user.first_name} {user.last_name}"

        return [
            {
                "professional_id": row.created_by,
                "professional_name": user_names.get(row.created_by, "-"),
                "budget_count": row.budget_count,
                "total_amount": row.total_amount,
                "accepted_count": row.accepted_count,
                "acceptance_rate": round(
                    (row.accepted_count / row.budget_count * 100) if row.budget_count > 0 else 0,
                    1,
                ),
            }
            for row in rows
        ]

    @staticmethod
    async def get_by_treatment(
        db: AsyncSession,
        clinic_id: UUID,
        date_from: date,
        date_to: date,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Get most common treatments in budgets."""
        day_start, day_end = await _clinic_days(db, clinic_id, date_from, date_to)
        result = await db.execute(
            select(
                BudgetItem.catalog_item_id,
                func.count(BudgetItem.id).label("occurrence_count"),
                func.coalesce(func.sum(BudgetItem.quantity), 0).label("total_quantity"),
                func.coalesce(func.sum(BudgetItem.line_total), Decimal("0")).label("total_amount"),
            )
            .join(Budget, BudgetItem.budget_id == Budget.id)
            .where(
                Budget.clinic_id == clinic_id,
                Budget.created_at >= day_start,
                Budget.created_at < day_end,
                Budget.deleted_at.is_(None),
                BudgetItem.catalog_item_id.isnot(None),
            )
            .group_by(BudgetItem.catalog_item_id)
            .order_by(func.count(BudgetItem.id).desc())
            .limit(limit)
        )
        rows = result.all()

        # Get treatment names
        catalog_ids = [r.catalog_item_id for r in rows if r.catalog_item_id]
        treatment_names: dict[UUID, str] = {}
        if catalog_ids:
            result = await db.execute(
                select(TreatmentCatalogItem).where(TreatmentCatalogItem.id.in_(catalog_ids))
            )
            for item in result.scalars():
                treatment_names[item.id] = item.names.get("es", item.internal_code)

        return [
            {
                "catalog_item_id": row.catalog_item_id,
                "treatment_name": treatment_names.get(row.catalog_item_id, "-"),
                "occurrence_count": row.occurrence_count,
                "total_quantity": row.total_quantity,
                "total_amount": row.total_amount,
            }
            for row in rows
        ]

    @staticmethod
    async def get_by_status(
        db: AsyncSession,
        clinic_id: UUID,
        date_from: date,
        date_to: date,
    ) -> list[dict[str, Any]]:
        """Get budget breakdown by status."""
        day_start, day_end = await _clinic_days(db, clinic_id, date_from, date_to)
        result = await db.execute(
            select(
                Budget.status,
                func.count(Budget.id).label("count"),
                func.coalesce(func.sum(Budget.total), Decimal("0")).label("total_amount"),
            )
            .where(
                Budget.clinic_id == clinic_id,
                Budget.created_at >= day_start,
                Budget.created_at < day_end,
                Budget.deleted_at.is_(None),
            )
            .group_by(Budget.status)
        )

        return [
            {
                "status": row.status,
                "count": row.count,
                "total_amount": row.total_amount,
            }
            for row in result.all()
        ]
