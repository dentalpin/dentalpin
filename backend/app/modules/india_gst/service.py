"""India GST module service layer — tax calculation, settings, catalog defaults.

Business logic only, no FastAPI imports (mirrors billing/verifactu).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .constants import DEFAULT_DENTAL_SAC_CODE
from .models import IndiaGstCatalogItem, IndiaGstSettings

INDIA_FY_START_MONTH = 4  # India's financial year runs April (4) to March.


def _quantize(value) -> Decimal:
    """Always route through ``str()`` before ``Decimal()`` — guards
    against float contamination, mirroring verifactu's ``_format_amount``.
    ``ROUND_HALF_UP`` (away from zero on ties), the rounding GST
    reporting expects — not Python's default banker's rounding.
    """
    if not isinstance(value, Decimal):
        value = Decimal(str(value or 0))
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


@dataclass
class GstLineInput:
    invoice_item_id: UUID | None
    vat_rate: float | Decimal
    line_tax: Decimal
    sac_code: str | None = None


@dataclass
class GstLineBreakdown:
    invoice_item_id: UUID | None
    sac_code: str | None
    tax_type: str  # "intra" | "inter"
    cgst_rate: Decimal = field(default_factory=lambda: Decimal("0"))
    cgst_amount: Decimal = field(default_factory=lambda: Decimal("0"))
    sgst_rate: Decimal = field(default_factory=lambda: Decimal("0"))
    sgst_amount: Decimal = field(default_factory=lambda: Decimal("0"))
    igst_rate: Decimal = field(default_factory=lambda: Decimal("0"))
    igst_amount: Decimal = field(default_factory=lambda: Decimal("0"))


@dataclass
class GstBreakdown:
    is_intra: bool
    lines: list[GstLineBreakdown]
    cgst_total: Decimal
    sgst_total: Decimal
    igst_total: Decimal


def compute_gst_breakdown(
    items: list[GstLineInput],
    *,
    clinic_state: str | None,
    place_of_supply: str | None,
) -> GstBreakdown:
    """Split each line's already-computed ``line_tax`` into CGST+SGST or
    IGST — never recomputes tax. Codes are compared directly (never
    display strings).

    Sign-agnostic: works unmodified for negative (credit-note) amounts,
    since it only ever adds/subtracts the line's own ``line_tax`` — it
    never assumes a positive amount. CGST and SGST are levied at the
    same rate on the same value, so the two halves MUST be equal —
    GSTR-1 reconciliation rejects asymmetric heads. Each half is the
    line tax / 2 rounded HALF_UP per head; on an odd-paise line the two
    heads together may differ from ``line_tax`` by ±0.01, which is the
    expected consequence of head-wise rounding (never an unequal split).
    """
    is_intra = bool(clinic_state) and bool(place_of_supply) and clinic_state == place_of_supply

    lines: list[GstLineBreakdown] = []
    # Quantized zero, not plain int-derived Decimal("0") — so an
    # all-inter-state (or all-intra-state) invoice still serializes its
    # untouched total as "0.00", not "0".
    cgst_total = sgst_total = igst_total = Decimal("0.00")

    for item in items:
        rate = Decimal(str(item.vat_rate or 0))
        tax_amount = _quantize(item.line_tax)

        if is_intra:
            half_rate = rate / 2
            cgst_amount = _quantize(tax_amount / 2)
            sgst_amount = cgst_amount
            lines.append(
                GstLineBreakdown(
                    invoice_item_id=item.invoice_item_id,
                    sac_code=item.sac_code,
                    tax_type="intra",
                    cgst_rate=half_rate,
                    cgst_amount=cgst_amount,
                    sgst_rate=half_rate,
                    sgst_amount=sgst_amount,
                )
            )
            cgst_total += cgst_amount
            sgst_total += sgst_amount
        else:
            lines.append(
                GstLineBreakdown(
                    invoice_item_id=item.invoice_item_id,
                    sac_code=item.sac_code,
                    tax_type="inter",
                    igst_rate=rate,
                    igst_amount=tax_amount,
                )
            )
            igst_total += tax_amount

    return GstBreakdown(
        is_intra=is_intra,
        lines=lines,
        cgst_total=cgst_total,
        sgst_total=sgst_total,
        igst_total=igst_total,
    )


def fy_label(issue_date) -> str:
    """``FY{yy}-{yy+1}`` — India's financial year runs April through
    March, so a March invoice and the following April's invoice fall in
    different FYs even though they're one month apart.
    """
    year = issue_date.year
    if issue_date.month >= INDIA_FY_START_MONTH:
        fy_start, fy_end = year, year + 1
    else:
        fy_start, fy_end = year - 1, year
    return f"FY{fy_start % 100:02d}-{fy_end % 100:02d}"


def compute_fy_document_number(prefix: str, sequential_number: int, issue_date) -> str:
    """Format ``{prefix}/FY{yy}-{yy+1}/{seq}``."""
    return f"{prefix}/{fy_label(issue_date)}/{sequential_number:04d}"


async def allocate_fy_document_number(
    db: AsyncSession, clinic_id: UUID, prefix: str, issue_date
) -> str:
    """Allocate the next GST document number for ``(clinic, prefix, FY)``.

    GST Rule 46(b) requires a consecutive serial unique within the
    financial year. Billing's ``sequential_number`` resets on the
    *calendar* year, so reusing it repeats numbers inside one FY between
    January and March — this module keeps its own FY-scoped counter.

    Concurrency-safe: ``INSERT … ON CONFLICT DO NOTHING`` creates the
    counter row on first use, then ``SELECT … FOR UPDATE`` serializes the
    increment (same locking pattern as billing's
    ``InvoiceService.generate_invoice_number``).
    """
    from datetime import UTC, datetime
    from uuid import uuid4

    from sqlalchemy.dialects.postgresql import insert as pg_insert

    from .models import IndiaGstDocumentSequence

    label = fy_label(issue_date)
    now = datetime.now(UTC)
    await db.execute(
        pg_insert(IndiaGstDocumentSequence)
        .values(
            id=uuid4(),
            clinic_id=clinic_id,
            prefix=prefix,
            fy_label=label,
            last_number=0,
            created_at=now,
            updated_at=now,
        )
        .on_conflict_do_nothing(constraint="uq_india_gst_document_sequences")
    )
    seq_q = await db.execute(
        select(IndiaGstDocumentSequence)
        .where(
            IndiaGstDocumentSequence.clinic_id == clinic_id,
            IndiaGstDocumentSequence.prefix == prefix,
            IndiaGstDocumentSequence.fy_label == label,
        )
        .with_for_update()
    )
    seq = seq_q.scalar_one()
    seq.last_number += 1
    await db.flush()
    return compute_fy_document_number(prefix, seq.last_number, issue_date)


async def get_or_create_settings(db: AsyncSession, clinic_id: UUID) -> IndiaGstSettings:
    result = await db.execute(
        select(IndiaGstSettings).where(IndiaGstSettings.clinic_id == clinic_id)
    )
    settings = result.scalar_one_or_none()
    if settings is None:
        settings = IndiaGstSettings(clinic_id=clinic_id)
        db.add(settings)
        await db.flush()
    return settings


class IndiaGstCatalogService:
    """SAC code defaults per treatment catalog item."""

    @staticmethod
    async def get_default(
        db: AsyncSession, clinic_id: UUID, catalog_item_id: UUID
    ) -> IndiaGstCatalogItem | None:
        result = await db.execute(
            select(IndiaGstCatalogItem).where(
                IndiaGstCatalogItem.clinic_id == clinic_id,
                IndiaGstCatalogItem.catalog_item_id == catalog_item_id,
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def upsert(
        db: AsyncSession,
        clinic_id: UUID,
        catalog_item_id: UUID,
        *,
        sac_code: str,
        notes: str | None = None,
    ) -> IndiaGstCatalogItem:
        existing = await IndiaGstCatalogService.get_default(db, clinic_id, catalog_item_id)
        if existing is None:
            existing = IndiaGstCatalogItem(clinic_id=clinic_id, catalog_item_id=catalog_item_id)
            db.add(existing)
        existing.sac_code = sac_code
        existing.notes = notes
        await db.flush()
        return existing

    @staticmethod
    async def _missing_sac_items(db: AsyncSession, clinic_id: UUID) -> list[Any]:
        """Active catalog items with no ``IndiaGstCatalogItem`` row yet."""
        from app.modules.catalog.models import TreatmentCatalogItem

        configured = await db.execute(
            select(IndiaGstCatalogItem.catalog_item_id).where(
                IndiaGstCatalogItem.clinic_id == clinic_id
            )
        )
        configured_ids = {row[0] for row in configured.all()}

        items = await db.execute(
            select(TreatmentCatalogItem).where(
                TreatmentCatalogItem.clinic_id == clinic_id,
                TreatmentCatalogItem.is_active.is_(True),
                TreatmentCatalogItem.deleted_at.is_(None),
            )
        )
        return [item for item in items.scalars() if item.id not in configured_ids]

    @staticmethod
    async def list_missing_sac(db: AsyncSession, clinic_id: UUID) -> list[dict]:
        """Treatment catalog items with no SAC default configured yet.

        Ships the whole ``names`` translation dict rather than picking one
        language server-side: this list is rendered inside the India GST
        settings page, where the viewer's own UI locale is the only
        correct choice. ``name`` stays as an English-or-code fallback for
        callers that don't localise.
        """
        missing = []
        for item in await IndiaGstCatalogService._missing_sac_items(db, clinic_id):
            names = item.names or {}
            missing.append(
                {
                    "catalog_item_id": item.id,
                    "names": names,
                    "name": names.get("en") or item.internal_code,
                    "internal_code": item.internal_code,
                }
            )
        return missing

    @staticmethod
    async def ensure_gst_vat_type(db: AsyncSession, clinic_id: UUID) -> None:
        """Get-or-create the clinic's ``GST 18%`` VAT type.

        Dental clinics coming from the default demo/catalog only have a
        0% VAT type, so without this the user would have to hand-create
        the GST slab in the catalog module before any invoice line could
        carry tax. Idempotent: matched by the English display name.
        """
        from app.modules.catalog.models import VatType

        existing = await db.execute(
            select(VatType.id).where(
                VatType.clinic_id == clinic_id,
                VatType.names.op("->>")("en") == "GST 18%",
            )
        )
        if existing.first() is None:
            db.add(
                VatType(
                    clinic_id=clinic_id,
                    names={
                        "en": "GST 18%",
                        "es": "GST 18%",
                        "fr": "GST 18%",
                        "ta": "GST 18%",
                        "hi": "GST 18%",
                    },
                    rate=18.0,
                )
            )
            await db.flush()

    @staticmethod
    async def autoconfigure_missing_sac(
        db: AsyncSession, clinic_id: UUID, *, sac_code: str = DEFAULT_DENTAL_SAC_CODE
    ) -> int:
        """Stamp ``sac_code`` on every catalog item still missing one.

        Every treatment a dental clinic bills falls under the same SAC
        (999312, human health services), so configuring them one input at
        a time is busywork. Only *missing* items are touched — an existing
        default, however it was set, is never overwritten. Returns the
        number of rows created. The caller commits.
        """
        created = 0
        for item in await IndiaGstCatalogService._missing_sac_items(db, clinic_id):
            db.add(
                IndiaGstCatalogItem(
                    clinic_id=clinic_id,
                    catalog_item_id=item.id,
                    sac_code=sac_code,
                )
            )
            created += 1
        await db.flush()
        return created
