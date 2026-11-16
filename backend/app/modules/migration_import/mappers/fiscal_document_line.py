"""Map ``fiscal_document_line`` → :class:`billing.InvoiceItem`.

Dental-bridge canonicalises Gesdén's ``LinAdmin`` into one
``CanonicalFiscalDocumentLine`` per row. Each line bills a concept under
a parent :class:`billing.Invoice` (which the sibling fiscal-document
mapper already created). Without this mapper, lines silently fall into
``RawEntity`` and the imported invoice ends up header-only — totals look
right but reports that cross factura↔tratamiento return nothing.

Like the fiscal-document header, we bypass ``InvoiceItemService`` and
write the model directly: the service's create path assumes an
**unbilled** budget/treatment context, which historical imports lack.
The DPMF payload carries the final billed snapshot — unit_price,
quantity, discount, VAT — so we copy verbatim and recompute totals
locally.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select

from app.modules.billing.models import InvoiceItem
from app.modules.odontogram.models import Treatment
from app.modules.treatment_plan.models import PlannedTreatmentItem

from ..models import ImportWarning
from .base import MapperContext


class FiscalDocumentLineMapper:
    async def apply(
        self,
        ctx: MapperContext,
        *,
        entity_type: str,
        payload: dict[str, Any],
        raw: dict[str, Any],
        canonical_uuid: str,
        source_id: str,
        source_system: str,
    ) -> UUID | None:
        existing = await ctx.resolver.get("fiscal_document_line", canonical_uuid)
        if existing is not None:
            return existing

        document_uuid = payload.get("document_uuid")
        if not document_uuid:
            await _warn(
                ctx,
                source_id,
                "fiscal_document_line.no_document",
                "Línea omitida: sin documento padre en origen.",
            )
            return None

        invoice_id = await ctx.resolver.get("fiscal_document", str(document_uuid))
        if invoice_id is None:
            await _warn(
                ctx,
                source_id,
                "fiscal_document_line.unmapped_document",
                "Línea omitida: factura padre no mapeada previamente.",
            )
            return None

        catalog_item_id = await _resolve_catalog_item(ctx, payload, source_id)

        quantity = _coerce_int(payload.get("units")) or 1
        quantity = max(quantity, 1)

        # ``amount`` is the line total in Gesdén; ``base_amount`` is the
        # pre-tax taxable base. We prefer base/quantity for unit_price so
        # discount + VAT recompose to the original ``amount``.
        base_amount = _decimal(payload.get("base_amount"))
        line_amount = _decimal(payload.get("amount"))
        unit_price = (
            (base_amount / Decimal(quantity)).quantize(Decimal("0.01"))
            if base_amount is not None
            else (
                (line_amount / Decimal(quantity)).quantize(Decimal("0.01"))
                if line_amount is not None
                else Decimal("0.00")
            )
        )

        discount_amount = _decimal(payload.get("discount_amount"))
        discount_percent = _decimal(payload.get("discount_percent"))
        if discount_amount and discount_amount > 0:
            discount_type: str | None = "absolute"
            discount_value: Decimal | None = discount_amount
            line_discount = discount_amount
        elif discount_percent and discount_percent > 0:
            discount_type = "percentage"
            discount_value = discount_percent
            line_discount = (
                unit_price * Decimal(quantity) * discount_percent / Decimal(100)
            ).quantize(Decimal("0.01"))
        else:
            discount_type = None
            discount_value = None
            line_discount = Decimal("0.00")

        vat_percent = _decimal(payload.get("vat_percent")) or Decimal("0")
        vat_amount = _decimal(payload.get("vat_amount"))
        line_subtotal = (unit_price * Decimal(quantity)).quantize(Decimal("0.01"))
        line_tax = (
            vat_amount.quantize(Decimal("0.01"))
            if vat_amount is not None
            else ((line_subtotal - line_discount) * vat_percent / Decimal(100)).quantize(
                Decimal("0.01")
            )
        )
        line_total = (
            line_amount.quantize(Decimal("0.01"))
            if line_amount is not None
            else (line_subtotal - line_discount + line_tax).quantize(Decimal("0.01"))
        )

        item = InvoiceItem(
            id=uuid4(),
            clinic_id=ctx.clinic_id,
            invoice_id=invoice_id,
            catalog_item_id=catalog_item_id,
            description=(payload.get("concept") or f"Concepto importado ({source_id})")[:500],
            unit_price=unit_price,
            quantity=quantity,
            discount_type=discount_type,
            discount_value=discount_value,
            vat_rate=float(vat_percent),
            line_subtotal=line_subtotal,
            line_discount=line_discount,
            line_tax=line_tax,
            line_total=line_total,
            display_order=_coerce_int(payload.get("line_number")) or 0,
        )
        ctx.db.add(item)
        await ctx.db.flush()

        await ctx.resolver.set(
            entity_type="fiscal_document_line",
            canonical_uuid=canonical_uuid,
            source_system=source_system,
            dentalpin_table="invoice_items",
            dentalpin_id=item.id,
        )
        return item.id


async def _resolve_catalog_item(
    ctx: MapperContext, payload: dict[str, Any], source_id: str
) -> UUID | None:
    # As for budget lines, resolve the parent first, then the tariff variant.
    for field, entity_type in (
        ("treatment_uuid", "treatment_catalog_item"),
        ("treatment_variant_uuid", "treatment_catalog_variant"),
    ):
        if catalog_uuid := payload.get(field):
            catalog_item_id = await ctx.resolver.get(entity_type, str(catalog_uuid))
            if catalog_item_id is not None:
                return catalog_item_id
            await _warn(
                ctx,
                source_id,
                "fiscal_document_line.unmapped_catalog_reference",
                f"Referencia de catálogo no mapeada ({field}={catalog_uuid}).",
            )

    # Gesdén fiscal lines can recover their catalog link via the applied act.
    applied_uuid = payload.get("applied_treatment_uuid")
    if not applied_uuid:
        return None
    plan_item_id = await ctx.resolver.get("applied_treatment", str(applied_uuid))
    if plan_item_id is None:
        return None
    result = await ctx.db.execute(
        select(Treatment.catalog_item_id)
        .join(PlannedTreatmentItem, PlannedTreatmentItem.treatment_id == Treatment.id)
        .where(
            PlannedTreatmentItem.id == plan_item_id,
            Treatment.clinic_id == ctx.clinic_id,
        )
    )
    return result.scalar_one_or_none()


async def _warn(ctx: MapperContext, source_id: str, code: str, message: str) -> None:
    ctx.db.add(
        ImportWarning(
            job_id=ctx.job_id,
            entity_type="fiscal_document_line",
            source_id=source_id,
            severity="warn",
            code=code,
            message=message,
        )
    )


def _decimal(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


def _coerce_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
