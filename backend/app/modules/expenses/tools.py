"""Agent tools for the expenses module. Thin wrappers over ExpenseService."""

from __future__ import annotations

from datetime import date as date_cls
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field

from app.core.agents import AgentContext, Tool, ToolCategory

from .schemas import ExpenseCategory, ExpenseCreate
from .service import ExpenseService


class ListExpensesArgs(BaseModel):
    category: ExpenseCategory | None = None
    date_from: date_cls | None = None
    date_to: date_cls | None = None
    limit: int = Field(default=20, ge=1, le=100)


class CreateExpenseArgs(BaseModel):
    category: ExpenseCategory
    amount: Decimal
    expense_date: date_cls
    description: str | None = None


class MonthlyTotalsArgs(BaseModel):
    year: int
    month: int = Field(ge=1, le=12)


def _expense_summary(expense) -> dict:
    return {
        "id": str(expense.id),
        "category": expense.category,
        "amount": expense.amount,
        "expense_date": expense.expense_date,
        "description": expense.description,
    }


async def _list_expenses(ctx: AgentContext, params: ListExpensesArgs) -> dict:
    items, total = await ExpenseService.list_expenses(
        ctx.db,
        ctx.clinic_id,
        category=params.category,
        date_from=params.date_from,
        date_to=params.date_to,
        page=1,
        page_size=params.limit,
    )
    return {"total": total, "expenses": [_expense_summary(e) for e in items]}


async def _create_expense(ctx: AgentContext, params: CreateExpenseArgs) -> dict:
    payload = ExpenseCreate(
        category=params.category,
        amount=params.amount,
        expense_date=params.expense_date,
        description=params.description,
    )
    expense = await ExpenseService.create_expense(ctx.db, ctx.clinic_id, payload, ctx.user_id)
    return _expense_summary(expense)


async def _monthly_totals(ctx: AgentContext, params: MonthlyTotalsArgs) -> dict:
    totals = await ExpenseService.monthly_totals_by_category(
        ctx.db, ctx.clinic_id, params.year, params.month
    )
    return {"totals": [{"category": t.category, "total": t.total} for t in totals]}


def get_tools() -> list[Tool]:
    return [
        Tool(
            name="list_expenses",
            description="List fixed office expenses, optionally filtered by category or date range.",
            parameters=ListExpensesArgs,
            handler=_list_expenses,
            permissions=["expenses.read"],
            category=ToolCategory.READ,
        ),
        Tool(
            name="create_expense",
            description="Record a new fixed office expense (rent, utilities, salaries, etc.).",
            parameters=CreateExpenseArgs,
            handler=_create_expense,
            permissions=["expenses.write"],
            category=ToolCategory.WRITE,
        ),
        Tool(
            name="expense_monthly_totals",
            description="Get total expenses per category for a given month.",
            parameters=MonthlyTotalsArgs,
            handler=_monthly_totals,
            permissions=["expenses.read"],
            category=ToolCategory.READ,
        ),
    ]
