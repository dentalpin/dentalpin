"""ExpenseService — business logic for expense CRUD and monthly summaries."""

from __future__ import annotations

from datetime import date
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import Expense
from .schemas import ExpenseCreate, ExpenseMonthlyTotal, ExpenseUpdate


class ExpenseService:
    @staticmethod
    async def create_expense(
        db: AsyncSession,
        clinic_id: UUID,
        payload: ExpenseCreate,
        created_by: UUID | None,
    ) -> Expense:
        expense = Expense(
            clinic_id=clinic_id,
            category=payload.category,
            amount=payload.amount,
            expense_date=payload.expense_date,
            description=payload.description,
            created_by=created_by,
        )
        db.add(expense)
        await db.commit()
        await db.refresh(expense)
        return expense

    @staticmethod
    async def list_expenses(
        db: AsyncSession,
        clinic_id: UUID,
        category: str | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Expense], int]:
        stmt = select(Expense).where(Expense.clinic_id == clinic_id)
        if category:
            stmt = stmt.where(Expense.category == category)
        if date_from:
            stmt = stmt.where(Expense.expense_date >= date_from)
        if date_to:
            stmt = stmt.where(Expense.expense_date <= date_to)

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await db.execute(count_stmt)).scalar_one()

        stmt = (
            stmt.order_by(Expense.expense_date.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        rows = (await db.execute(stmt)).scalars().all()
        return list(rows), total

    @staticmethod
    async def get_expense(db: AsyncSession, clinic_id: UUID, expense_id: UUID) -> Expense:
        stmt = select(Expense).where(Expense.id == expense_id, Expense.clinic_id == clinic_id)
        expense = (await db.execute(stmt)).scalar_one_or_none()
        if expense is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Expense not found")
        return expense

    @staticmethod
    async def update_expense(
        db: AsyncSession, clinic_id: UUID, expense_id: UUID, payload: ExpenseUpdate
    ) -> Expense:
        expense = await ExpenseService.get_expense(db, clinic_id, expense_id)
        for field, value in payload.model_dump(exclude_unset=True).items():
            setattr(expense, field, value)
        await db.commit()
        await db.refresh(expense)
        return expense

    @staticmethod
    async def delete_expense(db: AsyncSession, clinic_id: UUID, expense_id: UUID) -> None:
        expense = await ExpenseService.get_expense(db, clinic_id, expense_id)
        await db.delete(expense)
        await db.commit()

    @staticmethod
    async def monthly_totals_by_category(
        db: AsyncSession, clinic_id: UUID, year: int, month: int
    ) -> list[ExpenseMonthlyTotal]:
        stmt = (
            select(Expense.category, func.sum(Expense.amount).label("total"))
            .where(
                Expense.clinic_id == clinic_id,
                func.extract("year", Expense.expense_date) == year,
                func.extract("month", Expense.expense_date) == month,
            )
            .group_by(Expense.category)
        )
        rows = (await db.execute(stmt)).all()
        return [ExpenseMonthlyTotal(category=r.category, total=r.total) for r in rows]
