"""Expenses HTTP surface. Mounts under ``/api/v1/expenses/*``."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.dependencies import ClinicContext, get_clinic_context, require_permission
from app.core.schemas import ApiResponse, PaginatedApiResponse
from app.database import get_db

from .schemas import (
    ExpenseCreate,
    ExpenseMonthlyTotal,
    ExpenseResponse,
    ExpenseUpdate,
)
from .service import ExpenseService

router = APIRouter()


@router.get("/", response_model=PaginatedApiResponse[ExpenseResponse])
async def list_expenses(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("expenses.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    category: str | None = Query(default=None),
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> PaginatedApiResponse[ExpenseResponse]:
    expenses, total = await ExpenseService.list_expenses(
        db, ctx.clinic_id, category, date_from, date_to, page, page_size
    )
    return PaginatedApiResponse(
        data=[ExpenseResponse.model_validate(e) for e in expenses],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/monthly-totals", response_model=ApiResponse[list[ExpenseMonthlyTotal]])
async def monthly_totals(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("expenses.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    year: int = Query(...),
    month: int = Query(..., ge=1, le=12),
) -> ApiResponse[list[ExpenseMonthlyTotal]]:
    totals = await ExpenseService.monthly_totals_by_category(db, ctx.clinic_id, year, month)
    return ApiResponse(data=totals)


@router.post("/", response_model=ApiResponse[ExpenseResponse])
async def create_expense(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("expenses.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    payload: ExpenseCreate,
) -> ApiResponse[ExpenseResponse]:
    expense = await ExpenseService.create_expense(db, ctx.clinic_id, payload, ctx.user_id)
    return ApiResponse(data=ExpenseResponse.model_validate(expense))


@router.patch("/{expense_id}", response_model=ApiResponse[ExpenseResponse])
async def update_expense(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("expenses.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    expense_id: UUID,
    payload: ExpenseUpdate,
) -> ApiResponse[ExpenseResponse]:
    expense = await ExpenseService.update_expense(db, ctx.clinic_id, expense_id, payload)
    return ApiResponse(data=ExpenseResponse.model_validate(expense))


@router.delete("/{expense_id}", response_model=ApiResponse[None])
async def delete_expense(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("expenses.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    expense_id: UUID,
) -> ApiResponse[None]:
    await ExpenseService.delete_expense(db, ctx.clinic_id, expense_id)
    return ApiResponse(data=None)
