"""Imported invoices retain their fiscal snapshot and have no operational balance."""

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import func, select

from app.core.auth.models import User
from app.modules.accounting_export.service import AccountingExportService
from app.modules.billing.models import Invoice, InvoiceHistory, InvoicePayment
from app.modules.billing.service import compute_paid_summary
from app.modules.billing.workflow import InvoiceWorkflowService
from app.modules.migration_import.mappers.base import MapperContext, MappingResolver
from app.modules.migration_import.mappers.fiscal_document import FiscalDocumentMapper
from app.modules.migration_import.models import ImportJob
from app.modules.payments.models import Payment
from app.modules.reports.services.billing import BillingReportService
from app.modules.reports.services.financial import FinancialReportService
from app.modules.verifactu.hook import VerifactuHook
from app.modules.verifactu.models import VerifactuRecord, VerifactuSettings

INVOICES = "/api/v1/billing/invoices"
ISSUE_DATE = date(2023, 10, 1)
HISTORICAL_TOTAL = Decimal("125.50")
CURRENT_TOTAL = Decimal("79.00")


async def _invoice(db, patient, *, historical=False, status="issued"):
    invoice = Invoice(
        clinic_id=patient.clinic_id,
        patient_id=patient.id,
        created_by=await db.scalar(select(User.id)),
        invoice_number=f"TEST-{uuid4().hex[:10]}",
        status=status,
        is_historical=historical,
        issue_date=ISSUE_DATE,
        due_date=ISSUE_DATE,
        subtotal=HISTORICAL_TOTAL if historical else CURRENT_TOTAL,
        total=HISTORICAL_TOTAL if historical else CURRENT_TOTAL,
    )
    db.add(invoice)
    await db.flush()
    return invoice


@pytest.mark.asyncio
async def test_importer_sets_marker_and_retains_source_snapshot(db_session, test_patient):
    actor = await db_session.scalar(select(User.id))
    clinic_id = test_patient.clinic_id
    job = ImportJob(
        clinic_id=clinic_id,
        created_by=actor,
        original_filename="synthetic.dpm",
        file_path="/tmp/synthetic-877.dpm",
    )
    db_session.add(job)
    await db_session.flush()
    resolver = MappingResolver(db_session, clinic_id, job.id)
    patient_uuid = str(uuid4())
    await resolver.set(
        entity_type="patient",
        canonical_uuid=patient_uuid,
        source_system="synthetic",
        dentalpin_table="patients",
        dentalpin_id=test_patient.id,
    )
    ctx = MapperContext(db_session, clinic_id, job.id, resolver, False, actor)
    metadata = {
        "entity_type": "fiscal_document",
        "raw": {},
        "canonical_uuid": str(uuid4()),
        "source_id": "100",
        "source_system": "synthetic",
    }
    payload = {
        "patient_uuid": patient_uuid,
        "document_date": "2023-10-01",
        "number": "100",
        "series": "SRC",
        "status": "paid",
        "total": "125.50",
        "subtotal": "125.50",
        "tax_total": "0",
    }
    mapper = FiscalDocumentMapper()
    identifier = await mapper.apply(ctx, payload=payload, **metadata)
    assert await mapper.apply(ctx, payload=payload, **metadata) == identifier
    invoice = await db_session.get(Invoice, identifier)
    assert invoice.is_historical is True
    assert invoice.invoice_number == "SRC-100"
    assert invoice.patient_id == test_patient.id
    assert invoice.issue_date == ISSUE_DATE
    assert invoice.total == HISTORICAL_TOTAL
    assert invoice.status == "paid"
    assert invoice.series_id is None
    assert invoice.sequential_number is None
    assert await compute_paid_summary(db_session, clinic_id, invoice.id) == (0, 0)
    assert (
        await InvoiceWorkflowService.recalc_invoice_status(db_session, invoice, actor_id=actor)
        == "paid"
    )


@pytest.mark.asyncio
async def test_invoice_reads_and_guards(client, db_session, test_patient, auth_headers):
    historical = await _invoice(db_session, test_patient, historical=True)
    current = await _invoice(db_session, test_patient)
    historical_draft = await _invoice(db_session, test_patient, historical=True, status="draft")
    await db_session.commit()
    root = f"{INVOICES}/{historical.id}"
    reply = await client.get(root, headers=auth_headers)
    assert reply.status_code == 200, reply.text
    data = reply.json()["data"]
    assert data["is_historical"] is True
    assert Decimal(data["total"]) == HISTORICAL_TOTAL
    assert Decimal(data["total_paid"]) == Decimal(data["balance_due"]) == 0

    result = await client.get(INVOICES, headers=auth_headers)
    assert result.status_code == 200, result.text
    rows = {row["id"]: row for row in result.json()["data"]}
    assert rows[str(historical.id)]["is_historical"] is True
    assert Decimal(rows[str(historical.id)]["balance_due"]) == 0
    assert rows[str(current.id)]["is_historical"] is False
    assert Decimal(rows[str(current.id)]["balance_due"]) == CURRENT_TOTAL

    overdue = await client.get(INVOICES, params={"overdue": "true"}, headers=auth_headers)
    assert overdue.status_code == 200, overdue.text
    assert [row["id"] for row in overdue.json()["data"]] == [str(current.id)]

    for endpoint, payload in [
        ("credit-note", {"reason": "Synthetic correction"}),
        ("payments", {"amount": "10.00", "method": "cash"}),
        ("send-email", {"send_method": "email"}),
        ("send-email", {"send_method": "whatsapp"}),
        ("send-email", {"send_method": "manual"}),
    ]:
        reply = await client.post(f"{root}/{endpoint}", json=payload, headers=auth_headers)
        assert reply.status_code == 400, reply.text
        assert "historical" in reply.text.lower()

    reply = await client.post(
        f"{INVOICES}/{historical_draft.id}/issue", json={}, headers=auth_headers
    )
    assert reply.status_code == 400, reply.text
    assert "historical" in reply.text.lower()
    assert await db_session.scalar(select(func.count()).select_from(Invoice)) == 3
    assert await db_session.scalar(select(func.count()).select_from(InvoiceHistory)) == 0
    assert await db_session.scalar(select(func.count()).select_from(Payment)) == 0


@pytest.mark.asyncio
async def test_reporting_and_fiscal_integrations(db_session, test_patient):
    historical = await _invoice(db_session, test_patient, historical=True)
    current = await _invoice(db_session, test_patient)
    clinic_id = test_patient.clinic_id
    settings = VerifactuSettings(clinic_id=clinic_id, enabled=True, numero_instalacion="01")
    db_session.add(settings)
    await db_session.flush()

    assert await VerifactuHook().on_invoice_issued(historical, db_session) == {}
    assert await db_session.scalar(select(func.count()).select_from(VerifactuRecord)) == 0
    assert settings.last_huella is None
    export = await AccountingExportService.fetch(
        db_session, clinic_id, ISSUE_DATE, ISSUE_DATE, ["issued"]
    )
    assert [invoice.id for invoice in export] == [current.id]

    patient = await BillingReportService.get_patient_summary(db_session, clinic_id, test_patient.id)
    assert patient["total_invoiced"] == HISTORICAL_TOTAL + CURRENT_TOTAL
    assert patient["balance_pending"] == CURRENT_TOTAL
    assert patient["total_paid"] == 0

    summary = await BillingReportService.get_summary(db_session, clinic_id, ISSUE_DATE, ISSUE_DATE)
    assert summary["invoice_count"] == 2
    assert summary["total_invoiced"] == HISTORICAL_TOTAL + CURRENT_TOTAL
    assert summary["total_pending"] == CURRENT_TOTAL
    assert summary["overdue_count"] == 1
    assert summary["total_paid"] == 0
    overdue = await BillingReportService.get_overdue_invoices(db_session, clinic_id)
    assert [row["id"] for row in overdue] == [current.id]

    outside = await BillingReportService.get_summary(
        db_session, clinic_id, date(2024, 1, 1), date(2024, 1, 31)
    )
    assert outside["total_invoiced"] == 0
    aging = await FinancialReportService.aging_buckets(db_session, clinic_id)
    assert sum(row["total"] for row in aging) == CURRENT_TOTAL
    assert await db_session.scalar(select(func.count()).select_from(InvoicePayment)) == 0
