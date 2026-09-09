"""payroll: masked profiles, period lifecycle, balanced entries, reports, isolation."""

from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi import HTTPException
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic, ClinicMembership, User
from app.core.auth.service import create_access_token
from app.modules.payroll.schemas import (
    PayrollEntryCreate,
    PayrollEntryUpdate,
    PayrollPeriodCreate,
    PayrollProfileCreate,
    PayrollProfileUpdate,
    PeriodTransition,
)
from app.modules.payroll.service import (
    EntryService,
    PeriodService,
    ProfileService,
    ReportService,
    mask_profile,
)

IBAN = "ES9121000418450200051332"
TAX_ID = "12345678Z"


async def _make_user(db: AsyncSession, clinic_id=None, role="dentist") -> User:
    """A staff user; with ``clinic_id`` also a member of that clinic."""
    user = User(
        email=f"staff-{uuid4().hex[:8]}@test.clinic",
        password_hash="not-a-real-hash",
        first_name="Staff",
        last_name="Member",
    )
    db.add(user)
    if clinic_id is not None:
        await db.flush()
        db.add(ClinicMembership(user_id=user.id, clinic_id=clinic_id, role=role))
    await db.commit()
    await db.refresh(user)
    return user


async def _make_profile(db, clinic_id, user_id=None, **kw):
    user = await _make_user(db, clinic_id) if user_id is None else None
    return await ProfileService.create_profile(
        db,
        clinic_id,
        PayrollProfileCreate(
            user_id=user_id or user.id,
            payment_type=kw.pop("payment_type", "monthly"),
            base_amount=kw.pop("base_amount", Decimal("2500.00")),
            currency=kw.pop("currency", "EUR"),
            bank_account=kw.pop("bank_account", IBAN),
            tax_id=kw.pop("tax_id", TAX_ID),
        ),
    )


async def _make_period(db, clinic_id, month="2026-01"):
    return await PeriodService.create_period(db, clinic_id, PayrollPeriodCreate(month=month))


async def _make_entry(db, clinic_id, period_id, user_id, gross="3000", ded="600", net="2400"):
    return await EntryService.create_entry(
        db,
        clinic_id,
        PayrollEntryCreate(
            period_id=period_id,
            user_id=user_id,
            gross=Decimal(gross),
            deductions=Decimal(ded),
            net=Decimal(net),
        ),
    )


@pytest.mark.asyncio
async def test_profile_create_is_masked(db_session: AsyncSession, test_clinic: Clinic):
    user = await _make_user(db_session, test_clinic.id)
    row = await _make_profile(db_session, test_clinic.id, user.id)
    out = mask_profile(row)
    assert out.has_bank_account is True
    assert out.bank_last_4 == IBAN[-4:]
    assert out.has_tax_id is True
    assert out.tax_last_4 == TAX_ID[-4:]
    # The masked shape carries neither plaintext nor ciphertext, anywhere.
    dumped = out.model_dump_json()
    assert IBAN not in dumped
    assert TAX_ID not in dumped
    assert row.bank_account_encrypted not in dumped
    assert row.tax_id_encrypted not in dumped
    # ...but the ciphertext at rest decrypts (admin replace-to-edit reads it back never).
    assert row.bank_account_encrypted != IBAN
    assert row.tax_id_encrypted != TAX_ID


@pytest.mark.asyncio
async def test_profile_unknown_or_foreign_user_is_404(
    db_session: AsyncSession, test_clinic: Clinic
):
    with pytest.raises(HTTPException) as exc:
        await ProfileService.create_profile(
            db_session,
            test_clinic.id,
            PayrollProfileCreate(user_id=uuid4(), bank_account=IBAN),
        )
    assert exc.value.status_code == 404
    # A real user who is not a member of this clinic is equally invisible.
    outsider = await _make_user(db_session)
    with pytest.raises(HTTPException) as exc:
        await ProfileService.create_profile(
            db_session, test_clinic.id, PayrollProfileCreate(user_id=outsider.id)
        )
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_profile_duplicate_is_409(db_session: AsyncSession, test_clinic: Clinic):
    user = await _make_user(db_session, test_clinic.id)
    await _make_profile(db_session, test_clinic.id, user.id)
    with pytest.raises(HTTPException) as exc:
        await _make_profile(db_session, test_clinic.id, user.id)
    assert exc.value.status_code == 409


@pytest.mark.asyncio
async def test_profile_replace_to_edit(db_session: AsyncSession, test_clinic: Clinic):
    user = await _make_user(db_session, test_clinic.id)
    row = await _make_profile(db_session, test_clinic.id, user.id)
    old_cipher = row.bank_account_encrypted
    # Omitted fields keep the stored ciphertext.
    row = await ProfileService.update_profile(
        db_session, row, PayrollProfileUpdate(base_amount=Decimal("2600.00"))
    )
    assert row.base_amount == Decimal("2600.00")
    assert row.bank_account_encrypted == old_cipher
    # A provided full value rotates it.
    row = await ProfileService.update_profile(
        db_session, row, PayrollProfileUpdate(bank_account="ES7620770024003102575766")
    )
    assert row.bank_account_encrypted != old_cipher
    assert mask_profile(row).bank_last_4 == "5766"


@pytest.mark.asyncio
async def test_period_lifecycle_and_conflicts(db_session: AsyncSession, test_clinic: Clinic):
    # Bind ids upfront: any rollback below expires every instance
    # (expire_on_commit=False sessions), and touching an expired
    # attribute afterwards has no greenlet for the refresh.
    clinic_id = test_clinic.id
    period = await _make_period(db_session, clinic_id)
    assert period.status == "draft"
    period_id = period.id
    with pytest.raises(HTTPException) as exc:
        await _make_period(db_session, clinic_id)
    assert exc.value.status_code == 409
    # The rollback above expires every instance in the session: re-fetch
    # before reuse (async lazy refresh has no greenlet here).
    period = await PeriodService.get_period(db_session, clinic_id, period_id)
    assert period is not None
    # draft -> paid skips a step.
    with pytest.raises(HTTPException) as exc:
        await PeriodService.transition(db_session, period, PeriodTransition(status="paid"))
    assert exc.value.status_code == 409
    period = await PeriodService.transition(db_session, period, PeriodTransition(status="closed"))
    assert period.status == "closed"
    period = await PeriodService.transition(db_session, period, PeriodTransition(status="paid"))
    assert period.status == "paid"


@pytest.mark.asyncio
async def test_entry_balanced_and_draft_gated(db_session: AsyncSession, test_clinic: Clinic):
    # Same id-binding rule as above: no instance attribute is touched
    # after a rollback in this test.
    clinic_id = test_clinic.id
    user = await _make_user(db_session, test_clinic.id)
    user_id = user.id
    period = await _make_period(db_session, clinic_id)
    period_id = period.id
    # Unbalanced books are a 422.
    with pytest.raises(HTTPException) as exc:
        await EntryService.create_entry(
            db_session,
            clinic_id,
            PayrollEntryCreate(
                period_id=period_id,
                user_id=user_id,
                gross=Decimal("3000"),
                deductions=Decimal("600"),
                net=Decimal("2500"),
            ),
        )
    assert exc.value.status_code == 422
    entry = await _make_entry(db_session, clinic_id, period_id, user_id)
    assert entry.net == Decimal("2400")
    entry_id = entry.id
    with pytest.raises(HTTPException) as exc:
        await _make_entry(db_session, clinic_id, period_id, user_id)
    assert exc.value.status_code == 409
    # The rollback expired `entry` and `period`: re-fetch before reuse.
    entry = await EntryService.get_entry(db_session, clinic_id, entry_id)
    assert entry is not None
    period = await PeriodService.get_period(db_session, clinic_id, period_id)
    assert period is not None
    # Closed periods are immutable.
    await PeriodService.transition(db_session, period, PeriodTransition(status="closed"))
    with pytest.raises(HTTPException) as exc:
        await EntryService.update_entry(db_session, entry, PayrollEntryUpdate(notes="late change"))
    assert exc.value.status_code == 409


@pytest.mark.asyncio
async def test_reports_aggregate(db_session: AsyncSession, test_clinic: Clinic):
    user_a = await _make_user(db_session, test_clinic.id)
    user_b = await _make_user(db_session, test_clinic.id)
    jan = await _make_period(db_session, test_clinic.id, "2026-01")
    feb = await _make_period(db_session, test_clinic.id, "2026-02")
    await _make_entry(db_session, test_clinic.id, jan.id, user_a.id)
    await _make_entry(
        db_session, test_clinic.id, jan.id, user_b.id, gross="2000", ded="400", net="1600"
    )
    await _make_entry(db_session, test_clinic.id, feb.id, user_a.id)
    monthly = await ReportService.monthly_report(db_session, test_clinic.id, "2026-01")
    assert monthly is not None
    assert monthly["entry_count"] == 2
    assert monthly["total_gross"] == Decimal("5000")
    assert monthly["total_net"] == Decimal("4000")
    assert await ReportService.monthly_report(db_session, test_clinic.id, "2026-03") is None
    annual = await ReportService.annual_report(db_session, test_clinic.id, "2026")
    assert annual["period_count"] == 2
    assert annual["entry_count"] == 3
    assert annual["total_gross"] == Decimal("8000")


@pytest.mark.asyncio
async def test_cross_clinic_isolation(db_session: AsyncSession, test_clinic: Clinic):
    other = Clinic(
        id=uuid4(),
        name="Other Clinic",
        tax_id="B99999993",
        address={"street": "Otra", "city": "Madrid"},
        settings={"slot_duration_min": 15},
    )
    db_session.add(other)
    await db_session.commit()
    user = await _make_user(db_session, other.id)
    await _make_profile(db_session, other.id, user.id)
    items, total = await ProfileService.list_profiles(db_session, test_clinic.id)
    assert total == 0
    assert items == []


@pytest.mark.asyncio
async def test_http_masked_and_admin_only(
    client: AsyncClient, auth_headers: dict, test_clinic: Clinic, db_session: AsyncSession
):
    staff = await _make_user(db_session, test_clinic.id)
    created = await client.post(
        "/api/v1/payroll/profiles",
        json={"user_id": str(staff.id), "bank_account": IBAN, "tax_id": TAX_ID},
        headers=auth_headers,
    )
    assert created.status_code == 201, created.text
    body = created.json()["data"]
    assert body["bank_last_4"] == IBAN[-4:]
    assert IBAN not in created.text and TAX_ID not in created.text
    assert "encrypted" not in created.text
    # Non-admin staff (any role) never see payroll.
    receptionist = await _make_user(db_session, test_clinic.id, role="receptionist")
    token = create_access_token(receptionist.id, token_version=receptionist.token_version)
    headers = {"Authorization": f"Bearer {token}"}
    assert (await client.get("/api/v1/payroll/profiles", headers=headers)).status_code == 403
    assert (
        await client.get("/api/v1/payroll/reports/annual?year=2026", headers=headers)
    ).status_code == 403


@pytest.mark.asyncio
async def test_delete_entry_draft_only(db_session: AsyncSession, test_clinic: Clinic):
    # Bind ids upfront (M15): rollbacks below expire every instance.
    clinic_id = test_clinic.id
    user = await _make_user(db_session, clinic_id)
    user_id = user.id
    period = await _make_period(db_session, clinic_id)
    period_id = period.id
    entry = await _make_entry(db_session, clinic_id, period_id, user_id)
    entry_id = entry.id
    # Draft entry deletes cleanly and is gone afterwards.
    await EntryService.delete_entry(db_session, entry)
    assert await EntryService.get_entry(db_session, clinic_id, entry_id) is None
    # Re-add, close the period: the delete now conflicts.
    entry = await _make_entry(db_session, clinic_id, period_id, user_id)
    entry_id = entry.id
    period = await PeriodService.get_period(db_session, clinic_id, period_id)
    assert period is not None
    await PeriodService.transition(db_session, period, PeriodTransition(status="closed"))
    entry = await EntryService.get_entry(db_session, clinic_id, entry_id)
    assert entry is not None
    with pytest.raises(HTTPException) as exc:
        await EntryService.delete_entry(db_session, entry)
    assert exc.value.status_code == 409


@pytest.mark.asyncio
async def test_delete_period_empty_draft_only(db_session: AsyncSession, test_clinic: Clinic):
    clinic_id = test_clinic.id
    user = await _make_user(db_session, clinic_id)
    user_id = user.id
    # Unknown ids are 404 (never leak existence across clinics).
    with pytest.raises(HTTPException) as exc:
        await PeriodService.delete_period(db_session, clinic_id, uuid4())
    assert exc.value.status_code == 404
    # A period with entries cannot go even while draft.
    full = await _make_period(db_session, clinic_id, "2026-01")
    full_id = full.id
    await _make_entry(db_session, clinic_id, full_id, user_id)
    with pytest.raises(HTTPException) as exc:
        await PeriodService.delete_period(db_session, clinic_id, full_id)
    assert exc.value.status_code == 409
    # An empty draft period deletes; a closed one conflicts.
    empty = await _make_period(db_session, clinic_id, "2026-02")
    empty_id = empty.id
    await PeriodService.delete_period(db_session, clinic_id, empty_id)
    assert await PeriodService.get_period(db_session, clinic_id, empty_id) is None
    doomed = await _make_period(db_session, clinic_id, "2026-03")
    doomed_id = doomed.id
    doomed = await PeriodService.transition(db_session, doomed, PeriodTransition(status="closed"))
    with pytest.raises(HTTPException) as exc:
        await PeriodService.delete_period(db_session, clinic_id, doomed_id)
    assert exc.value.status_code == 409


@pytest.mark.asyncio
async def test_http_delete_draft_guards(
    client: AsyncClient, auth_headers: dict, test_clinic: Clinic, db_session: AsyncSession
):
    clinic_id = test_clinic.id
    user = await _make_user(db_session, clinic_id)
    period = await _make_period(db_session, clinic_id)
    entry = await _make_entry(db_session, clinic_id, period.id, user.id)
    entry_id, period_id = entry.id, period.id
    # Entry deletes with 204 while draft; unknown ids 404.
    gone = await client.delete(f"/api/v1/payroll/entries/{entry_id}", headers=auth_headers)
    assert gone.status_code == 204, gone.text
    assert await EntryService.get_entry(db_session, clinic_id, entry_id) is None
    assert (
        await client.delete(f"/api/v1/payroll/entries/{uuid4()}", headers=auth_headers)
    ).status_code == 404
    # Empty draft period deletes with 204; unknown ids 404.
    assert (
        await client.delete(f"/api/v1/payroll/periods/{period_id}", headers=auth_headers)
    ).status_code == 204
    assert (
        await client.delete(f"/api/v1/payroll/periods/{uuid4()}", headers=auth_headers)
    ).status_code == 404
    # Closed periods refuse with 409.
    period = await _make_period(db_session, clinic_id, "2026-04")
    period = await PeriodService.transition(db_session, period, PeriodTransition(status="closed"))
    closed = await client.delete(f"/api/v1/payroll/periods/{period.id}", headers=auth_headers)
    assert closed.status_code == 409, closed.text
    # Entries of a closed period refuse with 409 at HTTP level too: create
    # while draft, close, then delete.
    late = await _make_period(db_session, clinic_id, "2026-05")
    late_id = late.id
    user2 = await _make_user(db_session, clinic_id)
    stuck = await _make_entry(db_session, clinic_id, late_id, user2.id)
    stuck_id = stuck.id
    late = await PeriodService.get_period(db_session, clinic_id, late_id)
    assert late is not None
    await PeriodService.transition(db_session, late, PeriodTransition(status="closed"))
    blocked = await client.delete(f"/api/v1/payroll/entries/{stuck_id}", headers=auth_headers)
    assert blocked.status_code == 409, blocked.text
