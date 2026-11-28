"""NAV implementation of ``BillingComplianceHook`` (country ``HU``).

Registered from ``NavOnlineModule.on_activate``; billing finds it by the
clinic's country. ``on_invoice_issued`` snapshots the invoice as NAV
``InvoiceData`` XML into a ``pending`` queue row — no network in the
request (the worker submits). ``on_credit_note_issued`` queues a
modification document referencing the original number: STORNO when the
note cancels what is left of the original, MODIFY for a partial note
(#1069). Returns preliminary compliance data merged into
``Invoice.compliance_data["HU"]``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic
from app.core.utils.dates import clinic_today_for
from app.modules.billing.hooks import BillingComplianceHook
from app.modules.billing.models import Invoice, InvoiceItem

from .models import NavOnlineRecord, NavOnlineSettings
from .services.xml_builder import HungarianTaxNumber, build_invoice_data, count_lines


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


MODIFICATION_OPERATIONS = ("STORNO", "MODIFY")


@dataclass(frozen=True)
class _Chain:
    """What NAV already holds for an original invoice (#1069)."""

    modification_index: int  # for the next modification document
    line_number_offset: int  # lines of the original + earlier modifications
    gross_so_far: Decimal  # original gross + earlier modifications' gross


async def _modification_chain(db: AsyncSession, original: Invoice, exclude_invoice_id) -> _Chain:
    """Read the chain from this module's own queue rows, clinic-scoped.

    Earlier modification documents are the STORNO/MODIFY rows of the
    original's other credit notes, in any state: a row's XML is a snapshot
    that a retry resends unchanged, so its index stays taken. The original's
    own lines and gross come from its CREATE row; an original issued before
    NAV reporting was enabled has none, then billing's items/total are used.
    """
    clinic_id = original.clinic_id
    earlier = (
        await db.execute(
            select(NavOnlineRecord.xml_payload, NavOnlineRecord.gross_amount)
            .join(Invoice, Invoice.id == NavOnlineRecord.invoice_id)
            .where(
                NavOnlineRecord.clinic_id == clinic_id,
                NavOnlineRecord.operation.in_(MODIFICATION_OPERATIONS),
                NavOnlineRecord.invoice_id != exclude_invoice_id,
                Invoice.clinic_id == clinic_id,
                Invoice.credit_note_for_id == original.id,
            )
        )
    ).all()
    create_row = (
        await db.execute(
            select(NavOnlineRecord.xml_payload, NavOnlineRecord.gross_amount)
            .where(
                NavOnlineRecord.clinic_id == clinic_id,
                NavOnlineRecord.invoice_id == original.id,
                NavOnlineRecord.operation == "CREATE",
            )
            .order_by(NavOnlineRecord.created_at)
            .limit(1)
        )
    ).first()
    if create_row is not None:
        original_lines = count_lines(create_row.xml_payload)
        original_gross = Decimal(create_row.gross_amount)
    else:
        original_lines = (
            await db.execute(
                select(func.count(InvoiceItem.id)).where(
                    InvoiceItem.invoice_id == original.id, InvoiceItem.clinic_id == clinic_id
                )
            )
        ).scalar_one()
        original_gross = Decimal(str(original.total or 0))
    return _Chain(
        modification_index=len(earlier) + 1,
        line_number_offset=original_lines + sum(count_lines(r.xml_payload) for r in earlier),
        gross_so_far=original_gross + sum((Decimal(r.gross_amount) for r in earlier), Decimal(0)),
    )


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
        return await self._queue(credit_note, db, original=original_invoice)

    async def _queue(
        self, invoice: Invoice, db: AsyncSession, *, original: Invoice | None
    ) -> dict[str, Any]:
        settings = await _settings(db, invoice.clinic_id)
        if settings is None or not settings.enabled:
            return {}
        tax, supplier_name, address, _ = await _supplier(db, invoice.clinic_id)
        if tax is None:
            return {}
        chain = (
            await _modification_chain(db, original, exclude_invoice_id=invoice.id)
            if original is not None
            else None
        )
        result = build_invoice_data(
            invoice,
            supplier_tax_number=tax,
            supplier_name=supplier_name,
            supplier_address=address,
            original_invoice_number=original.invoice_number if original is not None else None,
            modification_index=chain.modification_index if chain else 1,
            line_number_offset=chain.line_number_offset if chain else 0,
        )
        if chain is None:
            operation = "CREATE"
        elif chain.gross_so_far + result.gross_amount == 0:
            # Nothing of the original is left on NAV's books: érvénytelenítés.
            operation = "STORNO"
        else:
            operation = "MODIFY"  # partial credit note
        record = NavOnlineRecord(
            clinic_id=invoice.clinic_id,
            invoice_id=invoice.id,
            operation=operation,
            invoice_number=result.invoice_number,
            issue_date=invoice.issue_date or await clinic_today_for(db, invoice.clinic_id),
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
