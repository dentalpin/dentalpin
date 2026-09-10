"""Expenses HTTP surface. Mounts under ``/api/v1/expenses/*``."""

from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.dependencies import ClinicContext, get_clinic_context, require_permission
from app.core.schemas import ApiResponse, PaginatedApiResponse
from app.database import get_db

from .csv_import import CsvImportError, import_expenses, read_upload_limited, validate_expense_csv
from .schemas import (
    ExpenseCreate,
    ExpenseImportReport,
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
    # Typed as date so asyncpg receives a date and the DB can compare it
    # against the Date column — a str here 500s on
    # ``operator does not exist: date >= character varying``.
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
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


@router.post("/", response_model=ApiResponse[ExpenseResponse], status_code=status.HTTP_201_CREATED)
async def create_expense(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("expenses.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    payload: ExpenseCreate,
) -> ApiResponse[ExpenseResponse]:
    expense = await ExpenseService.create_expense(db, ctx.clinic_id, payload, ctx.user_id)
    return ApiResponse(data=ExpenseResponse.model_validate(expense))


@router.post("/import.csv", response_model=ApiResponse[ExpenseImportReport])
async def import_expenses_csv(
    file: Annotated[UploadFile, File()],
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("expenses.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    dry_run: bool = Query(default=True),
) -> ApiResponse[ExpenseImportReport]:
    """Import expenses from CSV. Dry-run (default) validates only; with
    ``dry_run=false`` valid rows are created attributed to the caller."""
    try:
        content = await read_upload_limited(file)
        valid, errors, total = validate_expense_csv(content)
    except CsvImportError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    created = 0
    if not dry_run and valid:
        expenses = await import_expenses(db, ctx.clinic_id, ctx.user_id, valid)
        created = len(expenses)
    return ApiResponse(
        data=ExpenseImportReport(total=total, valid=len(valid), created=created, errors=errors)
    )


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


@router.delete("/{expense_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_expense(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("expenses.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    expense_id: UUID,
) -> None:
    await ExpenseService.delete_expense(db, ctx.clinic_id, expense_id)
