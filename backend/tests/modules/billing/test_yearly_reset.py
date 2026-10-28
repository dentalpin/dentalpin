"""A ``reset_yearly`` series restarts at 1 each year without colliding (#689).

``bil_0005`` made ``(series_id, sequential_number)`` unique over the
series' lifetime while ``generate_number`` reset the counter every
January, so the first invoice of a new year raised ``IntegrityError``
(a 500). Nothing tested the reset, and no test crossed a year boundary.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic, User
from app.modules.billing.models import Invoice, InvoiceItem, InvoiceSeries
from app.modules.billing.service import InvoiceSeriesService, InvoiceService
from app.modules.billing.workflow import InvoiceWorkflowService
from app.modules.patients.models import Patient
from app.modules.reports.services.billing import BillingReportService


async def _user_id(db: AsyncSession):
    return (await db.execute(select(User))).scalars().first().id


async def _patient(db: AsyncSession, clinic: Clinic) -> Patient:
    patient = Patient(
        id=uuid4(),
        clinic_id=clinic.id,
        first_name="Ana",
        last_name="Pérez",
        national_id="12345678Z",
        national_id_type="dni",
    )
    db.add(patient)
    await db.flush()
    return patient


async def _series(db: AsyncSession, clinic: Clinic, **fields) -> InvoiceSeries:
    series = InvoiceSeries(
        id=uuid4(),
        clinic_id=clinic.id,
        prefix="FAC",
        series_type="invoice",
        is_default=True,
        **fields,
    )
    db.add(series)
    await db.flush()
    return series


async def _issue(db: AsyncSession, clinic: Clinic, patient: Patient, today: date) -> Invoice:
    user_id = await _user_id(db)
    draft = Invoice(
        id=uuid4(),
        clinic_id=clinic.id,
        patient_id=patient.id,
        status="draft",
        subtotal=Decimal("60.00"),
        total=Decimal("60.00"),
        created_by=user_id,
    )
    db.add(draft)
    await db.flush()
    db.add(
        InvoiceItem(
            id=uuid4(),
            clinic_id=clinic.id,
            invoice_id=draft.id,
            description="Limpieza",
            unit_price=Decimal("60.00"),
            quantity=1,
            vat_rate=0.0,
            line_subtotal=Decimal("60.00"),
            line_tax=Decimal("0.00"),
            line_total=Decimal("60.00"),
            display_order=0,
        )
    )
    await db.commit()
    inv = await InvoiceService.get_invoice(
        db, clinic.id, draft.id, include_items=True, include_payments=False
    )
    issued = await InvoiceWorkflowService.issue_invoice(db, inv, user_id, today=today)
    await db.commit()
    return issued


@pytest.mark.asyncio
async def test_first_invoice_of_a_new_year_restarts_at_one(
    db_session: AsyncSession, test_clinic: Clinic
) -> None:
    patient = await _patient(db_session, test_clinic)
    await _series(db_session, test_clinic, last_reset_year=2026)

    dec = await _issue(db_session, test_clinic, patient, date(2026, 12, 31))
    jan = await _issue(db_session, test_clinic, patient, date(2027, 1, 1))

    assert (dec.invoice_number, dec.sequential_number, dec.fiscal_year) == (
        "FAC-2026-0001",
        1,
        2026,
    )
    assert (jan.invoice_number, jan.sequential_number, jan.fiscal_year) == (
        "FAC-2027-0001",
        1,
        2027,
    )


@pytest.mark.asyncio
async def test_a_series_without_yearly_reset_keeps_counting(
    db_session: AsyncSession, test_clinic: Clinic
) -> None:
    patient = await _patient(db_session, test_clinic)
    await _series(db_session, test_clinic, reset_yearly=False, last_reset_year=2026)

    await _issue(db_session, test_clinic, patient, date(2026, 12, 31))
    jan = await _issue(db_session, test_clinic, patient, date(2027, 1, 1))

    assert (jan.invoice_number, jan.sequential_number, jan.fiscal_year) == (
        "FAC-2027-0002",
        2,
        2027,
    )


@pytest.mark.asyncio
async def test_the_sequential_is_still_unique_within_a_year(
    db_session: AsyncSession, test_clinic: Clinic
) -> None:
    patient = await _patient(db_session, test_clinic)
    series = await _series(db_session, test_clinic)
    user_id = await _user_id(db_session)

    def issued(number: str, year: int) -> Invoice:
        return Invoice(
            id=uuid4(),
            clinic_id=test_clinic.id,
            patient_id=patient.id,
            invoice_number=number,
            series_id=series.id,
            sequential_number=7,
            fiscal_year=year,
            status="issued",
            issue_date=date(year, 6, 1),
            subtotal=Decimal("10"),
            total=Decimal("10"),
            created_by=user_id,
        )

    db_session.add_all([issued("FAC-2026-0007", 2026), issued("FAC-2027-0007", 2027)])
    await db_session.flush()

    db_session.add(issued("FAC-2027-9999", 2027))
    with pytest.raises(IntegrityError):
        await db_session.flush()


@pytest.mark.asyncio
async def test_counter_reset_compares_against_this_year_only(
    db_session: AsyncSession, test_clinic: Clinic
) -> None:
    patient = await _patient(db_session, test_clinic)
    series = await _series(db_session, test_clinic, last_reset_year=2026)
    for _ in range(3):
        await _issue(db_session, test_clinic, patient, date(2026, 12, 31))
    await _issue(db_session, test_clinic, patient, date(2027, 1, 2))
    await db_session.refresh(series)

    # Last year's 3 no longer competes with this year's 1.
    await InvoiceSeriesService.reset_series_counter(
        db_session, series, 2, changed_by=await _user_id(db_session)
    )
    assert series.current_number == 2

    with pytest.raises(ValueError, match="greater than 1"):
        await InvoiceSeriesService.reset_series_counter(
            db_session, series, 1, changed_by=await _user_id(db_session)
        )


@pytest.mark.asyncio
async def test_numbering_gaps_are_grouped_by_fiscal_year(
    db_session: AsyncSession, test_clinic: Clinic
) -> None:
    """All three drafts are created today; only the fiscal year tells the
    two counters apart. Grouping by ``created_at`` let 2027's #2 hide
    2026's missing #2."""
    patient = await _patient(db_session, test_clinic)
    series = await _series(db_session, test_clinic)
    user_id = await _user_id(db_session)
    for year, seq in ((2026, 1), (2026, 3), (2027, 2)):
        db_session.add(
            Invoice(
                id=uuid4(),
                clinic_id=test_clinic.id,
                patient_id=patient.id,
                invoice_number=f"FAC-{year}-{seq:04d}",
                series_id=series.id,
                sequential_number=seq,
                fiscal_year=year,
                status="issued",
                issue_date=date(year, 6, 1),
                subtotal=Decimal("10"),
                total=Decimal("10"),
                created_by=user_id,
            )
        )
    await db_session.flush()

    gaps = await BillingReportService.get_numbering_gaps(db_session, test_clinic.id)

    by_year = {g["year"]: g for g in gaps if g["series_prefix"] == "FAC"}
    assert set(by_year) == {2026, 2027}
    assert by_year[2026]["missing_numbers"] == [2]
    assert by_year[2027]["missing_numbers"] == [1]
