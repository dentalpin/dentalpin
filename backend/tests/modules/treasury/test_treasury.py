"""treasury: accounts, transfers, corrections, balances, tenancy."""

from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic
from app.modules.treasury.service import TreasuryService


@pytest.mark.asyncio
async def test_transfer_moves_both_legs_and_balances(db_session: AsyncSession, test_clinic: Clinic):
    cash = await TreasuryService.create_account(
        db_session,
        test_clinic.id,
        {"name": "Caja", "kind": "cash", "opening_balance": Decimal("100")},
    )
    bank = await TreasuryService.create_account(
        db_session,
        test_clinic.id,
        {"name": "Banco", "kind": "bank", "opening_balance": Decimal("0")},
    )
    await db_session.commit()
    assert await TreasuryService.balance(db_session, cash) == Decimal("100")

    legs = await TreasuryService.transfer(
        db_session, test_clinic.id, cash, bank, Decimal("30"), "seed", None
    )
    await db_session.commit()
    assert {leg.kind for leg in legs} == {"transfer_out", "transfer_in"}
    assert legs[0].group_id == legs[1].group_id
    assert await TreasuryService.balance(db_session, cash) == Decimal("70")
    assert await TreasuryService.balance(db_session, bank) == Decimal("30")

    await TreasuryService.correct(
        db_session, test_clinic.id, bank, Decimal("5"), "out", "fee", None
    )
    await db_session.commit()
    assert await TreasuryService.balance(db_session, bank) == Decimal("25")


@pytest.mark.asyncio
async def test_duplicate_name_is_409(db_session: AsyncSession, test_clinic: Clinic):
    await TreasuryService.create_account(db_session, test_clinic.id, {"name": "Caja"})
    await db_session.commit()
    with pytest.raises(HTTPException) as exc:
        await TreasuryService.create_account(db_session, test_clinic.id, {"name": "Caja"})
    assert exc.value.status_code == 409


@pytest.mark.asyncio
async def test_same_account_transfer_is_422(db_session: AsyncSession, test_clinic: Clinic):
    cash = await TreasuryService.create_account(db_session, test_clinic.id, {"name": "Caja"})
    await db_session.commit()
    with pytest.raises(HTTPException) as exc:
        await TreasuryService.transfer(
            db_session, test_clinic.id, cash, cash, Decimal("10"), None, None
        )
    assert exc.value.status_code == 422


@pytest.mark.asyncio
async def test_foreign_clinic_account_is_invisible(db_session: AsyncSession, test_clinic: Clinic):
    other = Clinic(id=uuid4(), name="Other", tax_id="B9", address={}, settings={})
    db_session.add(other)
    await db_session.commit()
    foreign = await TreasuryService.create_account(db_session, other.id, {"name": "Caja"})
    await db_session.commit()
    assert await TreasuryService.get_account(db_session, test_clinic.id, foreign.id) is None
    assert await TreasuryService.list_accounts(db_session, test_clinic.id) == []


@pytest.mark.asyncio
async def test_http_codes(client, auth_headers, test_clinic: Clinic):
    created = await client.post(
        "/api/v1/treasury/accounts",
        json={"name": "Caja", "kind": "cash"},
        headers=auth_headers,
    )
    assert created.status_code == 201
    assert Decimal(created.json()["data"]["balance"]) == Decimal("0")
    cash_id = created.json()["data"]["id"]

    bank = await client.post(
        "/api/v1/treasury/accounts",
        json={"name": "Banco", "kind": "bank"},
        headers=auth_headers,
    )
    assert bank.status_code == 201
    bank_id = bank.json()["data"]["id"]

    dup = await client.post(
        "/api/v1/treasury/accounts", json={"name": "Caja"}, headers=auth_headers
    )
    assert dup.status_code == 409

    bad_kind = await client.post(
        "/api/v1/treasury/accounts", json={"name": "X", "kind": "crypto"}, headers=auth_headers
    )
    assert bad_kind.status_code == 422

    moved = await client.post(
        "/api/v1/treasury/transfers",
        json={"from_account_id": cash_id, "to_account_id": bank_id, "amount": "25.50"},
        headers=auth_headers,
    )
    assert moved.status_code == 200
    assert len(moved.json()["data"]) == 2

    same = await client.post(
        "/api/v1/treasury/transfers",
        json={"from_account_id": cash_id, "to_account_id": cash_id, "amount": "1"},
        headers=auth_headers,
    )
    assert same.status_code == 422

    fixed = await client.post(
        f"/api/v1/treasury/accounts/{bank_id}/corrections",
        json={"amount": "0.50", "direction": "out", "memo": "fee"},
        headers=auth_headers,
    )
    assert fixed.status_code == 201

    listed = await client.get("/api/v1/treasury/accounts", headers=auth_headers)
    assert listed.status_code == 200
    balances = {a["name"]: Decimal(a["balance"]) for a in listed.json()["data"]}
    assert balances == {"Banco": Decimal("25"), "Caja": Decimal("-25.50")}

    statement = await client.get(
        f"/api/v1/treasury/accounts/{bank_id}/entries", headers=auth_headers
    )
    assert statement.status_code == 200
    assert len(statement.json()["data"]) == 2

    missing = await client.get(f"/api/v1/treasury/accounts/{uuid4()}/entries", headers=auth_headers)
    assert missing.status_code == 404
