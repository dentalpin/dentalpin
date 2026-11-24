"""Quote and invoice emails print amounts in the clinic's currency (#1133).

The handlers passed ``float(...)`` into the template context and the
templates appended a hard-coded ``€`` (es, de, fr, it, hu, pl, pt) or
nothing (en, hi, ar, ta, te): "1300.0 €" in Spanish, a bare "1300.0" in
English, and "€" for an INR clinic. These run the real handler and the
real gateway, then render the queued message with the email service, so
they pin both halves: the context carries ``format_currency`` strings for
the locale the gateway picked, and no template adds a symbol of its own.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic, User
from app.core.email.service import email_service
from app.modules.billing.models import Invoice, InvoiceItem
from app.modules.budget.models import Budget, BudgetItem
from app.modules.catalog.models import TreatmentCatalogItem, TreatmentCategory
from app.modules.notifications.handlers import NotificationHandlers
from app.modules.notifications.models import CommunicationMessage, NotificationPreference
from app.modules.patients.models import Patient

NBSP = "\xa0"


async def _clinic_and_patient(
    db: AsyncSession,
    currency: str,
    clinic_locale: str,
    patient_locale: str | None = None,
) -> tuple[Clinic, Patient, User]:
    user = User(
        email=f"cur-{uuid4().hex[:8]}@test.com",
        password_hash="x",
        first_name="Cur",
        last_name="Rency",
    )
    clinic = Clinic(
        id=uuid4(),
        name="Currency Clinic",
        tax_id="B11223344",
        address={},
        currency=currency,
        settings={"communication_language": clinic_locale},
    )
    db.add_all([user, clinic])
    await db.flush()
    patient = Patient(
        id=uuid4(),
        clinic_id=clinic.id,
        first_name="Ana",
        last_name="Test",
        email="ana@example.com",
        status="active",
    )
    db.add(patient)
    await db.flush()
    if patient_locale:
        db.add(
            NotificationPreference(
                clinic_id=clinic.id, patient_id=patient.id, preferred_locale=patient_locale
            )
        )
        await db.flush()
    return clinic, patient, user


async def _budget(db: AsyncSession, clinic: Clinic, patient: Patient, user: User) -> Budget:
    category = TreatmentCategory(
        id=uuid4(),
        clinic_id=clinic.id,
        key=f"cat-{uuid4().hex[:8]}",
        names={"es": "Cat", "en": "Cat"},
        is_system=False,
    )
    db.add(category)
    await db.flush()
    catalog_item = TreatmentCatalogItem(
        id=uuid4(),
        clinic_id=clinic.id,
        category_id=category.id,
        internal_code=f"T-{uuid4().hex[:6]}",
        names={"es": "Corona", "en": "Crown"},
        default_price=Decimal("1300.00"),
        is_active=True,
        is_system=False,
    )
    budget = Budget(
        id=uuid4(),
        clinic_id=clinic.id,
        patient_id=patient.id,
        budget_number=f"PRES-{uuid4().hex[:8]}",
        valid_from=date(2026, 11, 1),
        created_by=user.id,
        subtotal=Decimal("1300.00"),
        total_discount=Decimal("99.50"),
        total=Decimal("1200.50"),
    )
    db.add_all([catalog_item, budget])
    await db.flush()
    db.add(
        BudgetItem(
            id=uuid4(),
            clinic_id=clinic.id,
            budget_id=budget.id,
            catalog_item_id=catalog_item.id,
            unit_price=Decimal("1300.00"),
            quantity=1,
            line_total=Decimal("1300.00"),
            tooth_number=11,
        )
    )
    await db.commit()
    return budget


async def _queued(db: AsyncSession, clinic: Clinic, key: str) -> CommunicationMessage:
    return (
        await db.execute(
            select(CommunicationMessage).where(
                CommunicationMessage.clinic_id == clinic.id,
                CommunicationMessage.template_key == key,
            )
        )
    ).scalar_one()


def _render(msg: CommunicationMessage) -> str:
    ctx = msg.context_data
    email_service._initialize()
    html = email_service._render_template(msg.template_key, ctx["locale"], ctx)
    assert html, f"{msg.template_key} did not render"
    return html


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("currency", "clinic_locale", "patient_locale", "locale", "subtotal", "discount", "total"),
    [
        ("EUR", "es", None, "es", f"1.300,00{NBSP}€", f"99,50{NBSP}€", f"1.200,50{NBSP}€"),
        ("EUR", "en", None, "en", "€1,300.00", "€99.50", "€1,200.50"),
        # The patient's preferred language wins over the clinic's, in the
        # template *and* the amounts.
        ("EUR", "es", "en", "en", "€1,300.00", "€99.50", "€1,200.50"),
        ("INR", "en", None, "en", "₹1,300.00", "₹99.50", "₹1,200.50"),
        ("INR", "es", None, "es", f"1.300,00{NBSP}INR", f"99,50{NBSP}INR", f"1.200,50{NBSP}INR"),
    ],
)
async def test_budget_sent_amounts_use_clinic_currency_and_locale(
    db_session: AsyncSession,
    currency: str,
    clinic_locale: str,
    patient_locale: str | None,
    locale: str,
    subtotal: str,
    discount: str,
    total: str,
) -> None:
    clinic, patient, user = await _clinic_and_patient(
        db_session, currency, clinic_locale, patient_locale
    )
    budget = await _budget(db_session, clinic, patient, user)

    await NotificationHandlers.on_budget_sent(
        {"clinic_id": str(clinic.id), "budget_id": str(budget.id), "send_method": "email"},
        db=db_session,
    )
    msg = await _queued(db_session, clinic, "budget_sent")
    assert msg.status == "queued"
    ctx = msg.context_data
    assert ctx["locale"] == locale
    assert ctx["subtotal"] == subtotal
    assert ctx["discount_amount"] == discount
    assert ctx["total"] == total
    assert ctx["treatments"][0]["price"] == subtotal

    html = _render(msg)
    assert total in html
    assert f"-{discount}" in html
    assert "1300.0" not in html and "1200.5" not in html
    if currency == "INR":
        assert "€" not in html
    # No template appends its own symbol after the formatted amount.
    assert f"{total} €" not in html


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("currency", "locale", "total", "tax", "line"),
    [
        ("EUR", "es", f"1.210,50{NBSP}€", f"10,50{NBSP}€", f"1.300,00{NBSP}€"),
        ("EUR", "en", "€1,210.50", "€10.50", "€1,300.00"),
        ("INR", "en", "₹1,210.50", "₹10.50", "₹1,300.00"),
    ],
)
async def test_invoice_sent_amounts_use_clinic_currency_and_locale(
    db_session: AsyncSession,
    currency: str,
    locale: str,
    total: str,
    tax: str,
    line: str,
) -> None:
    clinic, patient, user = await _clinic_and_patient(db_session, currency, locale)
    invoice = Invoice(
        id=uuid4(),
        clinic_id=clinic.id,
        patient_id=patient.id,
        invoice_number=f"FAC-{uuid4().hex[:8]}",
        status="issued",
        issue_date=date(2026, 11, 2),
        created_by=user.id,
        subtotal=Decimal("1300.00"),
        total_discount=Decimal("100.00"),
        total_tax=Decimal("10.50"),
        total=Decimal("1210.50"),
    )
    db_session.add(invoice)
    await db_session.flush()
    db_session.add(
        InvoiceItem(
            id=uuid4(),
            clinic_id=clinic.id,
            invoice_id=invoice.id,
            description="Corona",
            unit_price=Decimal("1300.00"),
            quantity=1,
            line_subtotal=Decimal("1300.00"),
            line_total=Decimal("1300.00"),
        )
    )
    await db_session.commit()

    await NotificationHandlers.on_invoice_sent(
        {"clinic_id": str(clinic.id), "invoice_id": str(invoice.id), "send_method": "email"},
        db=db_session,
    )
    msg = await _queued(db_session, clinic, "invoice_sent")
    ctx = msg.context_data
    assert ctx["locale"] == locale
    assert ctx["total"] == total
    assert ctx["total_tax"] == tax
    assert ctx["items"][0]["line_total"] == line
    # Nothing paid yet: the balance is the whole total, so the template
    # hides the separate balance row.
    assert ctx["balance_due"] == total

    html = _render(msg)
    assert total in html and tax in html and line in html
    assert "1210.5" not in html
    if currency == "INR":
        assert "€" not in html


@pytest.mark.asyncio
async def test_manual_budget_send_formats_amounts(
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    test_clinic: Clinic,
    test_patient: Patient,
) -> None:
    """``POST /notifications/send`` builds the same context the handler does.

    No ``patient_id`` in the request: the patient comes from the budget,
    and the amounts still follow that patient's preferred language.
    """
    test_clinic.currency = "INR"
    test_patient.email = "pat@example.com"
    db_session.add(
        NotificationPreference(
            clinic_id=test_clinic.id, patient_id=test_patient.id, preferred_locale="en"
        )
    )
    user = User(
        email=f"cur-{uuid4().hex[:8]}@test.com", password_hash="x", first_name="A", last_name="B"
    )
    db_session.add(user)
    await db_session.flush()
    budget = await _budget(db_session, test_clinic, test_patient, user)
    clinic_id, budget_id = test_clinic.id, budget.id

    response = await client.post(
        "/api/v1/notifications/send",
        json={"notification_type": "budget_sent", "budget_id": str(budget_id)},
        headers=auth_headers,
    )
    assert response.status_code in (200, 201), response.text

    msg = (
        await db_session.execute(
            select(CommunicationMessage).where(
                CommunicationMessage.clinic_id == clinic_id,
                CommunicationMessage.template_key == "budget_sent",
            )
        )
    ).scalar_one()
    ctx = msg.context_data
    assert ctx["locale"] == "en"
    assert ctx["total"] == "₹1,200.50"
    assert ctx["subtotal"] == "₹1,300.00"
    assert ctx["discount_amount"] == "₹99.50"
    assert ctx["treatments"][0]["price"] == "₹1,300.00"
