"""treasury: accounts, transfers, corrections, balances, tenancy."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
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
    assert moved.status_code == 201
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


@pytest.mark.asyncio
async def test_delete_account_with_entries_is_409(db_session: AsyncSession, test_clinic: Clinic):
    cash = await TreasuryService.create_account(db_session, test_clinic.id, {"name": "Caja"})
    bank = await TreasuryService.create_account(db_session, test_clinic.id, {"name": "Banco"})
    await TreasuryService.transfer(
        db_session, test_clinic.id, cash, bank, Decimal("10"), None, None
    )
    await db_session.commit()
    with pytest.raises(HTTPException) as exc:
        await TreasuryService.delete_account(db_session, cash)
    assert exc.value.status_code == 409


@pytest.mark.asyncio
async def test_delete_empty_account(client, auth_headers, test_clinic: Clinic):
    created = await client.post(
        "/api/v1/treasury/accounts",
        json={"name": "Vacía", "kind": "cash"},
        headers=auth_headers,
    )
    assert created.status_code == 201
    gone = await client.delete(
        f"/api/v1/treasury/accounts/{created.json()['data']['id']}",
        headers=auth_headers,
    )
    assert gone.status_code == 204


@pytest.mark.asyncio
async def test_delete_account_with_entries_http_is_409(client, auth_headers, test_clinic: Clinic):
    cash = (
        await client.post(
            "/api/v1/treasury/accounts",
            json={"name": "Caja409", "kind": "cash"},
            headers=auth_headers,
        )
    ).json()["data"]
    bank = (
        await client.post(
            "/api/v1/treasury/accounts",
            json={"name": "Banco409", "kind": "bank"},
            headers=auth_headers,
        )
    ).json()["data"]
    moved = await client.post(
        "/api/v1/treasury/transfers",
        json={"from_account_id": cash["id"], "to_account_id": bank["id"], "amount": "5"},
        headers=auth_headers,
    )
    assert moved.status_code == 201
    gone = await client.delete(f"/api/v1/treasury/accounts/{cash['id']}", headers=auth_headers)
    assert gone.status_code == 409


@pytest.mark.asyncio
async def test_decimal_edges_are_422_not_500(client, auth_headers, test_clinic: Clinic):
    fuzzy = await client.post(
        "/api/v1/treasury/accounts",
        json={"name": "Fuzzy", "kind": "cash", "opening_balance": "10.005"},
        headers=auth_headers,
    )
    assert fuzzy.status_code == 422
    huge = await client.post(
        "/api/v1/treasury/accounts",
        json={"name": "Huge", "kind": "cash", "opening_balance": "9999999999999.99"},
        headers=auth_headers,
    )
    assert huge.status_code == 422


@pytest.mark.asyncio
async def test_transfer_stores_created_by(db_session: AsyncSession, test_clinic: Clinic):
    from app.core.auth.models import ClinicMembership, User
    from app.core.auth.service import hash_password

    actor = User(
        id=uuid4(),
        email=f"actor-{uuid4().hex[:6]}@t.c",
        password_hash=hash_password("TestPass1234"),
        first_name="A",
        last_name="C",
        is_active=True,
    )
    db_session.add(actor)
    await db_session.flush()
    db_session.add(
        ClinicMembership(id=uuid4(), user_id=actor.id, clinic_id=test_clinic.id, role="admin")
    )
    cash = await TreasuryService.create_account(db_session, test_clinic.id, {"name": "Caja"})
    bank = await TreasuryService.create_account(db_session, test_clinic.id, {"name": "Banco"})
    legs = await TreasuryService.transfer(
        db_session,
        test_clinic.id,
        cash,
        bank,
        Decimal("7"),
        None,
        None,
        created_by=actor.id,
    )
    await db_session.commit()
    assert all(leg.created_by == actor.id for leg in legs)


@pytest.mark.asyncio
async def test_denies_roles_without_treasury_grant(
    client, db_session: AsyncSession, test_clinic: Clinic
):
    """A clinic member whose role lacks treasury gets 403 on every route."""
    from app.core.auth.models import ClinicMembership, User
    from app.core.auth.service import create_access_token, hash_password

    user = User(
        id=uuid4(),
        email=f"no-grant-{uuid4().hex[:6]}@t.c",
        password_hash=hash_password("TestPass1234"),
        first_name="N",
        last_name="G",
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()
    db_session.add(
        ClinicMembership(id=uuid4(), user_id=user.id, clinic_id=test_clinic.id, role="guest")
    )
    await db_session.commit()
    headers = {"Authorization": f"Bearer {create_access_token(user.id, token_version=0)}"}

    assert (await client.get("/api/v1/treasury/accounts", headers=headers)).status_code == 403
    assert (
        await client.post(
            "/api/v1/treasury/accounts",
            json={"name": "X"},
            headers=headers,
        )
    ).status_code == 403
    assert (
        await client.post(
            "/api/v1/treasury/transfers",
            json={
                "from_account_id": str(uuid4()),
                "to_account_id": str(uuid4()),
                "amount": "1",
            },
            headers=headers,
        )
    ).status_code == 403
    assert (
        await client.get(f"/api/v1/treasury/accounts/{uuid4()}/entries", headers=headers)
    ).status_code == 403


@pytest.mark.asyncio
async def test_cross_clinic_accounts_are_invisible(
    client, db_session: AsyncSession, test_clinic: Clinic, auth_headers: dict
):
    """Accounts created in another clinic never surface here (HTTP level)."""
    from app.core.auth.models import ClinicMembership, User
    from app.core.auth.service import create_access_token, hash_password

    other_clinic = Clinic(
        id=uuid4(),
        name="Other Clinic",
        tax_id="B87654321",
        address={"street": "Other St", "city": "Valencia"},
        settings={"slot_duration_min": 15},
    )
    db_session.add(other_clinic)
    await db_session.flush()
    other_member = User(
        id=uuid4(),
        email=f"other-{uuid4().hex[:6]}@t.c",
        password_hash=hash_password("TestPass1234"),
        first_name="O",
        last_name="M",
        is_active=True,
    )
    db_session.add(other_member)
    await db_session.flush()
    db_session.add(
        ClinicMembership(
            id=uuid4(), user_id=other_member.id, clinic_id=other_clinic.id, role="admin"
        )
    )
    await db_session.commit()
    other_headers = {
        "Authorization": f"Bearer {create_access_token(other_member.id, token_version=0)}"
    }

    created = await client.post(
        "/api/v1/treasury/accounts",
        json={"name": "Ajena", "kind": "cash"},
        headers=other_headers,
    )
    assert created.status_code == 201

    listed = await client.get("/api/v1/treasury/accounts", headers=auth_headers)
    assert listed.status_code == 200
    assert all(a["name"] != "Ajena" for a in listed.json()["data"])

    peek = await client.get(
        f"/api/v1/treasury/accounts/{created.json()['data']['id']}/entries",
        headers=auth_headers,
    )
    assert peek.status_code == 404


@pytest.mark.asyncio
async def test_transfer_into_deactivated_account_is_422(
    db_session: AsyncSession, test_clinic: Clinic
):
    cash = await TreasuryService.create_account(db_session, test_clinic.id, {"name": "Caja"})
    bank = await TreasuryService.create_account(db_session, test_clinic.id, {"name": "Banco"})
    await TreasuryService.update_account(db_session, bank, {"is_active": False})
    await db_session.commit()
    with pytest.raises(HTTPException) as exc:
        await TreasuryService.transfer(
            db_session, test_clinic.id, cash, bank, Decimal("10"), None, None
        )
    assert exc.value.status_code == 422


@pytest.mark.asyncio
async def test_naive_datetime_is_clinic_local(db_session: AsyncSession, test_clinic: Clinic):
    """Naive input is interpreted as clinic-local wall clock (Madrid, UTC+2 in May)."""
    cash = await TreasuryService.create_account(db_session, test_clinic.id, {"name": "Caja"})
    bank = await TreasuryService.create_account(db_session, test_clinic.id, {"name": "Banco"})
    legs = await TreasuryService.transfer(
        db_session,
        test_clinic.id,
        cash,
        bank,
        Decimal("10"),
        None,
        datetime(2026, 5, 4, 10, 0),
    )
    await db_session.commit()
    assert legs[0].at == datetime(2026, 5, 4, 8, 0, tzinfo=UTC)


@pytest.mark.asyncio
async def test_list_balances_match_single_balance(db_session: AsyncSession, test_clinic: Clinic):
    """The aggregate balances map agrees with per-account balances."""
    cash = await TreasuryService.create_account(
        db_session, test_clinic.id, {"name": "Caja", "opening_balance": Decimal("100")}
    )
    bank = await TreasuryService.create_account(db_session, test_clinic.id, {"name": "Banco"})
    await TreasuryService.transfer(
        db_session, test_clinic.id, cash, bank, Decimal("30"), None, None
    )
    await db_session.commit()
    balances = await TreasuryService.balances(db_session, test_clinic.id)
    assert balances[cash.id] == await TreasuryService.balance(db_session, cash)
    assert balances[bank.id] == await TreasuryService.balance(db_session, bank)
    assert balances == {cash.id: Decimal("70"), bank.id: Decimal("30")}


@pytest.mark.asyncio
async def test_future_movement_is_422(db_session: AsyncSession, test_clinic: Clinic):
    """Future-dated transfers/corrections are typos, not data (staff_attendance rule)."""
    cash = await TreasuryService.create_account(db_session, test_clinic.id, {"name": "Caja"})
    bank = await TreasuryService.create_account(db_session, test_clinic.id, {"name": "Banco"})
    await db_session.commit()
    future = datetime.now(UTC) + timedelta(days=1)
    with pytest.raises(HTTPException) as exc:
        await TreasuryService.transfer(
            db_session, test_clinic.id, cash, bank, Decimal("10"), None, future
        )
    assert exc.value.status_code == 422
    with pytest.raises(HTTPException) as exc:
        await TreasuryService.correct(
            db_session, test_clinic.id, cash, Decimal("10"), "in", "late", future
        )
    assert exc.value.status_code == 422
