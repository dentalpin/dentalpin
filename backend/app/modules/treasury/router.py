"""HTTP surface for treasury.

Mounted under ``/api/v1/treasury/*``. Admin-only (money balances keep
the payroll-grade blast radius until clinics widen grants via roles).
"""

from decimal import Decimal
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.dependencies import ClinicContext, get_clinic_context, require_permission
from app.core.schemas import ApiResponse
from app.database import get_db

from .models import TreasuryAccount
from .schemas import (
    AccountCreate,
    AccountResponse,
    AccountUpdate,
    CorrectionRequest,
    EntryResponse,
    TransferRequest,
)
from .service import TreasuryService

router = APIRouter()


async def _ensure_account(db: AsyncSession, clinic_id: UUID, account_id: UUID):
    row = await TreasuryService.get_account(db, clinic_id, account_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")
    return row


async def _with_balance(
    db: AsyncSession, row: TreasuryAccount, balances: dict | None = None
) -> AccountResponse:
    if balances is None:
        balance = await TreasuryService.balance(db, row)
    else:
        balance = balances.get(row.id, row.opening_balance or Decimal("0"))
    return AccountResponse(
        id=row.id,
        name=row.name,
        kind=row.kind,
        opening_balance=row.opening_balance,
        is_active=row.is_active,
        balance=balance,
    )


# --- Accounts ------------------------------------------------------------


@router.get("/accounts", response_model=ApiResponse[list[AccountResponse]])
async def list_accounts(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("treasury.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[list[AccountResponse]]:
    rows = await TreasuryService.list_accounts(db, ctx.clinic_id)
    balances = await TreasuryService.balances(db, ctx.clinic_id)
    return ApiResponse(data=[await _with_balance(db, r, balances) for r in rows])


@router.post(
    "/accounts",
    response_model=ApiResponse[AccountResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_account(
    data: AccountCreate,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("treasury.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[AccountResponse]:
    row = await TreasuryService.create_account(db, ctx.clinic_id, data.model_dump())
    await db.commit()
    await db.refresh(row)
    return ApiResponse(data=await _with_balance(db, row))


@router.patch("/accounts/{account_id}", response_model=ApiResponse[AccountResponse])
async def update_account(
    account_id: UUID,
    data: AccountUpdate,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("treasury.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[AccountResponse]:
    row = await _ensure_account(db, ctx.clinic_id, account_id)
    row = await TreasuryService.update_account(db, row, data.model_dump(exclude_unset=True))
    await db.commit()
    await db.refresh(row)
    return ApiResponse(data=await _with_balance(db, row))


@router.delete("/accounts/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_account(
    account_id: UUID,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("treasury.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    row = await _ensure_account(db, ctx.clinic_id, account_id)
    await TreasuryService.delete_account(db, row)
    await db.commit()


@router.get(
    "/accounts/{account_id}/entries",
    response_model=ApiResponse[list[EntryResponse]],
)
async def account_statement(
    account_id: UUID,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("treasury.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: int = Query(default=100, ge=1, le=500),
) -> ApiResponse[list[EntryResponse]]:
    await _ensure_account(db, ctx.clinic_id, account_id)
    rows = await TreasuryService.statement(db, ctx.clinic_id, account_id, limit)
    return ApiResponse(data=[EntryResponse.model_validate(r) for r in rows])


# --- Movements -------------------------------------------------------------


@router.post(
    "/transfers",
    response_model=ApiResponse[list[EntryResponse]],
    status_code=status.HTTP_201_CREATED,
)
async def transfer(
    data: TransferRequest,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("treasury.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[list[EntryResponse]]:
    src = await _ensure_account(db, ctx.clinic_id, data.from_account_id)
    dst = await _ensure_account(db, ctx.clinic_id, data.to_account_id)
    legs = await TreasuryService.transfer(
        db,
        ctx.clinic_id,
        src,
        dst,
        data.amount,
        data.memo,
        data.at,
        created_by=ctx.user_id,
    )
    await db.commit()
    for leg in legs:
        await db.refresh(leg)
    return ApiResponse(data=[EntryResponse.model_validate(r) for r in legs])


@router.post(
    "/accounts/{account_id}/corrections",
    response_model=ApiResponse[EntryResponse],
    status_code=status.HTTP_201_CREATED,
)
async def correct(
    account_id: UUID,
    data: CorrectionRequest,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("treasury.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[EntryResponse]:
    row = await _ensure_account(db, ctx.clinic_id, account_id)
    entry = await TreasuryService.correct(
        db,
        ctx.clinic_id,
        row,
        data.amount,
        data.direction,
        data.memo,
        data.at,
        created_by=ctx.user_id,
    )
    await db.commit()
    await db.refresh(entry)
    return ApiResponse(data=EntryResponse.model_validate(entry))
