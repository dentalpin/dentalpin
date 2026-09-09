"""NAV implementation of ``BillingComplianceHook`` (country ``HU``).

Registered from ``NavOnlineModule.on_activate``; billing finds it by the
clinic's country. ``on_invoice_issued`` snapshots the invoice as NAV
``InvoiceData`` XML into a ``pending`` queue row — no network in the
request (the worker submits). ``on_credit_note_issued`` queues a STORNO
referencing the original number. Returns preliminary compliance data
merged into ``Invoice.compliance_data["HU"]``.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic
from app.modules.billing.hooks import BillingComplianceHook

from .models import NavOnlineRecord, NavOnlineSettings
from .services.xml_builder import HungarianTaxNumber, build_invoice_data

if TYPE_CHECKING:
    from app.modules.billing.models import Invoice


async def _settings(db: AsyncSession, clinic_id) -> NavOnlineSettings | None:
    return (
        await db.execute(select(NavOnlineSettings).where(NavOnlineSettings.clinic_id == clinic_id))
    ).scalar_one_or_none()


async def _supplier(
    db: AsyncSession, clinic_id
) -> tuple[HungarianTaxNumber | None, str, dict | None, str]:
    row = (
        await db.execute(
            select(
                Clinic.tax_id, Clinic.legal_name, Clinic.name, Clinic.address, Clinic.currency
            ).where(Clinic.id == clinic_id)
        )
    ).first()
    if row is None:
        return None, "", None, "EUR"
    tax_id, legal_name, name, address, currency = row
    return HungarianTaxNumber.parse(tax_id), (legal_name or name or "").strip(), address, currency


class NavOnlineHook(BillingComplianceHook):
    @property
    def country_code(self) -> str:
        return "HU"

    @property
    def name(self) -> str:
        return "NAV Online Számla (HU)"

    def get_required_fields(self) -> list[str]:
        return []  # patients are PRIVATE_PERSON customers; no tax id needed

    async def validate_before_issue(self, invoice, db) -> tuple[bool, str | None]:
        settings = await _settings(db, invoice.clinic_id)
        if settings is None or not settings.enabled:
            return True, None
        tax, _, _, currency = await _supplier(db, invoice.clinic_id)
        if tax is None:
            return False, "Állítsd be a klinika adószámát (8 vagy 11 számjegy) a NAV beküldéshez."
        if (currency or "HUF") != "HUF":
            return False, "A NAV Online Számla első fázisa csak HUF pénznemű számlákat támogat."
        if not (settings.technical_user_login and settings.signature_key_encrypted):
            return False, "Add meg a NAV technikai felhasználót és a kulcsokat a beállításokban."
        return True, None

    async def on_invoice_issued(self, invoice, db) -> dict[str, Any]:
        return await self._queue(invoice, db, original=None)

    async def on_credit_note_issued(self, credit_note, original_invoice, db) -> dict[str, Any]:
        return await self._queue(
            credit_note, db, original=original_invoice.invoice_number if original_invoice else None
        )

    async def _queue(
        self, invoice: Invoice, db: AsyncSession, *, original: str | None
    ) -> dict[str, Any]:
        settings = await _settings(db, invoice.clinic_id)
        if settings is None or not settings.enabled:
            return {}
        tax, supplier_name, address, _ = await _supplier(db, invoice.clinic_id)
        if tax is None:
            return {}
        result = build_invoice_data(
            invoice,
            supplier_tax_number=tax,
            supplier_name=supplier_name,
            supplier_address=address,
            original_invoice_number=original,
        )
        record = NavOnlineRecord(
            clinic_id=invoice.clinic_id,
            invoice_id=invoice.id,
            operation="STORNO" if original else "CREATE",
            invoice_number=result.invoice_number,
            issue_date=invoice.issue_date or datetime.now(UTC).date(),
            gross_amount=result.gross_amount,
            xml_payload=result.xml,
            state="pending",
            created_at=datetime.now(UTC),
        )
        db.add(record)
        await db.flush()
        return {
            "HU": {
                "record_id": str(record.id),
                "operation": record.operation,
                "state": "pending",
                "environment": settings.environment,
            }
        }
